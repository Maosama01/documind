import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { api, errorMessage } from "../api/client";
import { setToken, useToken } from "../auth/session";
import { Brand } from "../components/Mark";

type Mode = "sign-in" | "sign-up";

const COPY: Record<Mode, { title: string; lead: string; action: string; busy: string }> = {
  "sign-in": {
    title: "Sign in",
    lead: "Ask questions about your PDFs and see the pages each answer comes from.",
    action: "Sign in",
    busy: "Signing in…",
  },
  "sign-up": {
    title: "Create your account",
    lead: "Your documents are visible to you only.",
    action: "Create account",
    busy: "Creating account…",
  },
};

/** Only same-app paths may be returned to after sign-in (never another site). */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/documents";
}

export function AuthPage({ mode }: { mode: Mode }) {
  const copy = COPY[mode];
  const token = useToken();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (token) return <Navigate to={next} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "sign-up") {
        const created = await api.POST("/auth/signup", { body: { email, full_name: fullName, password } });
        if (created.error) throw new Error(errorMessage(created.error));
      }
      const login = await api.POST("/auth/login", { body: { email, password } });
      if (login.error || !login.data) {
        throw new Error(login.response.status === 401 ? "That email and password don't match an account." : errorMessage(login.error));
      }
      setToken(login.data.access_token);
      navigate(next, { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth-card">
        <Brand />
        <h1>{copy.title}</h1>
        <p className="lead">{copy.lead}</p>
        {params.get("expired") && mode === "sign-in" && (
          <p className="notice" role="status">Your session ended after 30 minutes. Sign in again to continue.</p>
        )}
        <form onSubmit={submit} noValidate={false}>
          {mode === "sign-up" && (
            <div className="field">
              <label htmlFor="full-name">Full name</label>
              <input id="full-name" className="input" autoComplete="name" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? copy.busy : copy.action}
          </button>
        </form>
        <p className="switch">
          {mode === "sign-in" ? (
            <>
              New to DocuMind? <Link to={`/sign-up${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`}>Create an account</Link>
            </>
          ) : (
            <>
              Already have an account? <Link to="/sign-in">Sign in</Link>
            </>
          )}
        </p>
      </div>
    </main>
  );
}
