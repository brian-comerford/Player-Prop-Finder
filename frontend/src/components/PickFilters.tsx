import type { Confidence } from "../lib/types";
import { pillClass } from "../lib/format";

const CONFIDENCE_OPTIONS: Array<Confidence | "All"> = ["All", "High", "Medium", "Low"];

export interface PickFilterState {
  minEdge: number;
  confidence: Confidence | "All";
  // Empty means "All".
  markets: Set<string>;
}

export const DEFAULT_PICK_FILTERS: PickFilterState = { minEdge: 0, confidence: "All", markets: new Set() };

export function pickFiltersActive(f: PickFilterState): boolean {
  return f.minEdge > 0 || f.confidence !== "All" || f.markets.size > 0;
}

export function matchesPickFilters(
  p: { edge: number; confidence: Confidence; market_label: string },
  f: PickFilterState
): boolean {
  return (
    // minEdge at its floor (0%) means "no edge filter" -- some graded
    // picks carry a negative edge (the model still grades whichever side
    // it liked better even when neither side looked profitable), and
    // those should still count by default so the unfiltered totals match
    // the overall summary, not silently drop picks before the user has
    // touched the slider.
    (f.minEdge <= 0 || p.edge >= f.minEdge) &&
    (f.confidence === "All" || p.confidence === f.confidence) &&
    (f.markets.size === 0 || f.markets.has(p.market_label))
  );
}

// The Min. edge / Confidence / Bet type controls shared by the track
// record panel and the confidence backtest.
export default function PickFilters({
  filters,
  onChange,
  marketOptions,
}: {
  filters: PickFilterState;
  onChange: (next: PickFilterState) => void;
  marketOptions: string[];
}) {
  const { minEdge, confidence, markets } = filters;

  function toggleMarket(m: string) {
    const next = new Set(markets);
    if (next.has(m)) next.delete(m);
    else next.add(m);
    onChange({ ...filters, markets: next });
  }

  return (
    <div className="mb-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500 dark:text-slate-400">Min. edge: {(minEdge * 100).toFixed(1)}%</span>
          <input
            type="range"
            min={0}
            max={0.1}
            step={0.005}
            value={minEdge}
            onChange={(e) => onChange({ ...filters, minEdge: Number(e.target.value) })}
            className="mt-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500 dark:text-slate-400">Confidence</span>
          <select
            value={confidence}
            onChange={(e) => onChange({ ...filters, confidence: e.target.value as Confidence | "All" })}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          >
            {CONFIDENCE_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 flex flex-col gap-1.5 text-sm">
        <span className="text-slate-500 dark:text-slate-400">
          Bet type{markets.size > 0 && ` (${markets.size} selected)`}
        </span>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => onChange({ ...filters, markets: new Set() })}
            className={pillClass(markets.size === 0)}
          >
            All
          </button>
          {marketOptions.map((m) => (
            <button key={m} type="button" onClick={() => toggleMarket(m)} className={pillClass(markets.has(m))}>
              {m}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
