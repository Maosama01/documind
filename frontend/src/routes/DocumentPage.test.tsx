import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { API, groundedAnswer, lease, scan, server } from "../test/server";
import { renderApp } from "../test/render";

async function ask(question: string) {
  await userEvent.type(await screen.findByLabelText("Your question"), question);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
}

describe("Document screen", () => {
  it("answers with clickable page citations, the verdict and the passages read", async () => {
    let sent: unknown = null;
    server.use(
      http.post(`${API}/query/`, async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(groundedAnswer);
      }),
    );
    renderApp(`/documents/${lease.id}`);

    await ask("When is rent due?");

    expect(await screen.findByRole("heading", { name: "When is rent due?" })).toBeInTheDocument();
    expect(sent).toEqual({ document_id: lease.id, question: "When is rent due?", max_results: 5 });
    expect(screen.getAllByRole("button", { name: "Show page 3" })).toHaveLength(2);
    expect(screen.getByText("Grounded")).toBeInTheDocument();
    expect(screen.getByText("Every cited page was among the passages read (p. 3 and p. 4).")).toBeInTheDocument();
    expect(screen.getByText("3 passages read, most similar first")).toBeInTheDocument();
    expect(screen.getByText("Answered by gemini-3.8-flash")).toBeInTheDocument();
  });

  it("opens the cited page in the viewer beside the answer", async () => {
    renderApp(`/documents/${lease.id}`);
    await ask("When is rent due?");
    await screen.findByText("Grounded");

    // the first cited page opens by itself; another citation moves the viewer
    expect(screen.getByRole("heading", { name: "Page 3 of 12" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show page 4" }));

    expect(screen.getByRole("heading", { name: "Page 4 of 12" })).toBeInTheDocument();
    expect(screen.getByTitle("PDF, page 4").getAttribute("src")).toMatch(/^blob:.+#page=4$/);
  });

  it("marks a cited page that was never read, and says the answer is not grounded", async () => {
    server.use(
      http.post(`${API}/query/`, () =>
        HttpResponse.json({ ...groundedAnswer, answer: "Rent is due monthly [p.3]. Pets are allowed [p.11].", cited_pages: [3, 11], grounded: false }),
      ),
    );
    renderApp(`/documents/${lease.id}`);
    await ask("Can I keep a cat?");

    expect(await screen.findByText("Not grounded")).toBeInTheDocument();
    expect(screen.getByText("Cites p. 11, which was not among the passages read.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show page 11 (cited, never read)" })).toHaveClass("missing");
  });

  it("labels the extractive fallback instead of passing it off as a written answer", async () => {
    server.use(
      http.post(`${API}/query/`, () =>
        HttpResponse.json({
          ...groundedAnswer,
          answer: "[Extractive answer: no LLM is configured (LLM_PROVIDER=none). These are the sentences.] The Tenant shall pay the rent on the first day of each calendar month. [p.3]",
          cited_pages: [3],
          provider: "none:extractive",
        }),
      ),
    );
    renderApp(`/documents/${lease.id}`);
    await ask("When is rent due?");

    expect(await screen.findByText("No LLM is configured, so these are the document's own sentences closest to the question.")).toBeInTheDocument();
    expect(screen.getByText("Answered by No LLM: extractive fallback")).toBeInTheDocument();
    expect(screen.queryByText(/\[Extractive answer/)).not.toBeInTheDocument();
  });

  it("shows a failed answer inside its card and can ask again", async () => {
    let calls = 0;
    server.use(
      http.post(`${API}/query/`, () =>
        ++calls === 1
          ? HttpResponse.json({ detail: "Answer generation failed: gemini returned HTTP 503" }, { status: 502 })
          : HttpResponse.json(groundedAnswer),
      ),
    );
    renderApp(`/documents/${lease.id}`);
    await ask("When is rent due?");

    const alert = await screen.findByText(/Couldn't get an answer/);
    expect(alert).toHaveTextContent("Couldn't get an answer: Answer generation failed: gemini returned HTTP 503");
    await userEvent.click(within(alert).getByRole("button", { name: "Ask again" }));

    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("explains a document that failed to process instead of offering questions", async () => {
    renderApp(`/documents/${scan.id}`);

    expect(await screen.findByRole("heading", { name: "This document couldn't be read" })).toBeInTheDocument();
    expect(screen.getByText(scan.error_message!)).toBeInTheDocument();
    expect(screen.queryByLabelText("Your question")).not.toBeInTheDocument();
  });

  it("says when a document does not exist or is not yours", async () => {
    renderApp("/documents/999");

    expect(await screen.findByRole("heading", { name: "Document not found" })).toBeInTheDocument();
  });

  it("keeps this tab's questions across a reload of the screen", async () => {
    const first = renderApp(`/documents/${lease.id}`);
    await ask("When is rent due?");
    await screen.findByText("Grounded");
    first.unmount();

    renderApp(`/documents/${lease.id}`);

    expect(await screen.findByRole("heading", { name: "When is rent due?" })).toBeInTheDocument();
  });
});
