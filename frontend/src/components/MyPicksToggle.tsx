// "All / My picks" switch over the results, shown once something on this
// tab has been marked as picked.
export default function MyPicksToggle({
  count,
  on,
  onChange,
}: {
  count: number;
  on: boolean;
  onChange: (on: boolean) => void;
}) {
  if (count === 0 && !on) return null;
  const seg = (active: boolean) =>
    `press flex h-9 items-center rounded-md px-3 text-xs font-medium sm:h-7 ${
      active
        ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
        : "text-slate-600 dark:text-slate-300"
    }`;
  return (
    <div role="group" aria-label="Show" className="inline-flex rounded-lg bg-slate-200/70 p-0.5 dark:bg-slate-800">
      <button type="button" aria-pressed={!on} onClick={() => onChange(false)} className={seg(!on)}>
        All
      </button>
      <button type="button" aria-pressed={on} onClick={() => onChange(true)} className={seg(on)}>
        My picks <span className="ml-1 tabular-nums opacity-70">{count}</span>
      </button>
    </div>
  );
}
