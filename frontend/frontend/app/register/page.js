"use client";

import Link from "next/link";
import { useState } from "react";
import { API_BASE, apiErrorMessage, saveAuth } from "../../lib/api";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (name.trim().length < 2) {
      setError("Name needs at least 2 characters.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email like name@example.com (with @ and a dot).");
      return;
    }
    if (password.length < 8) {
      setError("Password needs at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), email: email.trim(), password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Registration failed."));
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
        <h2>Create your account</h2>
        {error && <div className="error">⚠ {error}</div>}
        <form onSubmit={onSubmit}>
          <label htmlFor="name">Full name</label>
          <input id="name" placeholder="e.g. Priya Sharma" value={name}
            onChange={(e) => setName(e.target.value)} autoComplete="name" />
          <label htmlFor="email">Email</label>
          <input id="email" type="email" placeholder="you@example.com" value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <label htmlFor="password">Password</label>
          <div className="pass-row">
            <input id="password" type={showPass ? "text" : "password"} placeholder="At least 8 characters" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" style={{ marginBottom: 0 }} />
            <button type="button" className="btn small" onClick={() => setShowPass(!showPass)}>
              {showPass ? "Hide" : "Show"}
            </button>
          </div>
          <p className="hint">Use 8+ characters. New accounts are regular users — worker and admin accounts are created by the city desk.</p>
          <button className="btn primary full" type="submit" disabled={loading}>
            {loading ? "Creating..." : "Create Account"}
          </button>
        </form>
        <p className="hint">Already registered? <Link href="/login">Login instead →</Link></p>
      </section>
    </main>
  );
}
