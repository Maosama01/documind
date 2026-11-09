import { useMemo, useRef, useState, type DragEvent } from "react";
import { Link } from "react-router";
import type { Document } from "../api/client";
import { isInProgress, useDeleteDocument, useDocuments, useUpload } from "../api/hooks";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatPages, uploadProblem } from "../lib/format";

/** "3f0c…_annual report.pdf" was stored as "<uuid>_<name>"; show the name the user uploaded. */
export function originalName(filename: string): string {
  return filename.replace(/^[0-9a-f-]{36}_/i, "");
}

/** The title row's sentence: what can be asked about now, and what needs attention. */
export function summarise(documents: Document[]): string {
  if (documents.length === 0) return "No documents yet. Upload a PDF to start asking questions.";
  const ready = documents.filter((d) => d.status === "processed").length;
  const reading = documents.filter((d) => isInProgress(d.status)).length;
  const failed = documents.filter((d) => d.status === "failed").length;
  const parts = [ready === 0 ? "None ready to ask yet" : `${ready} ready to ask`];
  if (reading) parts.push(`${reading} being read`);
  if (failed) parts.push(`${failed} failed`);
  return parts.join(" · ");
}

export function DocumentsPage() {
  const documents = useDocuments();
  const upload = useUpload();
  const remove = useDeleteDocument();
  const fileInput = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [toDelete, setToDelete] = useState<Document | null>(null);

  const rows = useMemo(
    () => [...(documents.data?.documents ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [documents.data],
  );

  function startUpload(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    const reason = uploadProblem(file);
    setProblem(reason);
    if (reason) return;
    upload.mutate(file, { onError: (error) => setProblem(error.message) });
  }

  const dropProps = {
    onDragOver: (event: DragEvent) => {
      event.preventDefault();
      setDragging(true);
    },
    onDragLeave: () => setDragging(false),
    onDrop: (event: DragEvent) => {
      event.preventDefault();
      setDragging(false);
      startUpload(event.dataTransfer.files);
    },
  };

  const chooseFile = () => fileInput.current?.click();
  const dropzone = (big: boolean) => (
    <div className={`dropzone${big ? " big" : ""}${dragging ? " over" : ""}`}>
      <div>
        <span className="drag-only">
          <strong>Drop a PDF here</strong> or{" "}
        </span>
        <button type="button" className="link-btn" onClick={chooseFile}>
          <span className="drag-only">choose a file</span>
          <span className="tap-only">Choose a PDF</span>
        </button>
      </div>
      <div>PDFs up to 10 MB with selectable text. Scanned pages can't be read yet.</div>
    </div>
  );

  return (
    <>
      <div className="title-row">
        <div>
          <h1>Documents</h1>
          <p className="sub" aria-live="polite">
            {documents.data ? summarise(rows) : " "}
          </p>
        </div>
        <div className="actions">
          <button type="button" className="btn primary" onClick={chooseFile} disabled={upload.isPending}>
            Upload PDF
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            data-testid="file-input"
            onChange={(event) => {
              startUpload(event.target.files);
              event.target.value = "";
            }}
          />
        </div>
      </div>

      <div className="library-grid" {...dropProps}>
      <section className="panel flush library" aria-labelledby="library-title">
        <header>
          <h2 id="library-title">Your documents</h2>
          {documents.data && <span className="meta num">{documents.data.total.toLocaleString("en-GB")} total</span>}
        </header>

        {problem && (
          <p className="form-error" role="alert" style={{ margin: "0 var(--pad) 12px" }}>
            {problem}
          </p>
        )}
        {upload.isPending && (
          <p className="uploading" role="status">
            Uploading {upload.variables ? `"${upload.variables.name}"` : "the file"}…
          </p>
        )}

        {documents.isLoading && <LoadingRows />}
        {documents.isError && (
          <div className="empty" style={{ margin: "8px var(--pad) var(--pad)" }} role="alert">
            Couldn't load your documents.{" "}
            <button type="button" className="link-btn" onClick={() => documents.refetch()}>
              Retry
            </button>
          </div>
        )}
        {documents.data && rows.length === 0 && dropzone(true)}
        {rows.length > 0 && (
          <>
            <table>
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col" className="n">
                    Pages
                  </th>
                  <th scope="col">Status</th>
                  <th scope="col">Uploaded</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((doc) => (
                  <tr key={doc.id}>
                    <td className="doc-cell">
                      <Link className="doc-link" to={`/documents/${doc.id}`}>
                        {doc.title}
                      </Link>
                      <span className="sub">{originalName(doc.filename)}</span>
                      {doc.status === "failed" && doc.error_message && <span className="reason">{doc.error_message}</span>}
                    </td>
                    <td className="n num pages-cell">{formatPages(doc.page_count)}</td>
                    <td className="status-cell">
                      <StatusPill status={doc.status} />
                    </td>
                    <td className="date-cell num">{formatDateTime(doc.created_at)}</td>
                    <td className="n action-cell">
                      <button type="button" className="link-btn" aria-label={`Delete ${doc.title}`} onClick={() => setToDelete(doc)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
      {rows.length > 0 && (
        <aside className="panel upload-panel" aria-labelledby="add-title">
          <header>
            <h2 id="add-title">Add a document</h2>
          </header>
          {dropzone(false)}
          <h3 className="steps-title">After you upload</h3>
          <ol className="steps">
            <li>
              <strong>Reading.</strong> DocuMind extracts the text of every page and splits it into short passages.
            </li>
            <li>
              <strong>Ready.</strong> Ask questions; every answer cites the pages it comes from.
            </li>
            <li>
              <strong>Failed.</strong> The list says why, for example a scanned page with no text.
            </li>
          </ol>
        </aside>
      )}
      </div>

      <ConfirmDialog
        open={toDelete !== null}
        title={`Delete "${toDelete?.title ?? ""}"?`}
        confirmLabel="Delete document"
        busy={remove.isPending}
        error={remove.error?.message ?? null}
        onCancel={() => {
          remove.reset();
          setToDelete(null);
        }}
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id, { onSuccess: () => setToDelete(null) });
        }}
      >
        Its passages and the PDF file are deleted. This can't be undone.
      </ConfirmDialog>
    </>
  );
}

function LoadingRows() {
  return (
    <div style={{ padding: "8px var(--pad) var(--pad)" }} aria-label="Loading documents" role="status">
      {[0, 1, 2].map((i) => (
        <div key={i} style={{ display: "grid", gap: 6, padding: "12px 0" }}>
          <div className="skeleton" style={{ width: "40%" }} />
          <div className="skeleton" style={{ width: "24%", height: 12 }} />
        </div>
      ))}
    </div>
  );
}
