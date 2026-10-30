"use client";

import { useEffect, useState } from "react";
import { API_BASE, apiErrorMessage, updateUser } from "../lib/api";

/**
 * Shared email-verification card.
 *
 * - Register flow: the backend already sent a code (maybe a dev-mode code
 *   passed as initialDevCode) so autoRequest stays off.
 * - Dashboard banner: autoRequest=true sends a fresh code when the banner
 *   mounts, with a "Skip for now" escape hatch.
 */
export default function VerifyEmailCard({
  email,
  initialDevCode = "",
  autoRequest = false,
  onVerified,
  onDismiss,
}) {
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState(initialDevCode);
  const [sent, setSent] = useState(Boolean(initialDevCode));
  const [info, setInfo] = useState(
    initialDevCode
      ? `A 6-digit code was just sent to ${email}. Enter it below.`
      : `We'll email a 6-digit code to ${email}. Hit "Send code" to get it.`
  );
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useState(initialDevCode ? 60 : 0);

  useEffect(() => {
    if (resendIn <= 0) return undefined;
    const timer = setInterval(() => setResendIn((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(timer);
  }, [resendIn]);

  const sendRequest = async () => {
    setError("");
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/verify-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not send the code."));
      setDevCode(data.otp || "");
      setSent(true);
      setResendIn(60);
      setInfo(
        data.otp
          ? "Dev mode (SMTP not configured) — your code:"
          : `Code sent to ${email}. Check your inbox (and spam).`
      );
    } catch (err) {
      const msg = err.message || "";
      if (/already verified/i.test(msg)) {
        setDone(true);
        updateUser({ verified: true });
        onVerified?.();
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (autoRequest) sendRequest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRequest]);

  const onConfirm = async (e) => {
    e.preventDefault();
    setError("");
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/verify-confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(data, "Could not verify the code."));
      setDone(true);
      updateUser({ verified: true });
      onVerified?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" data-testid="verify-email-card">
      <h2>Verify your email</h2>
      {info && <p className="hint">{info}</p>}
      {devCode && <p className="hint">Dev code: <b>{devCode}</b></p>}
      {error && <div className="error">⚠ {error}</div>}
      {done ? (
        <p className="success">✔ Email verified — thanks for confirming!</p>
      ) : (
        <form onSubmit={onConfirm}>
          <label htmlFor="otp-code">6-digit code</label>
          <div className="otp-row">
            <input
              id="otp-code"
              className="otp-input"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder="000000"
            />
            <button
              type="submit"
              className="btn primary"
              disabled={busy}
            >
              {busy ? "Checking..." : "Verify"}
            </button>
          </div>
          <div className="otp-row">
            <button
              type="button"
              className="btn small"
              onClick={sendRequest}
              disabled={busy || resendIn > 0}
            >
              {!sent ? "Send code" : resendIn > 0 ? `Resend code (${resendIn}s)` : "Resend code"}
            </button>
            {onDismiss && (
              <button type="button" className="btn small ghost" onClick={onDismiss}>
                Skip for now
              </button>
            )}
          </div>
          <p className="hint">Codes expire in 10 minutes. Resend is limited to once a minute.</p>
        </form>
      )}
    </div>
  );
}
