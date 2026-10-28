"use client";

import Link from "next/link";
import { useState } from "react";
import { API_BASE, apiErrorMessage, saveAuth } from "../../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email like name@example.com.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Login failed. Check your details."));
      saveAuth(data.access_token, data.user);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="wrap">
      <section className="card form-card auth-card">
        <h2>Welcome back</h2>
        {error && <div className="error">⚠ {error}</div>}
        <form onSubmit={onSubmit}>
          <label htmlFor="email">Email</label>
          <input id="email" type="email" placeholder="you@example.com" value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <label htmlFor="password">Password</label>
          <div className="pass-row">
            <input id="password" type={showPass ? "text" : "password"} placeholder="Your password" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" style={{ marginBottom: 0 }} />
            <button type="button" className="btn small" onClick={() => setShowPass(!showPass)}>
              {showPass ? "Hide" : "Show"}
            </button>
          </div>
          <button className="btn primary full" type="submit" disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>
        <p className="hint">New to CivicFix? <Link href="/register">Create an account →</Link></p>
      </section>
    </main>
  );
}
