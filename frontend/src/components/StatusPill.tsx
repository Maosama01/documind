// The words of the trade for a document's processing state.
const LABELS: Record<string, { label: string; tone: "" | "pos" | "neg" }> = {
  pending: { label: "Queued", tone: "" },
  processing: { label: "Reading", tone: "" },
  processed: { label: "Ready", tone: "pos" },
  failed: { label: "Failed", tone: "neg" },
};

export function statusLabel(status: string): string {
  return LABELS[status]?.label ?? status;
}

export function StatusPill({ status }: { status: string }) {
  const entry = LABELS[status] ?? { label: status, tone: "" };
  return <span className={`pill ${entry.tone}`.trim()}>{entry.label}</span>;
}
