import { useState } from "react";
import type { Source } from "../api/client";
import { providerLabel, separateLabel, splitAnswer, verdict } from "../lib/answer";
import { formatDateTime } from "../lib/format";
import type { Turn } from "../lib/history";
import { PageStrip } from "./PageStrip";

type Props = {
  turn: Turn;
  pageCount: number;
  shownPage: number | null;
  latest: boolean;
  onShowPage: (page: number) => void;
  onRetry: (turn: Turn) => void;
};

export function AnswerTurn({ turn, pageCount, shownPage, latest, onShowPage, onRetry }: Props) {
  return (
    <article className="panel turn" aria-busy={turn.status === "pending"}>
      <h3>{turn.question}</h3>
      {turn.status === "pending" && (
        <div role="status" aria-label="Reading the passages">
          <p className="answer pending">Reading the passages…</p>
          <div className="skeleton" style={{ width: "92%", marginTop: 10 }} />
          <div className="skeleton" style={{ width: "70%" }} />
        </div>
      )}
      {turn.status === "error" && (
        <div className="form-error" role="alert" style={{ marginTop: 0 }}>
          Couldn't get an answer: {turn.error}{" "}
          <button type="button" className="link-btn" onClick={() => onRetry(turn)}>
            Ask again
          </button>
        </div>
      )}
      {turn.status === "done" && turn.result && (
        <Result turn={turn} pageCount={pageCount} shownPage={shownPage} latest={latest} onShowPage={onShowPage} />
      )}
    </article>
  );
}

function Result({ turn, pageCount, shownPage, latest, onShowPage }: Omit<Props, "onRetry">) {
  const result = turn.result!;
  const { extractive, body } = separateLabel(result.answer);
  const retrieved = result.sources.map((s) => s.page_number).filter((p): p is number => p !== null && p !== undefined);
  const outcome = verdict(body, result.grounded, result.cited_pages, retrieved);
  const tone = { positive: "pos", negative: "neg", neutral: "" }[outcome.tone];

  return (
    <>
      {extractive && (
        <p className="note">No LLM is configured, so these are the document's own sentences closest to the question.</p>
      )}
      <p className="answer">
        {splitAnswer(body).map((segment, i) =>
          segment.kind === "text" ? (
            <span key={i}>{segment.text}</span>
          ) : (
            segment.pages.map((page, j) => (
              <button
                key={`${i}-${j}`}
                type="button"
                className="cite"
                aria-pressed={shownPage === page}
                aria-label={`Show page ${page}`}
                onClick={() => onShowPage(page)}
              >
                {j === 0 ? "[" : ""}p.&nbsp;{page}
                {j === segment.pages.length - 1 ? "]" : ","}
              </button>
            ))
          ),
        )}
      </p>
      <div className="verdict">
        <span className={`pill ${tone}`.trim()}>{outcome.label}</span>
        <span className="muted">{outcome.detail}</span>
        <span className="caveat">This checks page numbers only, not whether a passage supports the answer.</span>
      </div>
      {pageCount > 0 && (
        <PageStrip pageCount={pageCount} retrieved={retrieved} cited={result.cited_pages} onShowPage={onShowPage} />
      )}
      <Sources sources={result.sources} cited={result.cited_pages} open={latest} onShowPage={onShowPage} />
      <footer>
        <span>Answered by {providerLabel(result.provider)}</span>
        <span className="num">{formatDateTime(turn.askedAt)}</span>
      </footer>
    </>
  );
}

function Sources({ sources, cited, open, onShowPage }: { sources: Source[]; cited: number[]; open: boolean; onShowPage: (page: number) => void }) {
  const citedSet = new Set(cited);
  return (
    <details className="sources" open={open}>
      <summary>
        {sources.length} {sources.length === 1 ? "passage" : "passages"} read, most similar first
      </summary>
      <ol>
        {sources.map((source) => (
          <SourceRow key={`${source.rank}-${source.chunk_index}`} source={source} cited={citedSet.has(source.page_number ?? -1)} onShowPage={onShowPage} />
        ))}
      </ol>
    </details>
  );
}

function SourceRow({ source, cited, onShowPage }: { source: Source; cited: boolean; onShowPage: (page: number) => void }) {
  const [expanded, setExpanded] = useState(false);
  const long = source.content.length > 280;
  const page = source.page_number;
  return (
    <li className={`source${cited ? " cited" : ""}`}>
      {page ? (
        <button type="button" className="page" onClick={() => onShowPage(page)} aria-label={`Show page ${page}${cited ? " (cited)" : ""}`}>
          p.&nbsp;{page}
        </button>
      ) : (
        <span className="page">—</span>
      )}
      <div>
        <p className={long && !expanded ? "clamped" : undefined}>{source.content}</p>
        {long && (
          <button type="button" className="link-btn" style={{ marginTop: 4 }} onClick={() => setExpanded((e) => !e)}>
            {expanded ? "Show less" : "Show the whole passage"}
          </button>
        )}
      </div>
    </li>
  );
}
