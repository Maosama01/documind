import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router";
import { isInProgress, useAsk, useDocument, usePdfUrl } from "../api/hooks";
import { AnswerTurn } from "../components/AnswerTurn";
import { PdfViewer } from "../components/PdfViewer";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatPages } from "../lib/format";
import { useHistory, type Turn } from "../lib/history";
import { useMediaQuery } from "../lib/useMediaQuery";

const MAX_RESULTS = [3, 5, 8, 10];

export function DocumentPage() {
  const id = Number(useParams().id);
  if (!Number.isInteger(id) || id < 1) return <Missing />;
  return <DocumentScreen key={id} id={id} />;
}

function DocumentScreen({ id }: { id: number }) {
  const document = useDocument(id);
  const ready = document.data?.status === "processed";
  const wide = useMediaQuery("(min-width: 961px)");
  const pdf = usePdfUrl(id, ready);
  const { turns, add, update } = useHistory(id);
  const ask = useAsk();
  const [question, setQuestion] = useState("");
  const [maxResults, setMaxResults] = useState(5);
  const [shownPage, setShownPage] = useState(1);

  const latestCited = turns.find((t) => t.status === "done")?.result?.cited_pages ?? [];

  if (document.isLoading) return <Loading />;
  if (document.isError || !document.data) {
    return document.error?.message === "Document not found" ? <Missing /> : <LoadError onRetry={() => document.refetch()} />;
  }
  const doc = document.data;

  function send(text: string, results: number, existing?: Turn) {
    const turn: Turn = existing
      ? { ...existing, status: "pending", error: undefined }
      : { id: crypto.randomUUID(), question: text, maxResults: results, askedAt: new Date().toISOString(), status: "pending" };
    if (existing) update(turn.id, turn);
    else add(turn);
    ask.mutate(
      { documentId: id, question: text, maxResults: results },
      {
        onSuccess: (result) => {
          update(turn.id, { status: "done", result, askedAt: new Date().toISOString() });
          const first = result.cited_pages[0];
          if (first) setShownPage(first);
        },
        onError: (error) => update(turn.id, { status: "error", error: error.message }),
      },
    );
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = question.trim();
    if (!text || ask.isPending) return;
    send(text, maxResults);
    setQuestion("");
  }

  // Enter asks; Shift+Enter starts a new line.
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  // On a wide screen the page opens in the viewer beside the answer; on a
  // phone, in the browser's own PDF viewer in a new tab.
  function showPage(page: number) {
    setShownPage(page);
    if (!wide && pdf.url) window.open(`${pdf.url}#page=${page}`, "_blank", "noopener");
  }

  return (
    <>
      <Link to="/documents" className="crumb">
        ← Documents
      </Link>
      <div className="title-row">
        <div>
          <h1>{doc.title}</h1>
          <p className="sub">
            {formatPages(doc.page_count)} · uploaded {formatDateTime(doc.created_at)}
          </p>
        </div>
        <div className="actions">
          {!ready && <StatusPill status={doc.status} />}
          {ready && pdf.url && (
            <a className="btn phone-only" href={pdf.url} target="_blank" rel="noopener">
              Open PDF
            </a>
          )}
        </div>
      </div>

      {!ready ? (
        <NotReady status={doc.status} reason={doc.error_message} />
      ) : (
        <div className="doc-grid">
          <div className="doc-main">
            <form className="panel" onSubmit={submit} aria-labelledby="ask-title">
              <header>
                <h2 id="ask-title">Ask about this document</h2>
                <span className="meta">Your questions stay in this tab; DocuMind doesn't save them</span>
              </header>
              <div className="field">
                <label htmlFor="question" className="visually-hidden">
                  Your question
                </label>
                <textarea
                  id="question"
                  className="input"
                  rows={2}
                  maxLength={2000}
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={onKeyDown}
                  aria-describedby="ask-hint"
                />
                <span id="ask-hint" className="hint">
                  Answers come only from this document and cite the pages they use. Enter to ask, Shift+Enter for a new line.
                </span>
              </div>
              <div className="ask-row">
                <label>
                  Passages to read
                  <select className="input num" value={maxResults} onChange={(event) => setMaxResults(Number(event.target.value))}>
                    {MAX_RESULTS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="submit" className="btn primary" disabled={!question.trim() || ask.isPending}>
                  {ask.isPending ? "Asking…" : "Ask"}
                </button>
              </div>
            </form>

            {turns.length === 0 ? (
              <div className="empty">
                <p>Ask a question to get an answer that cites the pages it comes from.</p>
                <p>Click a citation to see that page beside the answer.</p>
              </div>
            ) : (
              <section aria-label="Answers" aria-live="polite" style={{ display: "grid", gap: "var(--gap)" }}>
                {turns.map((turn, index) => (
                  <AnswerTurn
                    key={turn.id}
                    turn={turn}
                    pageCount={doc.page_count ?? 0}
                    shownPage={wide ? shownPage : null}
                    latest={index === 0}
                    onShowPage={showPage}
                    onRetry={(t) => send(t.question, t.maxResults, t)}
                  />
                ))}
              </section>
            )}
          </div>
          <aside className="doc-pane">
            <PdfViewer
              url={pdf.url}
              page={shownPage}
              pageCount={doc.page_count}
              cited={latestCited.includes(shownPage)}
              loading={pdf.isLoading}
              error={Boolean(pdf.error)}
              onRetry={() => pdf.refetch()}
            />
          </aside>
        </div>
      )}
    </>
  );
}

function NotReady({ status, reason }: { status: string; reason?: string | null }) {
  if (isInProgress(status)) {
    return (
      <div className="panel" role="status">
        <h2>Reading this document</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          DocuMind is extracting its text and preparing its passages. This page updates by itself when it's ready.
        </p>
      </div>
    );
  }
  return (
    <div className="panel" role="alert">
      <h2>This document couldn't be read</h2>
      <p style={{ marginTop: 6 }}>{reason ?? "The reason was not recorded."}</p>
      <p className="muted" style={{ marginTop: 6 }}>
        Delete it from <Link to="/documents" className="link-btn">your documents</Link> and upload it again, or try another file.
      </p>
    </div>
  );
}

function Missing() {
  return (
    <div className="panel" role="alert" style={{ marginTop: 24 }}>
      <h1 style={{ fontSize: "var(--fs-title)", fontWeight: 500 }}>Document not found</h1>
      <p className="muted" style={{ marginTop: 6 }}>
        It may have been deleted, or it belongs to another account. <Link to="/documents" className="link-btn">Back to your documents</Link>
      </p>
    </div>
  );
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="panel" role="alert" style={{ marginTop: 24 }}>
      <h1 style={{ fontSize: "var(--fs-title)", fontWeight: 500 }}>Couldn't load this document</h1>
      <p className="muted" style={{ marginTop: 6 }}>
        <button type="button" className="link-btn" onClick={onRetry}>
          Retry
        </button>
      </p>
    </div>
  );
}

function Loading() {
  return (
    <div role="status" aria-label="Loading the document" style={{ paddingTop: 28 }}>
      <div className="skeleton" style={{ width: 240, height: 24 }} />
      <div className="skeleton" style={{ width: 180, height: 14, marginTop: 10 }} />
    </div>
  );
}
