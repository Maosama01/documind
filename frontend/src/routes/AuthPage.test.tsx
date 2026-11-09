import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { getToken } from "../auth/session";
import { API, server } from "../test/server";
import { renderApp } from "../test/render";

async function fill(email: string, password: string) {
  await userEvent.type(await screen.findByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
}

describe("Sign in", () => {
  it("sends signed-out visitors to sign in, then back where they were going", async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json({ access_token: "token-123", token_type: "bearer" })));
    const { router } = renderApp("/documents/7", { signedIn: false });

    await screen.findByRole("heading", { name: "Sign in" });
    await fill("asha.verma@documind-tests.dev", "a long password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/documents/7"));
    expect(getToken()).toBe("token-123");
  });

  it("says plainly when the email and password don't match", async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json({ detail: "Incorrect email or password" }, { status: 401 })));
    renderApp("/sign-in", { signedIn: false });

    await fill("asha.verma@documind-tests.dev", "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don't match an account.");
    expect(getToken()).toBeNull();
  });

  it("never returns to another site after sign-in", async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json({ access_token: "t", token_type: "bearer" })));
    const { router } = renderApp("/sign-in?next=//evil.example", { signedIn: false });

    await fill("asha.verma@documind-tests.dev", "a long password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/documents"));
  });

  it("creates an account, then signs in with it", async () => {
    let created: unknown = null;
    server.use(
      http.post(`${API}/auth/signup`, async ({ request }) => {
        created = await request.json();
        return HttpResponse.json({}, { status: 201 });
      }),
      http.post(`${API}/auth/login`, () => HttpResponse.json({ access_token: "new-token", token_type: "bearer" })),
    );
    renderApp("/sign-up", { signedIn: false });

    await userEvent.type(await screen.findByLabelText("Full name"), "Asha Verma");
    await fill("asha.verma@documind-tests.dev", "a long password");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(getToken()).toBe("new-token"));
    expect(created).toEqual({ email: "asha.verma@documind-tests.dev", full_name: "Asha Verma", password: "a long password" });
  });

  it("returns to sign in, with a reason, when the session has expired", async () => {
    server.use(http.get(`${API}/documents/`, () => HttpResponse.json({ detail: "Could not validate credentials" }, { status: 401 })));
    const { router } = renderApp("/documents");

    await waitFor(() => expect(router.state.location.pathname).toBe("/sign-in"));
    expect(await screen.findByText("Your session ended after 30 minutes. Sign in again to continue.")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });
});
