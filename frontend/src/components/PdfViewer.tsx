type Props = {
  url: string | null;
  page: number;
  pageCount: number | null | undefined;
  cited: boolean;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
};

/**
 * The document itself, at the page a citation points to, in the browser's own
 * PDF viewer. The iframe is keyed by page because changing only the #page
 * fragment does not move every browser's viewer.
 */
export function PdfViewer({ url, page, pageCount, cited, loading, error, onRetry }: Props) {
  const src = url ? `${url}#page=${page}` : null;
  return (
    <section className="panel viewer" aria-label="Document viewer">
      <header>
        <h2 aria-live="polite">
          <span className={cited ? "on-page" : undefined}>Page {page}</span>
          {pageCount ? (
            <>
              {" "}
              <span className="muted">of {pageCount}</span>
            </>
          ) : null}
        </h2>
        {src && (
          <a className="link-btn" href={src} target="_blank" rel="noopener">
            Open in a new tab
          </a>
        )}
      </header>
      {loading && <div className="state">Loading the PDF…</div>}
      {error && (
        <div className="state" role="alert">
          <p>
            Couldn't load the PDF.{" "}
            <button type="button" className="link-btn" onClick={onRetry}>
              Retry
            </button>
          </p>
        </div>
      )}
      {src && !loading && !error && <iframe key={page} src={src} title={`PDF, page ${page}`} />}
    </section>
  );
}
