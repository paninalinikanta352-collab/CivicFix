"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import RiskBadge from "../../components/RiskBadge";
import { API_BASE, apiErrorMessage, getUser, getToken, parseAiAnalysis } from "../../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    const user = getUser();
    if (!user) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/issues?limit=100`, {
          headers: { Authorization: `Bearer ${getToken() ?? ""}` },
        });
        if (res.status === 401) {
          setSessionExpired(true);
          throw new Error("Your session expired. Please log in again.");
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(apiErrorMessage(data, "Could not load issues."));
        }
        const data = await res.json();
        const mine = (data.items || []).filter((r) => r.reporter_id === Number(user.id));
        setIssues(mine);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  if (sessionExpired) {
    return (
      <main className="wrap">
        <div className="card empty">
          <h2>Session expired</h2>
          <p>Please <Link href="/login">log in</Link> again to see your issues.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="wrap">
      <h2>My Reported Issues</h2>
      {error && <div className="error">⚠ {error}</div>}
      {loading && <p className="hint">Loading issues…</p>}

      {!loading && !error && issues.length === 0 && (
        <div className="card empty">
          <h2>Nothing reported yet</h2>
          <p>Spotted a pothole, broken light, or open wire? Report your first issue.</p>
          <Link href="/report" className="btn primary">📸 Report a Problem</Link>
        </div>
      )}

      <div className="feed">
        {issues.map((r) => {
          const ai = parseAiAnalysis(r.ai_analysis);
          return (
            <div className="report" key={r.id}>
              {r.photo_url ? (
                <img className="thumb" src={`${API_BASE}${r.photo_url}`} alt={r.title} />
              ) : (
                <div className="thumb-fallback">No photo</div>
              )}
              <h3>{r.title}</h3>
              <div className="rowline">
                <span className={`pill ${r.status}`}>{r.status.replace("_", " ")}</span>
                <span className="chip">{r.category}</span>
                {ai && (
                  <span className="chip" title={`AI suggested category: ${ai.suggested_category}${ai.matches_title ? " · title se match" : ""}`}>
                    🤖 {ai.best} {ai.confidence}%
                  </span>
                )}
                {r.assigned_worker_id != null && <span className="chip">Worker assigned</span>}
              </div>
              <div className="meta">
                {r.latitude != null && r.longitude != null
                  ? `${r.latitude.toFixed(5)}, ${r.longitude.toFixed(5)} · `
                  : ""}
                {new Date(r.created_at).toLocaleString()}
                {r.address ? ` · ${r.address}` : ""}
              </div>
              <div className="desc">{r.description}</div>
              <RiskBadge risk={r.risk_percentage} />
            </div>
          );
        })}
      </div>
    </main>
  );
}
