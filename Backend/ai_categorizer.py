"""LLM-based category auto-detection for CivicFix reports.

When a citizen submits a report without a confident category (the form
defaults to 'other'), this calls the configured Gemini model with a strict
JSON schema and asks it to map the text to one of the five supported
categories. Every failure path returns None so reporting still works with
no API key, no network, or a malformed response - never blocks a report.

Env:
  CIVICFIX_GEMINI_API_KEY - Google AI Studio key (required to enable)
  CIVICFIX_GEMINI_MODEL   - optional, defaults to gemini-2.0-flash
  CIVICFIX_LLM_ENABLED    - optional, set to 'false' to force-disable
"""
from __future__ import annotations

import os

REQUEST_TIMEOUT_SECONDS = 8

VALID_CATEGORIES = ('roads', 'water', 'electricity', 'cleanliness', 'other')

PROMPT = (
    "You classify Indian municipal civic complaints into exactly one category.\n"
    "Categories:\n"
    "- roads: broken/damaged roads, potholes, footpath issues, accident-prone roads\n"
    "- water: water supply, leaks, waterlogging, flooding, sewage overflow, drainage\n"
    "- electricity: streetlights, power poles, outages, exposed/dangling wires\n"
    "- cleanliness: garbage, litter, dumps, open waste, public toilet issues\n"
    "- other: anything that fits none of the above (e.g. stray animals, noise, safety)\n"
    "Answer only with the JSON object requested."
)


def detect_category(title: str, description: str):
    """Return {'category', 'confidence', 'detail'} or None on any failure.

    Never raises: callers treat None as 'leave the category as-is'.
    """
    api_key = os.getenv('CIVICFIX_GEMINI_API_KEY')
    if not api_key or os.getenv('CIVICFIX_LLM_ENABLED', 'true').strip().lower() == 'false':
        return None
    if not title.strip() and not description.strip():
        return None
    try:
        import requests

        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{os.getenv("CIVICFIX_GEMINI_MODEL", "gemini-2.0-flash").strip()}:generateContent',
            params={'key': api_key},
            json={
                'systemInstruction': {'parts': [{'text': PROMPT}]},
                'contents': [{'role': 'user', 'parts': [{'text': f'Title: {title}\nDescription: {description}'}]}],
                'generationConfig': {
                    'temperature': 0.1,
                    'responseMimeType': 'application/json',
                    'responseSchema': {
                        'type': 'OBJECT',
                        'properties': {
                            'category': {'type': 'STRING', 'enum': list(VALID_CATEGORIES)},
                            'confidence': {'type': 'NUMBER'},
                        },
                        'required': ['category'],
                    },
                },
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload['candidates'][0]['content']['parts'][0]['text']
        import json

        parsed = json.loads(text)
        category = str(parsed.get('category', '')).strip().lower()
        if category not in VALID_CATEGORIES:
            return None
        confidence = parsed.get('confidence')
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = None
        return {'category': category, 'confidence': confidence, 'detail': 'gemini'}
    except Exception:
        return None
