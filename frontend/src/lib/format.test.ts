import { describe, expect, it } from "vitest";
import { formatPages, uploadProblem } from "./format";

describe("uploadProblem", () => {
  it("accepts a PDF up to 10 MB", () => {
    expect(uploadProblem(new File([new Uint8Array(10 * 1024 * 1024)], "lease.pdf"))).toBeNull();
  });

  it("rejects other files and larger PDFs before uploading, with the same rules as the API", () => {
    expect(uploadProblem(new File(["x"], "notes.docx"))).toBe('"notes.docx" is not a PDF. DocuMind reads .pdf files only.');
    expect(uploadProblem(new File([new Uint8Array(10 * 1024 * 1024 + 1)], "big.pdf"))).toBe('"big.pdf" is larger than 10 MB.');
  });
});

describe("formatPages", () => {
  it("counts pages and shows a dash when the count is unknown", () => {
    expect(formatPages(1)).toBe("1 page");
    expect(formatPages(1200)).toBe("1,200 pages");
    expect(formatPages(null)).toBe("—");
  });
});
