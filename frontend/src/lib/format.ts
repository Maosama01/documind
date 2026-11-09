const dateTime = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** "9 Nov 2026, 16:20" in the viewer's time zone. */
export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** "1 page", "12 pages"; a page count not known yet is a dash. */
export function formatPages(count: number | null | undefined): string {
  if (count === null || count === undefined) return "—";
  return `${count.toLocaleString("en-GB")} ${count === 1 ? "page" : "pages"}`;
}

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // same limit as the API

/** Why a file cannot be uploaded, checked before sending it; null if it can. */
export function uploadProblem(file: File): string | null {
  if (!file.name.endsWith(".pdf")) return `"${file.name}" is not a PDF. DocuMind reads .pdf files only.`;
  if (file.size > MAX_UPLOAD_BYTES) return `"${file.name}" is larger than 10 MB.`;
  return null;
}
