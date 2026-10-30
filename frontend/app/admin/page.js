"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import RiskBadge from "../../components/RiskBadge";
import { API_BASE, apiErrorMessage, getUser, getToken, parseAiAnalysis } from "../../lib/api";

const STATUSES = ["reported", "assigned", "in_progress", "resolved", "rejected"];

function IssueRow({ issue, workers, token, onUpdated }) {
  const ai = parseAiAnalysis(issue.ai_analysis);
  const [workerId, setWorkerId] = useState(issue.assigned_worker_id ?? "");
  const [status, setStatus] = useState(issue.status);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setWorkerId(issue.assigned_worker_id ?? "");
    setStatus(issue.status);
  }, [issue]);

  const changed =
    status !== issue.status ||
    (workerId !== "" && workerId !== String(issue.assigned_worker_id ?? ""));

  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      if (workerId !== "" && workerId !== String(issue.assigned_worker_id ?? "")) {
        const res = await fetch(`${API_BASE}/api/admin/issues/${issue.id}/assign`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ worker_id: Number(workerId) }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(apiErrorMessage(data, "Could not assign worker."));
      }
      if (status !== issue.status) {
        const res = await fetch(`${API_BASE}/api/issues/${issue.id}/status`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(apiErrorMessage(data, "Could not update status."));
      }
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
        {ai && (
          <span className="chip" title={`AI suggested category: ${ai.suggested_category}${ai.matches_title ? " · title se match" : ""}`}>
            🤖 {ai.best} {ai.confidence}%
          </span>
        )}
        {issue.assigned_worker_id != null && <span className="chip">Worker #{issue.assigned_worker_id}</span>}
      </div>
      <div className="meta">
        Risk {issue.risk_percentage}% · {new Date(issue.created_at).toLocaleString()}
        {issue.address ? ` · ${issue.address}` : ""}
      </div>
      <div className="desc">{issue.description}</div>
      <RiskBadge risk={issue.risk_percentage} />
      <div className="admin-controls">
        <label htmlFor={`w${issue.id}`} className="hint">Worker</label>
        <select id={`w${issue.id}`} value={workerId === "" ? "" : String(workerId)}
          onChange={(e) => setWorkerId(e.target.value)} className="select-inline">
          <option value="">— unassigned —</option>
          {workers.map((w) => (
            <option key={w.id} value={String(w.id)}>{w.name}</option>
          ))}
        </select>
        <label htmlFor={`s${issue.id}`} className="hint">Status</label>
        <select id={`s${issue.id}`} value={status} onChange={(e) => setStatus(e.target.value)} className="select-inline">
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace("_", " ")}</option>
          ))}
        </select>
        <button className="btn small primary" onClick={save} disabled={!changed || busy}>
          {busy ? "Saving..." : "Save changes"}
        </button>
        {err && <span className="hint danger-text">{err}</span>}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [denied, setDenied] = useState(false);
  const [issues, setIssues] = useState([]);
  const [workers, setWorkers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [wForm, setWForm] = useState({ name: "", email: "", password: "" });
  const [wErr, setWErr] = useState("");
  const [wBusy, setWBusy] = useState(false);
  const [token, setToken] = useState("");

  const load = async (tk = token) => {
    setError("");
    setLoading(true);
    try {
      const headers = { Authorization: `Bearer ${tk}` };
      const [i, s, w] = await Promise.all([
        fetch(`${API_BASE}/api/admin/issues?limit=500`, { headers }),
        fetch(`${API_BASE}/api/admin/stats`, { headers }),
        fetch(`${API_BASE}/api/admin/workers`, { headers }),
      ]);
      if (i.status === 401 || i.status === 403) {
        setDenied(true);
        throw new Error("Admins only. Log in with an admin account.");
      }
      if (!i.ok || !s.ok || !w.ok) {
        const data = await i.json().catch(() => ({}));
        throw new Error(apiErrorMessage(data, "Could not load admin data."));
      }
      setIssues((await i.json()).items || []);
      setStats(await s.json());
      setWorkers(await w.json());
    } catch (e) {
      if (e.message !== "Admins only. Log in with an admin account.") setError(e.message);
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
    const tk = getToken() ?? "";
    setToken(tk);
    if (user.role === "admin") load(tk);
    else setDenied(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createWorker = async (e) => {
    e.preventDefault();
    setWErr("");
    if (wForm.name.trim().length < 2 || wForm.password.length < 8) {
      setWErr("Name needs 2+ characters, password needs 8+.");
      return;
    }
    setWBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/workers`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ name: wForm.name.trim(), email: wForm.email.trim(), password: wForm.password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not create worker."));
      setWForm({ name: "", email: "", password: "" });
      load();
    } catch (err) {
      setWErr(err.message);
    } finally {
      setWBusy(false);
    }
  };

  const shown = filter === "all" ? issues : issues.filter((r) => r.status === filter);
  const openCount = stats?.issues_by_status
    ? ["reported", "assigned", "in_progress"].reduce((n, k) => n + (stats.issues_by_status[k] || 0), 0)
    : null;

  if (denied) {
    return (
      <main className="wrap">
        <div className="card empty">
          <div className="lock">🔒</div>
          <h2>Admin access only</h2>
          <p>
            This page is for the city desk. Log in with an admin account —
            regular users can use <Link href="/dashboard">My Issues</Link>.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="wrap">
      <h2>Admin Desk</h2>
      {error && <div className="error">⚠ {error}</div>}
      {loading && <p className="hint">Loading admin data…</p>}

      {stats && (
        <div className="stats-grid">
          <div className="stat"><div className="stat-num">{stats.total_issues}</div><span>Total issues</span></div>
          <div className="stat"><div className="stat-num warn">{openCount}</div><span>Open</span></div>
          <div className="stat"><div className="stat-num good">{stats.issues_by_status?.resolved || 0}</div><span>Resolved</span></div>
          <div className="stat"><div className="stat-num">{stats.average_risk_percentage}%</div><span>Avg risk</span></div>
          <div className="stat"><div className="stat-num">{workers.length}</div><span>Workers</span></div>
        </div>
      )}

      <section className="card">
        <h2>Add a Worker</h2>
        {wErr && <div className="error">⚠ {wErr}</div>}
        <form onSubmit={createWorker} className="rowline">
          <input placeholder="Full name" value={wForm.name} className="w-auto"
            onChange={(e) => setWForm({ ...wForm, name: e.target.value })} />
          <input placeholder="Email" type="email" value={wForm.email} className="w-auto"
            onChange={(e) => setWForm({ ...wForm, email: e.target.value })} />
          <input placeholder="Password (8+ chars)" type="password" value={wForm.password} className="w-auto"
            onChange={(e) => setWForm({ ...wForm, password: e.target.value })} />
          <button className="btn primary" type="submit" disabled={wBusy}>
            {wBusy ? "Creating..." : "Create Worker"}
          </button>
        </form>
        <p className="hint">Workers can only update issues assigned to them.</p>
      </section>

      <div className="filters">
        <button className={`chip-btn ${filter === "all" ? "on" : ""}`} onClick={() => setFilter("all")}>All</button>
        {STATUSES.map((s) => (
          <button key={s} className={`chip-btn ${filter === s ? "on" : ""}`} onClick={() => setFilter(s)}>
            {s.replace("_", " ")}
          </button>
        ))}
      </div>

      {!loading && !error && shown.length === 0 && (
        <div className="card empty">
          <h2>No issues here</h2>
          <p>Nothing has been reported yet — new reports appear here with their risk score.</p>
        </div>
      )}

      <div className="feed">
        {shown.map((issue) => (
          <IssueRow key={issue.id} issue={issue} workers={workers} token={token} onUpdated={() => load()} />
        ))}
      </div>
    </main>
  );
}
