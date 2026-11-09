import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useMe } from "../api/hooks";
import { clearSession, wasExpired, useToken } from "../auth/session";
import { Brand } from "./Mark";

/** Signed-in screens: a top bar over one centred column. Signed-out visitors go to sign in. */
export function Shell() {
  const token = useToken();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const me = useMe();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 0);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Signed out (or the session expired): drop every cached answer of this account.
  useEffect(() => {
    if (!token) queryClient.clear();
  }, [token, queryClient]);

  if (!token) {
    const next = encodeURIComponent(location.pathname);
    const reason = wasExpired() ? "expired=1&" : "";
    return <Navigate to={`/sign-in?${reason}next=${next}`} replace />;
  }

  const signOut = () => {
    clearSession();
    queryClient.clear();
    navigate("/sign-in", { replace: true });
  };

  return (
    <>
      <header className={`topbar${scrolled ? " scrolled" : ""}`}>
        <div className="column">
          <Link to="/documents" aria-label="DocuMind, your documents">
            <Brand />
          </Link>
          <nav aria-label="Main">
            <NavLink to="/documents" end>
              Documents
            </NavLink>
          </nav>
          <div className="account">
            {me.data && <span className="who" title={me.data.email}>{me.data.email}</span>}
            <button type="button" className="link-btn" onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="column">
        <Outlet />
      </main>
    </>
  );
}
