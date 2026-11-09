import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";
import { expireSession, getToken } from "../auth/session";

export type Document = components["schemas"]["DocumentResponse"];
export type QueryResult = components["schemas"]["QueryResponse"];
export type Source = components["schemas"]["SourceResponse"];
export type User = components["schemas"]["UserResponse"];

const auth: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ request, response }) {
    // A 401 from sign-in itself means a wrong password, not an expired session.
    const isAuthCall = new URL(request.url).pathname.startsWith("/api/auth/");
    if (response.status === 401 && !isAuthCall) expireSession();
    return response;
  },
};

// Every call goes to /api on this origin; the dev server and nginx forward it
// to the API (see vite.config.ts and nginx.conf).
// fetch is looked up on every call, not captured once: anything that wraps
// fetch after this module loads (a test's mock server) still sees the calls.
export const api = createClient<paths>({
  baseUrl: `${window.location.origin}/api`,
  fetch: (input: Request) => globalThis.fetch(input),
});
api.use(auth);

/** The API's error as one sentence: FastAPI sends {"detail": "..."} or a list of field errors. */
export function errorMessage(error: unknown, fallback = "Something went wrong. Try again."): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first.msg === "string") return first.msg.replace(/^Value error, /, "");
    }
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/** Throw the API's error message, so TanStack Query treats it as a failed request. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    throw new Error(errorMessage(result.error, `Request failed (${result.response.status}).`));
  }
  return result.data;
}
