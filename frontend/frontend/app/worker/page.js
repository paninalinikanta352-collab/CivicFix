"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import RiskBadge from "../../components/RiskBadge";
import { API_BASE, apiErrorMessage, getUser, getToken } from "../../lib/api";

// A worker moves an issue forward: reported -> in_progress -> resolved.
const WORKER_STATUSES = ["in_progress", "resolved"];

function DutyCard({ issue, token, onUpdated }) {
  const [status, setStatus] = useState(issue.status);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setStatus(issue.status);
    setNote("");
  }, [issue]);

  const changed = status !== issue.status || note.trim() !== "";
  const done = issue.status === "resolved";

  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await fetch(`${API_BASE}/api/issues/${issue.id}/status`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ status, note: note.trim() || null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not update this issue."));
      setNote("");
      onUpdated();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="report">
      {issue.photo_url ? (
        <img className="thumb" src={`${API_BASE}${issue.photo_url}`} alt={issue.title} />
      ) : (
        <div className="thumb-fallback">No photo</div>
      )}
      <h3>#{issue.id} · {issue.title}</h3>
      <div className="rowline">
        <span className={`pill ${issue.status}`}>{issue.status.replace("_", " ")}</span>
        <span className="chip">{issue.category}</span>
      </div>
      <div className="meta">
        {issue.latitude != null && issue.longitude != null
          ? `${issue.latitude.toFixed(5)}, ${issue.longitude.toFixed(5)} · `
          : ""}
        {new Date(issue.created_at).toLocaleString()}
        {issue.address ? ` · ${issue.address}` : ""}
      </div>
      <div className="desc">{issue.description}</div>
      <RiskBadge risk={issue.risk_percentage} />

      {done ? (
        <div className="success">✔ Resolved — kaam complete. Admin ko confirm dikh raha hai.</div>
      ) : (
        <div className="admin-controls">
          <label htmlFor={`st${issue.id}`}>Update status</label>
          <select
            id={`st${issue.id}`}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="select-inline"
          >
            {[...new Set([issue.status, ...WORKER_STATUSES])].map((s) => (
              <option key={s} value={s}>{s.replace("_", " ")}</option>
            ))}
          </select>
          <label htmlFor={`nt${issue.id}`}>Note (optional)</label>
          <input
            id={`nt${issue.id}`}
            className="w-auto"
            value={note}
            maxLength={1000}
            placeholder="e.g. Site visit done, material ordered"
            onChange={(e) => setNote(e.target.value)}
          />
          <button className="btn small primary" onClick={save} disabled={!changed || busy}>
            {busy ? "Saving..." : "Save update"}
          </button>
        </div>
      )}
      {err && <span className="hint danger-text">{err}</span>}
    </div>
  );
}

export default function WorkerPage() {
  const router = useRouter();
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [denied, setDenied] = useState(false);
  const [expired, setExpired] = useState(false);
  const [token, setToken] = useState("");

  const fetchAssignments = async (tk) => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/worker/assignments`, {
        headers: { Authorization: `Bearer ${tk}` },
      });
      if (res.status === 401) {
        setExpired(true);
        throw new Error("Your session expired. Please log in again.");
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(apiErrorMessage(data, "Could not load your assignments."));
      }
      setIssues(await res.json());
    } catch (e) {
      if (e.message !== "Your session expired. Please log in again.") setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const user = getUser();
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== "worker") {
      setDenied(true);
      setLoading(false);
      return;
    }
    const tk = getToken() ?? "";
    setToken(tk);
    fetchAssignments(tk);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (expired) {
    return (
      <main className="wrap">
        <div className="card empty">
          <h2>Session expired</h2>
          <p>Please <Link href="/login">log in</Link> again to see your assignments.</p>
        </div>
      </main>
    );
  }

  if (denied) {
    return (
      <main className="wrap">
        <div className="card empty">
          <div className="lock">🛠️</div>
          <h2>Workers only</h2>
          <p>
            This page is for municipal workers. If you reported an issue,
            check <Link href="/dashboard">My Issues</Link> — an admin assigns
            workers from the Admin Desk.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="wrap">
      <h2>My Duty</h2>
      <p className="hint">Issues assigned to you, riskiest first. Highest risk = pehle.</p>
      {error && <div className="error">⚠ {error}</div>}
      {loading && <p className="hint">Loading assignments…</p>}

      {!loading && !error && issues.length === 0 && (
        <div className="card empty">
          <h2>No assignments yet</h2>
          <p>Jab admin koi issue assign karega, wo yahan dikhega. Filhaal aaram.</p>
        </div>
      )}

      <div className="feed">
        {issues.map((issue) => (
          <DutyCard key={issue.id} issue={issue} token={token} onUpdated={() => fetchAssignments(token)} />
        ))}
      </div>
    </main>
  );
}
