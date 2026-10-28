"""AI photo detection for CivicFix (offline zero-shot CLIP via onnxruntime).

When a photo is uploaded, this answers one question: what does the photo show,
and does that agree with the report title? The result is stored on the issue as
a JSON string in the issues.ai_analysis column. It NEVER changes the risk score
and NEVER blocks a report - every failure path returns None so the caller can
silently skip the enhancement.

Model files expected in ./ai_models (downloaded from Xenova/clip-vit-base-patch32):
  - model_quantized.onnx  (INT8, full CLIP graph: image + text -> logits)
  - tokenizer.json        (matching CLIP BPE tokenizer)

Result shape:
  {
    "best": "pothole",
    "confidence": 87,
    "matches_title": true,
    "suggested_category": "roads",
    "labels": [{"name": "pothole", "confidence": 87}, ...top 3]
  }
"""
from __future__ import annotations

import io
import json
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / 'ai_models'
IMAGE_SIZE = 224
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)

# CivicFix labels: (label, prompt, suggested category, title keywords for cross-check)
LABELS = (
    ('pothole', 'a photo of a pothole and cracked broken road surface', 'roads',
     ('pothole', 'potholes', 'road', 'sadak', 'street', 'asphalt', 'gaddha', 'crater')),
    ('garbage', 'a photo of garbage trash litter dumped on the ground', 'cleanliness',
     ('garbage', 'trash', 'waste', 'kachra', 'litter', 'rubbish', 'gandagi', 'safai', 'dump')),
    ('water logging', 'a photo of a street flooded and full of accumulated water', 'water',
     ('water', 'logging', 'waterlogging', 'flood', 'paani', 'leak', 'pipe', 'overflow', 'harab')),
    ('broken streetlight', 'a photo of a broken or unlit streetlight on a lamp post', 'electricity',
     ('streetlight', 'street light', 'light', 'lamp', 'batti', 'bulb', 'dark', 'lamppost')),
    ('electric wires', 'a photo of dangerous hanging electrical wires and cables', 'electricity',
     ('wire', 'wires', 'electric', 'electrical', 'cable', 'bijli', 'current', 'shock', 'short circuit')),
    ('drainage', 'a photo of an open or clogged drainage drain sewer', 'water',
     ('drain', 'drainage', 'sewer', 'nal', 'nala', 'gutter', 'manhole', 'clog')),
    ('structural damage', 'a photo of a damaged cracked building wall or collapsed structure', 'other',
     ('structure', 'building', 'wall', 'collapse', 'crack', 'deewar', 'imarat', 'bridge', 'rubble', 'ghar')),
    ('fire', 'a photo of burning fire flames and smoke', 'other',
     ('fire', 'aag', 'smoke', 'burn', 'flame', 'blaze', 'jala')),
    ('other', 'a photo of something unrelated to civic problems', 'other', ()),
)

_session_cache: dict = {'session': None, 'tokenizer': None}


def _warm_session():
    """Load the ONNX session and tokenizer once, lazily, on first use."""
    if _session_cache['session'] is not None:
        return
    model_path = MODEL_DIR / 'model_quantized.onnx'
    tokenizer_path = MODEL_DIR / 'tokenizer.json'
    if not model_path.exists() or not tokenizer_path.exists():
        raise FileNotFoundError('CLIP model files are missing from ai_models/')
    # Imported lazily so the rest of the backend never depends on these packages.
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    options = ort.SessionOptions()
    options.log_severity_level = 3  # silence ORT warnings (quantized kernels etc.)
    _session_cache['session'] = ort.InferenceSession(
        str(model_path), sess_options=options, providers=['CPUExecutionProvider'])
    _session_cache['tokenizer'] = Tokenizer.from_file(str(tokenizer_path))
    _session_cache['np'] = np


def _build_feed(session, pixel_values, input_ids, attention_mask):
    """Fill every required input we can provide; tolerate optional position_ids."""
    np = _session_cache['np']
    feed = {}
    for inp in session.get_inputs():
        if inp.name == 'pixel_values' and pixel_values is not None:
            feed['pixel_values'] = pixel_values
        elif inp.name == 'input_ids' and input_ids is not None:
            feed['input_ids'] = input_ids
        elif inp.name == 'attention_mask' and attention_mask is not None:
            feed['attention_mask'] = attention_mask
        elif inp.name == 'position_ids' and input_ids is not None:
            positions = np.arange(input_ids.shape[1], dtype=np.int64)
            feed['position_ids'] = np.tile(positions[None, :], (input_ids.shape[0], 1))
    return feed


def _preprocess(image_bytes: bytes):
    """CLIP preprocessing: RGB, resize shortest side 224, center crop, normalize."""
    np = _session_cache['np']
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert('RGB')
    width, height = image.size
    scale = IMAGE_SIZE / min(width, height)
    image = image.resize(
        (max(IMAGE_SIZE, round(width * scale)), max(IMAGE_SIZE, round(height * scale))),
        Image.BICUBIC)
    width, height = image.size
    left, top = (width - IMAGE_SIZE) // 2, (height - IMAGE_SIZE) // 2
    image = image.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    pixels = (pixels - CLIP_MEAN) / CLIP_STD
    return pixels.transpose(2, 0, 1)[None].astype(np.float32)


def _encode_texts(tokenizer, prompts) -> tuple:
    """Tokenize prompts and pad/truncate each to CLIP's 77-token budget."""
    np = _session_cache['np']
    pad_id = tokenizer.token_to_id('endoftext')
    all_ids, all_masks = [], []
    for prompt in prompts:
        encoded = tokenizer.encode(prompt)
        ids = list(encoded.ids)[:77]
        masks = [1] * len(ids)
        while len(ids) < 77:
            ids.append(pad_id if pad_id is not None else 0)
            masks.append(0)
        all_ids.append(ids)
        all_masks.append(masks)
    input_ids = np.asarray(all_ids, dtype=np.int64)
    attention_mask = np.asarray(all_masks, dtype=np.int64)
    return input_ids, attention_mask


def _score_photos_against_prompts(session, pixel_values, input_ids, attention_mask):
    """Run the graph and return similarity scores (higher = better match)."""
    np = _session_cache['np']

    if 'pixel_values' in {inp.name for inp in session.get_inputs()}:
        # Full CLIPModel graph: one call scores the image against every prompt.
        feed = _build_feed(session, pixel_values, input_ids, attention_mask)
        outputs = {o.name: v for o, v in zip(session.get_outputs(), session.run(None, feed))}
        if 'logits_per_image' in outputs:
            scores = np.asarray(outputs['logits_per_image'], dtype=np.float64)
        elif 'image_embeds' in outputs and 'text_embeds' in outputs:
            image_embeds = np.asarray(outputs['image_embeds'], dtype=np.float64)
            text_embeds = np.asarray(outputs['text_embeds'], dtype=np.float64)
            image_embeds /= np.linalg.norm(image_embeds, axis=-1, keepdims=True)
            text_embeds /= np.linalg.norm(text_embeds, axis=-1, keepdims=True)
            scores = image_embeds @ text_embeds.T * 100.0
        else:
            raise RuntimeError('Unsupported ONNX graph outputs: ' + ', '.join(outputs))
        if scores.ndim == 2:
            scores = scores[0]
        return scores  # one score per prompt for the single image

    raise RuntimeError('This ONNX graph has no pixel_values input')


def _softmax_percent(scores):
    np = _session_cache['np']
    exps = np.exp(scores - scores.max())
    return (exps / exps.sum()) * 100.0


def _matches_title(best_label: str, title: str) -> bool:
    lowered = (title or '').lower()
    for name, _prompt, _category, keywords in LABELS:
        if name == best_label:
            return any(keyword in lowered for keyword in keywords)
    return False


def analyze_photo(image_bytes: bytes, title: str = '', top_n: int = 3) -> dict | None:
    """What does this photo show, and does it agree with the title?

    Returns the result dict, or None when the photo/model fails (bad image,
    missing model files, anything unexpected). Reporting flow must never break.
    """
    result = _try_analyze(image_bytes, title, top_n)
    if result is not None:
        return result

    # One transparent retry: warm-up of the quantized session can fail once.
    try:
        if _session_cache['session'] is None:
            return None
        _session_cache['session'] = None
        return _try_analyze(image_bytes, title, top_n)
    except Exception:
        return None


def _try_analyze(image_bytes: bytes, title: str, top_n: int) -> dict | None:
    try:
        _warm_session()
        session, tokenizer = _session_cache['session'], _session_cache['tokenizer']
        prompts = [prompt for _name, prompt, _category, _kw in LABELS]
        pixel_values = _preprocess(image_bytes)
        input_ids, attention_mask = _encode_texts(tokenizer, prompts)
        scores = _score_photos_against_prompts(session, pixel_values, input_ids, attention_mask)
        percentages = _softmax_percent(scores)
        ranked = sorted(
            (percentages[index], LABELS[index][0], LABELS[index][2]) for index in range(len(LABELS)))
        ranked.reverse()
        best_percent, best_label, best_category = ranked[0]
        return {
            'best': best_label,
            'confidence': round(float(best_percent)),
            'matches_title': bool(_matches_title(best_label, title)),
            'suggested_category': best_category,
            'labels': [
                {'name': name, 'confidence': round(float(pct))}
                for pct, name, _category in ranked[:top_n]
            ],
        }
    except Exception:
        return None


def summarize(result: dict | None) -> str:
    """One-line human summary, ready for logs or the UI chip."""
    if not result:
        return 'AI analysis unavailable'
    verdict = 'matches title' if result.get('matches_title') else 'does not match title'
    return (f"AI sees: {result['best']} ({result['confidence']}%) - "
            f"{verdict} - suggested: {result['suggested_category']}")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('usage: python ai_detector.py <image_path> [title]')
        raise SystemExit(2)
    image_path = Path(sys.argv[1])
    issue_title = sys.argv[2] if len(sys.argv) > 2 else ''
    outcome = analyze_photo(image_path.read_bytes(), issue_title)
    if outcome is None:
        print('AI unavailable (analysis skipped)')
        raise SystemExit(1)
    print(json.dumps(outcome, indent=2))
    print(summarize(outcome))
