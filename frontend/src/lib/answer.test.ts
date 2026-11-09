import { describe, expect, it } from "vitest";
import { NOT_FOUND, pageMarks, providerLabel, separateLabel, splitAnswer, verdict } from "./answer";

describe("splitAnswer", () => {
  it("separates text from citations in every form the backend accepts", () => {
    expect(splitAnswer("Due monthly [p.3]. Fee [p. 4] and [p.3, p.5].")).toEqual([
      { kind: "text", text: "Due monthly " },
      { kind: "cite", text: "[p.3]", pages: [3] },
      { kind: "text", text: ". Fee " },
      { kind: "cite", text: "[p. 4]", pages: [4] },
      { kind: "text", text: " and " },
      { kind: "cite", text: "[p.3, p.5]", pages: [3, 5] },
      { kind: "text", text: "." },
    ]);
  });

  it("leaves forms the backend does not count as plain text", () => {
    expect(splitAnswer("See page 3, (p.3) and [p.3-5].")).toEqual([{ kind: "text", text: "See page 3, (p.3) and [p.3-5]." }]);
  });
});

describe("separateLabel", () => {
  it("takes the extractive fallback's label off the answer", () => {
    const answer = "[Extractive answer: no LLM is configured (LLM_PROVIDER=none). These are the sentences.] Rent is due [p.3]";
    expect(separateLabel(answer)).toEqual({ extractive: true, body: "Rent is due [p.3]" });
  });

  it("leaves other answers untouched", () => {
    expect(separateLabel("Rent is due [p.3]")).toEqual({ extractive: false, body: "Rent is due [p.3]" });
  });
});

describe("providerLabel", () => {
  it.each([
    ["none:extractive", "No LLM: extractive fallback"],
    ["gemini:gemini-3.8-flash", "gemini-3.8-flash"],
    ["anthropic:claude-opus-5-5", "claude-opus-5-5"],
  ])("%s → %s", (provider, label) => expect(providerLabel(provider)).toBe(label));
});

describe("pageMarks", () => {
  it("marks each page by what the answer did with it", () => {
    expect(pageMarks(5, [1, 2, 4], [2, 5]).map((m) => m.kind)).toEqual(["retrieved", "cited", "unread", "retrieved", "missing"]);
  });

  it("still shows a cited page past the document's last page, as missing", () => {
    expect(pageMarks(2, [1], [9]).at(-1)).toEqual({ page: 9, kind: "missing" });
  });
});

describe("verdict", () => {
  it("explains a grounded answer", () => {
    expect(verdict("Due [p.3] [p.4]", true, [3, 4], [3, 4, 9])).toEqual({
      tone: "positive",
      label: "Grounded",
      detail: "Every cited page was among the passages read (p. 3 and p. 4).",
    });
  });

  it("names the cited pages that were never read", () => {
    expect(verdict("Due [p.3] [p.9]", false, [3, 9], [3, 4])).toMatchObject({
      tone: "negative",
      detail: "Cites p. 9, which was not among the passages read.",
    });
  });

  it("calls out an answer that cites nothing", () => {
    expect(verdict("Rent is due monthly.", false, [], [3])).toMatchObject({ tone: "negative", detail: "The answer cites no page." });
  });

  it("treats the not-found reply as its own outcome", () => {
    expect(verdict(NOT_FOUND, true, [], [3])).toMatchObject({ tone: "neutral", label: "Not found" });
  });
});
