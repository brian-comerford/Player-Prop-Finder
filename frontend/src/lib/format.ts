const BOOK_LABELS: Record<string, string> = {
  draftkings: "DraftKings",
  fanduel: "FanDuel",
  kalshi: "Kalshi",
  sample: "Sample",
};

export function formatBook(book: string | null): string {
  if (!book) return "—";
  return BOOK_LABELS[book] ?? book;
}

export function formatOdds(odds: number | null): string {
  if (odds === null || Number.isNaN(odds)) return "—";
  return odds > 0 ? `+${odds}` : `${odds}`;
}

export function formatPct(value: number | null, digits = 1): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatLine(line: number | null): string {
  return line === null ? "—" : line.toString();
}

export function edgeColorClass(edge: number): string {
  if (edge >= 0.06) return "text-emerald-600 dark:text-emerald-400 font-semibold";
  if (edge > 0) return "text-emerald-700/80 dark:text-emerald-400/80";
  return "text-slate-500 dark:text-slate-400";
}

export function confidenceColorClass(confidence: string): string {
  switch (confidence) {
    case "High":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300";
    case "Medium":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
    default:
      return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  }
}
