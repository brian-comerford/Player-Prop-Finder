import type { Meta } from "../lib/types";

export interface FilterState {
  search: string;
  position: string;
  market: string;
  minEdge: number;
  minConfidence: "Any" | "Medium" | "High";
}

export const DEFAULT_FILTERS: FilterState = {
  search: "",
  position: "All",
  market: "All",
  minEdge: 0.03,
  minConfidence: "Any",
};

const POSITIONS = ["All", "QB", "RB", "WR", "TE"];

export default function Filters({
  meta,
  filters,
  onChange,
}: {
  meta: Meta;
  filters: FilterState;
  onChange: (next: FilterState) => void;
}) {
  const set = <K extends keyof FilterState>(key: K, value: FilterState[K]) =>
    onChange({ ...filters, [key]: value });

  return (
    <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-2 lg:grid-cols-5">
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Search player</span>
        <input
          type="text"
          value={filters.search}
          onChange={(e) => set("search", e.target.value)}
          placeholder="e.g. Bijan Robinson"
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Position</span>
        <select
          value={filters.position}
          onChange={(e) => set("position", e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        >
          {POSITIONS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Market</span>
        <select
          value={filters.market}
          onChange={(e) => set("market", e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        >
          <option value="All">All</option>
          {Object.entries(meta.markets).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">
          Min. edge: {(filters.minEdge * 100).toFixed(0)}%
        </span>
        <input
          type="range"
          min={0}
          max={0.25}
          step={0.01}
          value={filters.minEdge}
          onChange={(e) => set("minEdge", Number(e.target.value))}
          className="mt-2"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Min. confidence</span>
        <select
          value={filters.minConfidence}
          onChange={(e) => set("minConfidence", e.target.value as FilterState["minConfidence"])}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        >
          <option value="Any">Any</option>
          <option value="Medium">Medium+</option>
          <option value="High">High only</option>
        </select>
      </label>
    </div>
  );
}
