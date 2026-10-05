import type { GameMeta } from "../lib/types";
import { formatBook, pillClass } from "../lib/format";

const MARKET_OPTIONS: Array<{ key: "spread" | "total"; label: string }> = [
  { key: "spread", label: "Spread" },
  { key: "total", label: "Total" },
];

export interface GameFilterState {
  segment: "All" | "full" | "h1" | "h2";
  // Which market(s) to show. Empty means "all markets", same convention
  // as Filters.tsx.
  markets: Set<"spread" | "total">;
  matchup: string;
  minEdge: number;
  minConfidence: "Any" | "Medium" | "High";
  // Which book(s) the recommended side's price has to come from. Empty
  // means "all books", same convention as Filters.tsx.
  books: Set<string>;
}

export const DEFAULT_GAME_FILTERS: GameFilterState = {
  segment: "All",
  markets: new Set(),
  matchup: "All",
  minEdge: 0.03,
  minConfidence: "Any",
  books: new Set(),
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

  function toggleMarket(market: "spread" | "total") {
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
          {MARKET_OPTIONS.map(({ key, label }) => (
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
