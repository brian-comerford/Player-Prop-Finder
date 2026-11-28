import { useState, type ReactNode } from "react";

// The box the Props/TD/Games filters live in. From sm: up everything is
// always shown; on phones it folds down to one row (plus an optional
// leading control, e.g. the player search) so the list itself starts on
// the first screen, with a count of what's switched on.
export default function FilterPanel({
  activeCount,
  summary,
  onReset,
  leading,
  children,
}: {
  activeCount: number;
  // Shown next to the toggle while folded, e.g. the minimum edge in force.
  summary?: ReactNode;
  onReset?: () => void;
  leading?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900 sm:p-4">
      <div className="flex items-center gap-2 sm:hidden">
        {leading}
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className={`press flex shrink-0 items-center gap-1.5 rounded-lg text-sm font-medium ${
            !leading
              ? // The panel's own border already frames it -- no box-in-a-box.
                "-my-1 h-9 w-full justify-between px-1 text-slate-700 dark:text-slate-200"
              : open
                ? "h-10 border border-slate-900 bg-slate-900 px-3 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                : "h-10 border border-slate-300 px-3 text-slate-700 dark:border-slate-700 dark:text-slate-200"
          }`}
        >
          <span className="flex items-center gap-1.5">
            Filters
            {activeCount > 0 && (
              <span
                className={`min-w-[1.25rem] rounded-full px-1.5 text-center text-[11px] font-semibold tabular-nums ${
                  open && leading ? "bg-white/20" : "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                }`}
              >
                {activeCount}
              </span>
            )}
          </span>
          <span className="flex items-center gap-1.5">
            {!leading && summary && !open && <span className="text-xs font-normal opacity-70">{summary}</span>}
            <svg
              viewBox="0 0 20 20"
              className={`h-4 w-4 transition-transform duration-200 ease-[var(--ease-out)] ${open ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              <path d="M5 8l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>
      </div>
      {leading && summary && !open && (
        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 sm:hidden">{summary}</p>
      )}
      <div className={open ? "reveal mt-3 sm:mt-0" : "hidden sm:block"}>
        {children}
        {onReset && activeCount > 0 && (
          <button
            type="button"
            onClick={onReset}
            className="press mt-3 text-xs font-medium text-slate-500 underline decoration-dotted underline-offset-2 dark:text-slate-400"
          >
            Reset filters
          </button>
        )}
      </div>
    </div>
  );
}
