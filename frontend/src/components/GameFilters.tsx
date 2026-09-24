import type { GameMeta } from "../lib/types";

export interface GameFilterState {
  segment: "All" | "full" | "h1" | "h2";
  market: "All" | "spread" | "total";
  matchup: string;
  minEdge: number;
  minConfidence: "Any" | "Medium" | "High";
}

export const DEFAULT_GAME_FILTERS: GameFilterState = {
  segment: "All",
  market: "All",
  matchup: "All",
  minEdge: 0.03,
  minConfidence: "Any",
};

export default function GameFilters({
  meta,
  matchups,
  filters,
  onChange,
}: {
  meta: GameMeta;
  matchups: string[];
  filters: GameFilterState;
  onChange: (next: GameFilterState) => void;
}) {
  const set = <K extends keyof GameFilterState>(key: K, value: GameFilterState[K]) =>
    onChange({ ...filters, [key]: value });

  return (
    <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-2 lg:grid-cols-4">
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Segment</span>
        <select
          value={filters.segment}
          onChange={(e) => set("segment", e.target.value as GameFilterState["segment"])}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        >
          <option value="All">All</option>
          {Object.entries(meta.segments).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Market</span>
        <select
          value={filters.market}
          onChange={(e) => set("market", e.target.value as GameFilterState["market"])}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        >
          <option value="All">All</option>
          <option value="spread">Spread</option>
          <option value="total">Total</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Game</span>
        <select
          value={filters.matchup}
          onChange={(e) => set("matchup", e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        >
          <option value="All">All games</option>
          {matchups.map((m) => (
            <option key={m} value={m}>
              {m}
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
          onChange={(e) => set("minConfidence", e.target.value as GameFilterState["minConfidence"])}
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
