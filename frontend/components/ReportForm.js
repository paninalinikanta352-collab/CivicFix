"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { API_BASE, apiErrorMessage, getToken, parseAiAnalysis } from "../lib/api";

const MAX_MB = 8;
const ACCEPT = { "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp" };

const CATEGORIES = [
  { value: "roads", label: "Roads and potholes" },
  { value: "water", label: "Water" },
  { value: "electricity", label: "Electricity" },
  { value: "cleanliness", label: "Cleanliness" },
  { value: "other", label: "Other" },
];
const categoryLabel = (value) => CATEGORIES.find((c) => c.value === value)?.label || value;

export default function ReportForm() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState(""); // empty = citizen must pick; AI only suggests
  const [address, setAddress] = useState("");
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiSuggestion, setAiSuggestion] = useState(null); // {category, confidence} | {unavailable: true}
  const [suggesting, setSuggesting] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const pickFile = (f) => {
    setError("");
    if (!f) return;
    if (!ACCEPT[f.type]) {
      setError("Please choose a JPEG, PNG, or WebP photo.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`Photo must be ${MAX_MB} MB or smaller.`);
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    setImage(f);
    setPreview(URL.createObjectURL(f));
  };

  const getLocation = () => {
    setError("");
    if (!navigator.geolocation) {
      setError("Your browser does not support location sharing.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
      },
      () => setError("Could not get your location. Allow location access and try again."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const suggestCategory = async () => {
    setError("");
    setAiResult(null);
    const token = getToken();
    if (!token) {
      setError("Please log in first.");
      return;
    }
    if (title.trim().length < 4 || description.trim().length < 8) {
      setError("Type the title (4+ chars) and description (8+ chars) first, so AI has something to read.");
      return;
    }
    setSuggesting(true);
    try {
      const res = await fetch(`${API_BASE}/api/issues/category-suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: title.trim(), description: description.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "AI suggestion failed. Pick a category yourself."));
      if (data.category) {
        setCategory(data.category);
        setAiSuggestion({ category: data.category, confidence: data.confidence });
      } else {
        setAiSuggestion({ unavailable: true });
      }
    } catch (err) {
      setAiSuggestion({ unavailable: true });
      setError(err.message || "AI suggestion failed. Pick a category yourself.");
    } finally {
      setSuggesting(false);
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setDone(false);
    setAiResult(null);
    const token = getToken();
    if (!token) {
      setError("Please log in first to report an issue.");
      return;
    }
    if (title.trim().length < 4) {
      setError("Title needs at least 4 characters.");
      return;
    }
    if (description.trim().length < 8) {
      setError("Description needs at least 8 characters.");
      return;
    }
    if (!image) {
      setError("Add a photo of the problem.");
      return;
    }
    if (!category) {
      setError("Pick a category — or ask AI for a suggestion above.");
      return;
    }
    if (lat === null || lng === null) {
      setError("Click 'Use Live Location' first.");
      return;
    }

    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("title", title.trim());
      fd.append("description", description.trim());
      fd.append("category", category);
      fd.append("lat", String(lat));
      fd.append("lng", String(lng));
      if (address.trim()) fd.append("address", address.trim());
      fd.append("image", image);

      const res = await fetch(`${API_BASE}/api/issues`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not submit your report."));
      setAiResult(parseAiAnalysis(data.ai_analysis));
      setDone(true);
      setTitle("");
      setDescription("");
      setCategory("");
      setAddress("");
      setLat(null);
      setLng(null);
      setAiSuggestion(null);
      setSuggesting(false);
      if (preview) URL.revokeObjectURL(preview);
      setImage(null);
      setPreview("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err.message || "Could not submit your report. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="card form-card">
      <h2>Report an Issue</h2>
      {error && <div className="error">⚠ {error}</div>}
      {done && (
        <div className="success">
          ✔ Report submitted! <Link href="/dashboard">Track it in My Issues →</Link>
          {aiResult && (
            <span className="chip" title={`AI suggested category: ${aiResult.suggested_category}`}>
              🤖 AI: {aiResult.best} {aiResult.confidence}% · {aiResult.matches_title ? "title se match ✔" : "title se match nahi ⚠"}
            </span>
          )}
        </div>
      )}

      <div className="step-label">◇ Step 1 · Photo</div>
      <label className="hint" htmlFor="imageInput">Under {MAX_MB} MB — JPG, PNG, or WebP. A clear, well-lit photo gets fixed faster.</label>
      <input
        ref={fileRef}
        id="imageInput"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => pickFile(e.target.files?.[0])}
      />
      {preview && <img className="preview" src={preview} alt="Preview of the photo you selected" />}

      <div className="step-label">◇ Step 2 · What is the problem</div>
      <label htmlFor="title">Short title</label>
      <input id="title" value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)}
        placeholder="e.g. Broken streetlight near Gate 2" />
      <label htmlFor="description">Describe the problem</label>
      <textarea id="description" value={description} maxLength={5000} onChange={(e) => setDescription(e.target.value)}
        placeholder="What you saw, since when, and why it is dangerous... (mention words like 'accident', 'fire', 'leak', 'school' so risk scoring picks them up)" />
      <label htmlFor="category">Category</label>
      <div className="rowline">
        <select id="category" value={category} onChange={(e) => setCategory(e.target.value)} style={{ flex: "1 1 220px" }}>
          <option value="" disabled>Choose a category…</option>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <button
          type="button"
          className="btn"
          onClick={suggestCategory}
          disabled={suggesting || submitting}
          title="AI reads your title + description and suggests a category - you always decide"
        >
          {suggesting ? "🤖 Thinking..." : "🤖 Ask AI"}
        </button>
      </div>
      {aiSuggestion?.unavailable && (
        <p className="hint">🤖 AI suggestion unavailable right now — pick a category yourself.</p>
      )}
      {aiSuggestion?.category && (
        <p className="hint">
          🤖 AI suggests: <b>{categoryLabel(aiSuggestion.category)}</b>
          {aiSuggestion.confidence != null && ` (${Math.round(aiSuggestion.confidence * 100)}%)`} — preselected above; you can change it.
        </p>
      )}
      <label htmlFor="address">Street or landmark (optional)</label>
      <input id="address" value={address} maxLength={500} onChange={(e) => setAddress(e.target.value)}
        placeholder="e.g. Near Gate 2, behind the school" />

      <div className="step-label">◇ Step 3 · Pin the spot</div>
      <div className="rowline">
        <button type="button" className="btn" onClick={getLocation} disabled={submitting}>📍 Use Live Location</button>
        <span className="loc-chip">{lat === null || lng === null ? "Location not set" : `${lat.toFixed(5)}, ${lng.toFixed(5)}`}</span>
      </div>

      <button type="submit" className="btn primary full" disabled={submitting}>
        {submitting ? "Submitting..." : "Submit Issue"}
      </button>
      <p className="hint center">You can track your report any time from My Issues.</p>
    </form>
  );
}
