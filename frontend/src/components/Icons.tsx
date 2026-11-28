// Drawn icons, one stroke weight, so nothing leans on font glyphs (which
// render at different sizes and weights from one platform to the next).
export function ChevronIcon({ className = "", direction = "right" }: { className?: string; direction?: "right" | "down" }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className={`h-3.5 w-3.5 shrink-0 ${direction === "down" ? "rotate-90" : ""} ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path d="M8 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
