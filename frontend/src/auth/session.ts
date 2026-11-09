import { useSyncExternalStore } from "react";

// The sign-in token lives in sessionStorage: it survives a reload, and closing
// the tab signs you out. Any script on the page can read it, so the app must
// not run untrusted scripts (React escapes everything it renders; the app
// never sets raw HTML). Moving it to an httpOnly cookie would close that gap
// and needs backend changes.
const TOKEN_KEY = "documind.token";
const PREFIX = "documind.";

const listeners = new Set<() => void>();
// Set when the API rejects the token, so the redirect to sign in can say why.
let expired = false;
const notify = () => listeners.forEach((listener) => listener());

function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null; // storage blocked (private mode, sandboxed frame): act signed out
  }
}

export function getToken(): string | null {
  return read(TOKEN_KEY);
}

export function setToken(token: string): void {
  expired = false;
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // storage blocked: the token cannot be kept, so the user stays signed out
  }
  notify();
}

/** Sign out: forget the token and everything this tab kept (question history). */
export function clearSession(): void {
  try {
    for (const key of Object.keys(window.sessionStorage)) {
      if (key.startsWith(PREFIX)) window.sessionStorage.removeItem(key);
    }
  } catch {
    // nothing stored
  }
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The API rejected the token: sign this tab out and remember why. */
export function expireSession(): void {
  expired = true;
  clearSession();
}

/** True after the API rejected the token, until the next sign-in. Safe to read during render. */
export function wasExpired(): boolean {
  return expired;
}

export function useToken(): string | null {
  return useSyncExternalStore(subscribe, getToken, () => null);
}

/**
 * Development only: open any page with ?dev-token=<jwt> to sign this tab in.
 * The screenshot tool used to check the design cannot fill in the sign-in
 * form, so it signs in this way. import.meta.env.DEV is false in production
 * builds, so Vite removes this branch from them.
 */
export function adoptDevToken(): void {
  if (!import.meta.env.DEV) return;
  const url = new URL(window.location.href);
  const token = url.searchParams.get("dev-token");
  if (!token) return;
  setToken(token);
  url.searchParams.delete("dev-token");
  window.history.replaceState(null, "", url.toString());
}
