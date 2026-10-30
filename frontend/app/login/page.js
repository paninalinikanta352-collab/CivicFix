"use client";

import Link from "next/link";
import { useState } from "react";
import { API_BASE, apiErrorMessage, saveAuth } from "../../lib/api";

export default function LoginPage() {
  const [mode, setMode] = useState("login"); // login | forgot | reset
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  // forgot flow state
  const [devOtp, setDevOtp] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onLogin = async (e) => {
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

  const onForgot = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email like name@example.com.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not start the reset. Try again."));
      setDevOtp(data.otp || "");
      setNotice(
        data.otp
          ? "Dev mode (SMTP not configured) — your code:"
          : "Reset code sent. Check your inbox (and spam), then enter it below."
      );
      setMode("reset");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const onReset = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code from the email.");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password needs at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code, new_password: newPassword }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not reset the password."));
      setNotice(data.message || "Password updated. Sign in with your new password.");
      setCode("");
      setNewPassword("");
      setPassword("");
      setDevOtp("");
      setMode("login");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (mode === "forgot" || mode === "reset") {
    return (
      <main className="wrap">
        <section className="card form-card auth-card">
          {mode === "forgot" ? (
            <>
              <h2>Forgot password</h2>
              {error && <div className="error">⚠ {error}</div>}
              <form onSubmit={onForgot}>
                <label htmlFor="email">Email</label>
                <input id="email" type="email" placeholder="you@example.com" value={email}
                  onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
                <button className="btn primary full" type="submit" disabled={loading}>
                  {loading ? "Sending..." : "Email me a reset code"}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2>Reset password</h2>
              {notice && <div className="success">{notice}{devOtp && <> <b>{devOtp}</b></>}</div>}
              {error && <div className="error">⚠ {error}</div>}
              <form onSubmit={onReset}>
                <label htmlFor="code">6-digit code</label>
                <input id="code" className="otp-input" inputMode="numeric" autoComplete="one-time-code"
                  maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="000000" />
                <label htmlFor="new-password">New password</label>
                <input id="new-password" type="password" placeholder="At least 8 characters" value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
                <button className="btn primary full" type="submit" disabled={loading}>
                  {loading ? "Updating..." : "Set new password"}
                </button>
              </form>
              <p className="hint">
                Didn't get it?{" "}
                <button type="button" className="btn small" onClick={() => setMode("forgot")}>
                  Back
                </button>
              </p>
            </>
          )}
          <p className="hint"><Link href="#" onClick={(e) => { e.preventDefault(); setMode("login"); setError(""); setDevOtp(""); setNotice(""); }}>← Back to login</Link></p>
        </section>
      </main>
    );
  }

  return (
    <main className="wrap">
      <section className="card form-card auth-card">
        <h2>Welcome back</h2>
        {notice && <div className="success">✔ {notice}</div>}
        {error && <div className="error">⚠ {error}</div>}
        <form onSubmit={onLogin}>
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
          <p className="hint"><Link href="#" onClick={(e) => { e.preventDefault(); setMode("forgot"); setError(""); }}>Forgot password?</Link></p>
          <button className="btn primary full" type="submit" disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>
        <p className="hint">New to CivicFix? <Link href="/register">Create an account →</Link></p>
      </section>
    </main>
  );
}
