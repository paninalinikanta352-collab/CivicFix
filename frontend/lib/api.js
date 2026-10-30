// Single place for the FastAPI contract. All client pages import from here.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export const TOKEN_KEY = "civicfix_token";
export const USER_KEY = "civicfix_user";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function saveAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

// Merge a patch (e.g. {verified: true}) into the stored user without
// touching the token.
export function updateUser(patch) {
  if (typeof window === "undefined") return;
  const user = getUser();
  if (!user) return;
  localStorage.setItem(USER_KEY, JSON.stringify({ ...user, ...patch }));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// FastAPI error bodies: {"detail": "msg"} or 422 {"detail": [{loc, msg}, ...]}
export function apiErrorMessage(data, fallback = "Something went wrong. Please try again.") {
  const detail = data?.detail;
  if (!detail) return data?.error || fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`)
      .join("; ");
  }
  if (detail.msg) return detail.msg;
  return fallback;
}

// issues.ai_analysis is a JSON string created by the backend AI detector, or null.
// Returns {"best","confidence","matches_title","suggested_category","labels"} or null.
export function parseAiAnalysis(raw) {
  if (typeof raw !== "string" || !raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.best && typeof parsed.confidence === "number") return parsed;
  } catch {
    /* malformed or old data - treat as no analysis */
  }
  return null;
}
