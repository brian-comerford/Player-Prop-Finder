import type { MouseEvent } from "react";
import { formatBook, formatOdds } from "../lib/format";
import type { PickSnapshot } from "../lib/usePicks";

function CheckIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" className={`h-4 w-4 shrink-0 ${className}`} fill="none" stroke="currentColor" strokeWidth={2.25} aria-hidden="true">
      <path d="M5 10.5l3.2 3.2L15 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// "Mark as picked" toggle. icon: the table's narrow column; footer: the
// bottom bar of a phone card; block: the full-width button in a sheet.
export default function PickButton({
  picked,
  onToggle,
  variant,
}: {
  picked: boolean;
  onToggle: () => void;
  variant: "icon" | "footer" | "block";
}) {
  const handle = (e: MouseEvent) => {
    e.stopPropagation();
    onToggle();
  };
  const label = picked ? "Picked" : "Mark as picked";

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={handle}
        aria-pressed={picked}
        aria-label={picked ? "Picked (tap to unmark)" : "Mark as picked"}
        title={label}
        className={`press flex h-7 w-7 items-center justify-center rounded-full border ${
          picked
            ? "border-emerald-600 bg-emerald-600 text-white dark:border-emerald-500 dark:bg-emerald-500 dark:text-slate-950"
            : "border-slate-300 text-transparent hover:border-emerald-500 hover:text-emerald-600 dark:border-slate-600 dark:hover:text-emerald-400"
        }`}
      >
        <CheckIcon className="h-3.5 w-3.5" />
      </button>
    );
  }

  if (variant === "footer") {
    return (
      <button
        type="button"
        onClick={handle}
        aria-pressed={picked}
        className={`press flex min-h-[44px] shrink-0 items-center gap-1.5 px-3.5 text-xs font-semibold ${
          picked ? "text-emerald-700 dark:text-emerald-400" : "text-slate-600 dark:text-slate-300"
        }`}
      >
        <span
          className={`flex h-5 w-5 items-center justify-center rounded-full border ${
            picked
              ? "border-emerald-600 bg-emerald-600 text-white dark:border-emerald-500 dark:bg-emerald-500 dark:text-slate-950"
              : "border-slate-400 text-transparent dark:border-slate-500"
          }`}
        >
          <CheckIcon className="h-3 w-3" />
        </span>
        {label}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handle}
      aria-pressed={picked}
      className={`press flex h-11 w-full items-center justify-center gap-2 rounded-xl border text-sm font-semibold sm:w-auto sm:px-5 ${
        picked
          ? "border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700 dark:border-emerald-500 dark:bg-emerald-500 dark:text-slate-950 dark:hover:bg-emerald-400"
          : "border-slate-300 bg-white text-slate-800 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
      }`}
    >
      <CheckIcon />
      {picked ? "Picked — tap to unmark" : "Mark as picked"}
    </button>
  );
}

// What they took, shown when the side, line, price or book has moved since.
export function PickedNote({
  snapshot,
  current,
  className = "",
}: {
  snapshot: PickSnapshot;
  // The same pick as it stands in today's data (see propSnapshot).
  current: PickSnapshot;
  className?: string;
}) {
  const moved = snapshot.label !== current.label || snapshot.price !== current.price || snapshot.book !== current.book;
  if (!moved) return null;
  return (
    <p className={`text-xs text-slate-600 dark:text-slate-400 ${className}`}>
      You took <span className="font-semibold tabular-nums">{snapshot.label}</span> at{" "}
      <span className="font-semibold tabular-nums">{formatOdds(snapshot.price)}</span>
      {snapshot.book && <> on {formatBook(snapshot.book)}</>}. Now:{" "}
      <span className="tabular-nums">
        {current.label} at {formatOdds(current.price)}
        {current.book && current.book !== snapshot.book && <> on {formatBook(current.book)}</>}
      </span>
      .
    </p>
  );
}
