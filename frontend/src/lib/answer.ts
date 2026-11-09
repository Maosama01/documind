// Reading an answer: its page citations, its extractive-fallback label, and
// what its grounded flag means. Pure functions, so they are unit-tested.

export const NOT_FOUND = "Not found in the document.";

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "cite"; text: string; pages: number[] };

// Mirrors the backend's parser (llm_service._CITATION): [p.3], [p. 3], [p.3, p.5]
const CITATION = /\[\s*(p\.\s*\d+(?:\s*,\s*p\.\s*\d+)*)\s*\]/g;
const PAGE = /p\.\s*(\d+)/g;

/** The answer as text and citation segments, in order. */
export function splitAnswer(answer: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of answer.matchAll(CITATION)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ kind: "text", text: answer.slice(last, start) });
    const pages = [...(match[1] ?? "").matchAll(PAGE)].map((m) => Number(m[1]));
    segments.push({ kind: "cite", text: match[0], pages });
    last = start + match[0].length;
  }
  if (last < answer.length) segments.push({ kind: "text", text: answer.slice(last) });
  return segments;
}

// The backend prefixes extractive answers with "[Extractive answer: ...]".
const EXTRACTIVE_LABEL = /^\[Extractive answer:[^\]]*\]\s*/;

/** Split the extractive fallback's label off the answer, so it can be shown as a note. */
export function separateLabel(answer: string): { extractive: boolean; body: string } {
  const match = answer.match(EXTRACTIVE_LABEL);
  return match ? { extractive: true, body: answer.slice(match[0].length) } : { extractive: false, body: answer };
}

/** "none:extractive" → "No LLM: extractive fallback"; "gemini:gemini-3.8-flash" → "gemini-3.8-flash". */
export function providerLabel(provider: string): string {
  if (provider.startsWith("none")) return "No LLM: extractive fallback";
  const [, model] = provider.split(":", 2);
  return model || provider;
}

export type PageKind = "cited" | "retrieved" | "missing" | "unread";

/**
 * One mark per page of the document: cited (and retrieved), retrieved only,
 * cited but never retrieved (what makes an answer not grounded), or unread.
 * A cited page past the document's last page is still shown, as missing.
 */
export function pageMarks(pageCount: number, retrieved: number[], cited: number[]): { page: number; kind: PageKind }[] {
  const retrievedSet = new Set(retrieved);
  const citedSet = new Set(cited);
  const last = Math.max(pageCount, ...cited, 0);
  return Array.from({ length: last }, (_, i) => {
    const page = i + 1;
    if (citedSet.has(page)) return { page, kind: retrievedSet.has(page) ? "cited" : "missing" };
    return { page, kind: retrievedSet.has(page) ? "retrieved" : "unread" };
  });
}

function pageList(pages: number[]): string {
  const labels = pages.map((page) => `p. ${page}`);
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}

export type Verdict = { tone: "positive" | "negative" | "neutral"; label: string; detail: string };

/** What the grounded flag means for this answer, in words. */
export function verdict(answer: string, grounded: boolean, cited: number[], retrieved: number[]): Verdict {
  if (answer.trim() === NOT_FOUND) {
    return { tone: "neutral", label: "Not found", detail: "The passages read don't answer this question." };
  }
  if (grounded) {
    return {
      tone: "positive",
      label: "Grounded",
      detail: `${cited.length === 1 ? "The cited page was" : "Every cited page was"} among the passages read (${pageList(cited)}).`,
    };
  }
  if (cited.length === 0) {
    return { tone: "negative", label: "Not grounded", detail: "The answer cites no page." };
  }
  const retrievedSet = new Set(retrieved);
  const missing = cited.filter((page) => !retrievedSet.has(page));
  return {
    tone: "negative",
    label: "Not grounded",
    detail: `Cites ${pageList(missing)}, which ${missing.length === 1 ? "was" : "were"} not among the passages read.`,
  };
}
