import type { Meta } from "../lib/types";
import { formatBook, pillClass } from "../lib/format";

export interface FilterState {
  search: string;
  position: string;
  // Which market(s) to show. Empty means "all markets" -- same empty-set-
  // means-All convention as books/the track record's bet-type filter.
  markets: Set<string>;
  matchup: string;
  timeSlot: string;
  minEdge: number;
  minConfidence: "Any" | "Medium" | "High";
  // Which book(s) the recommended side's price has to come from. Empty
  // means "all books".
  books: Set<string>;
}

export const DEFAULT_FILTERS: FilterState = {
  search: "",
  position: "All",
  markets: new Set(),
  matchup: "All",
  timeSlot: "All",
  // On graded history, blended edges under 4% showed no real edge over
  // the market; 4%+ beat it by 8-11 points.
  minEdge: 0.04,
  minConfidence: "Any",
  books: new Set(),
};

// Anytime TD uses a smaller model weight (10%), so its blended edges run
// smaller -- a 4% floor would hide nearly the whole tab.
export const DEFAULT_TD_FILTERS: FilterState = { ...DEFAULT_FILTERS, minEdge: 0.03 };

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

  function toggleMarket(market: string) {
    const next = new Set(filters.markets);
    if (next.has(market)) next.delete(market);
    else next.add(market);
    set("markets", next);
  }

  function toggleBook(book: string) {
    const next = new Set(filters.books);
    if (next.has(book)) next.delete(book);
    else next.add(book);
    set("books", next);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
          <span className="text-slate-500 dark:text-slate-400">Game</span>
          <select
            value={filters.matchup}
            onChange={(e) => set("matchup", e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          >
            <option value="All">All games</option>
            {meta.matchups.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500 dark:text-slate-400">Time slot</span>
          <select
            value={filters.timeSlot}
            onChange={(e) => set("timeSlot", e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          >
            <option value="All">All times</option>
            {meta.time_slots.map((t) => (
              <option key={t} value={t}>
                {t}
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

      <div className="mt-3 flex flex-col gap-1.5 text-sm">
        <span className="text-slate-500 dark:text-slate-400">
          Market{filters.markets.size > 0 && ` (${filters.markets.size} selected)`}
        </span>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => set("markets", new Set())}
            className={pillClass(filters.markets.size === 0)}
          >
            All
          </button>
          {Object.entries(meta.markets).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => toggleMarket(key)}
              className={pillClass(filters.markets.has(key))}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {meta.books.length > 0 && (
        <div className="mt-3 flex flex-col gap-1.5 text-sm">
          <span className="text-slate-500 dark:text-slate-400">
            Book{filters.books.size > 0 && ` (${filters.books.size} selected)`}
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => set("books", new Set())}
              className={pillClass(filters.books.size === 0)}
            >
              All
            </button>
            {meta.books.map((b) => (
              <button key={b} type="button" onClick={() => toggleBook(b)} className={pillClass(filters.books.has(b))}>
                {formatBook(b)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
