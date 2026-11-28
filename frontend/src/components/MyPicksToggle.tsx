import type { PickView } from "../lib/usePicks";

// All / Hide picked / My picks, over the results. Shown once something on
// this tab has been marked as picked.
export default function MyPicksToggle({
  count,
  view,
  onChange,
}: {
  count: number;
  view: PickView;
  onChange: (view: PickView) => void;
}) {
  if (count === 0 && view === "all") return null;
  const seg = (active: boolean) =>
    `press flex h-9 items-center whitespace-nowrap rounded-md px-2.5 text-xs font-medium sm:h-7 sm:px-3 ${
      active
        ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
        : "text-slate-600 dark:text-slate-300"
    }`;
  return (
    <div role="group" aria-label="Picked bets" className="inline-flex rounded-lg bg-slate-200/70 p-0.5 dark:bg-slate-800">
      <button type="button" aria-pressed={view === "all"} onClick={() => onChange("all")} className={seg(view === "all")}>
        All
      </button>
      <button type="button" aria-pressed={view === "hide"} onClick={() => onChange("hide")} className={seg(view === "hide")}>
        Hide picked
      </button>
      <button type="button" aria-pressed={view === "only"} onClick={() => onChange("only")} className={seg(view === "only")}>
        My picks <span className="ml-1 tabular-nums opacity-70">{count}</span>
      </button>
    </div>
  );
}
