import { pageMarks, type PageKind } from "../lib/answer";

const KIND_LABEL: Record<Exclude<PageKind, "unread">, string> = {
  cited: "Cited",
  retrieved: "Read, not cited",
  missing: "Cited, never read",
};

type Props = {
  pageCount: number;
  retrieved: number[];
  cited: number[];
  onShowPage: (page: number) => void;
};

/**
 * Every page of the document as one cell, marked by what this answer did with
 * it. A red cell is a cited page that was never among the passages read: the
 * reason an answer is not grounded, made visible.
 */
export function PageStrip({ pageCount, retrieved, cited, onShowPage }: Props) {
  const marks = pageMarks(pageCount, retrieved, cited);
  const present = (["cited", "retrieved", "missing"] as const).filter((kind) => marks.some((m) => m.kind === kind));

  return (
    <div className="strip">
      <div className="strip-head">
        <h4>Pages</h4>
        <ul className="legend" aria-label="Key">
          {present.map((kind) => (
            <li key={kind}>
              <span className={`cell ${kind}`} aria-hidden="true" />
              {KIND_LABEL[kind]}
            </li>
          ))}
        </ul>
      </div>
      <div className="cells">
        {marks.map(({ page, kind }) =>
          kind === "unread" ? (
            <span key={page} className="cell" title={`p. ${page}`} aria-hidden="true" />
          ) : (
            <button
              key={page}
              type="button"
              className={`cell ${kind}`}
              title={`p. ${page}: ${KIND_LABEL[kind]}`}
              aria-label={`Show page ${page} (${KIND_LABEL[kind].toLowerCase()})`}
              onClick={() => onShowPage(page)}
            />
          ),
        )}
      </div>
    </div>
  );
}
