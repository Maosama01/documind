/** DocuMind's mark: three pages, the middle one cited (the one hue). Same drawing as the page strip. */
export function Mark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <rect x="3" y="2" width="14" height="4" rx="1" fill="var(--text)" />
      <rect x="3" y="8" width="14" height="4" rx="1" fill="var(--cite)" />
      <rect x="3" y="14" width="14" height="4" rx="1" fill="var(--text)" />
    </svg>
  );
}

export function Brand() {
  return (
    <span className="brand">
      <Mark />
      DocuMind
    </span>
  );
}
