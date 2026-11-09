import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import type { Document, QueryResult, User } from "../api/client";

// A fake API with the same shapes as the real one (the types come from its
// OpenAPI schema). Tests override handlers with server.use(...).
export const API = `${window.location.origin}/api`;

export const me: User = {
  id: 1,
  email: "asha.verma@documind-tests.dev",
  full_name: "Asha Verma",
  is_active: true,
  created_at: "2026-11-02T09:15:00Z",
};

export const lease: Document = {
  id: 7,
  title: "Flat Lease 2026",
  filename: "1b4e28ba-2fa1-11d2-883f-0016d3cca427_flat-lease-2026.pdf",
  status: "processed",
  error_message: null,
  page_count: 12,
  content_preview: "Tenancy agreement",
  created_at: "2026-11-08T14:05:00Z",
};

export const scan: Document = {
  id: 8,
  title: "Gas Safety Certificate",
  filename: "6fa459ea-ee8a-3ca4-894e-db77e160355e_gas-safety.pdf",
  status: "failed",
  error_message: "No text could be extracted. Scanned PDFs need OCR, which is not supported, and pages with fewer than 20 words are skipped.",
  page_count: 2,
  content_preview: "",
  created_at: "2026-11-09T08:40:00Z",
};

export const groundedAnswer: QueryResult = {
  question: "When is rent due?",
  answer: "Rent is due on the 1st of each month [p.3]. A late fee applies after 5 days [p.3, p.4].",
  cited_pages: [3, 4],
  grounded: true,
  provider: "gemini:gemini-3.8-flash",
  sources: [
    { rank: 1, page_number: 3, chunk_index: 11, content: "The Tenant shall pay the rent on the first day of each calendar month." },
    { rank: 2, page_number: 4, chunk_index: 14, content: "If rent is more than five days late, a late fee of £30 is payable." },
    { rank: 3, page_number: 9, chunk_index: 40, content: "The deposit is held in a government-approved scheme." },
  ],
};

export const handlers = [
  http.get(`${API}/auth/me`, () => HttpResponse.json(me)),
  http.get(`${API}/documents/`, () => HttpResponse.json({ documents: [lease, scan], total: 2 })),
  http.get(`${API}/documents/:id`, ({ params }) => {
    const doc = [lease, scan].find((d) => d.id === Number(params.id));
    return doc ? HttpResponse.json(doc) : HttpResponse.json({ detail: "Document not found" }, { status: 404 });
  }),
  http.get(`${API}/documents/:id/file`, () =>
    new HttpResponse("%PDF-1.4 test", { headers: { "Content-Type": "application/pdf" } }),
  ),
  http.post(`${API}/query/`, () => HttpResponse.json(groundedAnswer)),
];

export const server = setupServer(...handlers);
