import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { API, lease, scan, server } from "../test/server";
import { renderApp } from "../test/render";
import { originalName, summarise } from "./DocumentsPage";

describe("Documents screen", () => {
  it("lists documents newest first, with the title row's finding and each failure's reason", async () => {
    renderApp("/documents");

    expect(await screen.findByRole("heading", { level: 1, name: "Documents" })).toBeInTheDocument();
    expect(await screen.findByText("1 ready to ask · 1 failed")).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]!).getByRole("link", { name: scan.title })).toBeInTheDocument(); // uploaded later
    expect(within(rows[0]!).getByText(scan.error_message!)).toBeInTheDocument();
    expect(within(rows[0]!).getByText("Failed")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("Ready")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("12 pages")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("flat-lease-2026.pdf")).toBeInTheDocument();
  });

  it("shows the upload area as the first step when there are no documents", async () => {
    server.use(http.get(`${API}/documents/`, () => HttpResponse.json({ documents: [], total: 0 })));
    renderApp("/documents");

    expect(await screen.findByText("No documents yet. Upload a PDF to start asking questions.")).toBeInTheDocument();
    expect(screen.getByText("Drop a PDF here")).toBeInTheDocument();
  });

  it("refuses a file that is not a PDF without sending it", async () => {
    let uploads = 0;
    server.use(http.post(`${API}/documents/upload`, () => (uploads++, HttpResponse.json(lease, { status: 201 }))));
    renderApp("/documents");
    await screen.findByText("1 ready to ask · 1 failed");

    await userEvent.upload(screen.getByTestId("file-input"), new File(["hello"], "notes.txt", { type: "text/plain" }), { applyAccept: false });

    expect(await screen.findByRole("alert")).toHaveTextContent('"notes.txt" is not a PDF.');
    expect(uploads).toBe(0);
  });

  it("uploads a PDF as multipart form data", async () => {
    let contentType = "";
    let filePart: FormDataEntryValue | null = null;
    server.use(
      http.post(`${API}/documents/upload`, async ({ request }) => {
        contentType = request.headers.get("content-type") ?? "";
        filePart = (await request.formData()).get("file");
        return HttpResponse.json({ ...lease, id: 9, title: "Insurance", status: "pending" }, { status: 201 });
      }),
    );
    renderApp("/documents");
    await screen.findByText("1 ready to ask · 1 failed");

    await userEvent.upload(screen.getByTestId("file-input"), new File(["%PDF-1.4"], "insurance.pdf", { type: "application/pdf" }));

    // (jsdom's File loses its name when Node's fetch serialises it, so the
    // name is not checked here; the end-to-end test uploads a real file.)
    await waitFor(() => expect(filePart).not.toBeNull());
    expect(contentType).toMatch(/^multipart\/form-data; boundary=/);
  });

  it("deletes only after confirming, naming the document", async () => {
    let deleted: string | null = null;
    server.use(
      http.delete(`${API}/documents/:id`, ({ params }) => {
        deleted = String(params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderApp("/documents");
    await screen.findByText("1 ready to ask · 1 failed");

    await userEvent.click(screen.getByRole("button", { name: `Delete ${lease.title}` }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading")).toHaveTextContent(`Delete "${lease.title}"?`);
    expect(deleted).toBeNull();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete document" }));

    await waitFor(() => expect(deleted).toBe(String(lease.id)));
  });
});

describe("helpers", () => {
  it("shows the name the user uploaded, without the stored UUID prefix", () => {
    expect(originalName(lease.filename)).toBe("flat-lease-2026.pdf");
  });

  it("summarises what can be asked about and what needs attention", () => {
    expect(summarise([lease, { ...scan, status: "processing" }])).toBe("1 ready to ask · 1 being read");
    expect(summarise([{ ...lease, status: "pending" }])).toBe("None ready to ask yet · 1 being read");
  });
});
