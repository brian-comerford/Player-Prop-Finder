import { useMemo, useState, type ReactNode } from "react";
import { fetchConfidenceBacktest } from "../lib/data";
import { formatPct, formatUnits } from "../lib/format";
import { sumUnits } from "../lib/odds";
import type { BacktestPick, Confidence, ConfidenceBacktest as Backtest } from "../lib/types";
import PickFilters, { DEFAULT_PICK_FILTERS, matchesPickFilters, type PickFilterState } from "./PickFilters";

const TIERS: Confidence[] = ["High", "Medium", "Low"];

interface Summary {
  picks: number;
  hitRate: number;
  expectedHitRate: number;
  units: number | null;
  pricedPicks: number;
}

function summarize(picks: BacktestPick[]): Summary | undefined {
  if (picks.length === 0) return undefined;
  const hits = picks.filter((p) => p.hit).length;
  const expected = picks.reduce((a, p) => a + p.market_prob, 0);
  return {
    picks: picks.length,
    hitRate: hits / picks.length,
    expectedHitRate: expected / picks.length,
    ...sumUnits(picks),
  };
}

function byTier(picks: BacktestPick[]): Partial<Record<Confidence, Summary>> {
  return Object.fromEntries(TIERS.map((t) => [t, summarize(picks.filter((p) => p.confidence === t))]));
}

function Cell({ summary }: { summary: Summary | undefined }) {
  if (!summary) return <td className="px-2 py-1.5 align-top text-slate-400">—</td>;
  const { units } = summary;
  return (
    <td className="whitespace-nowrap px-2 py-1.5 align-top">
      <div
        className={`font-semibold ${
          summary.hitRate > summary.expectedHitRate ? "text-emerald-600 dark:text-emerald-400" : ""
        }`}
      >
        {formatPct(summary.hitRate)}
      </div>
      <div className="text-slate-500 dark:text-slate-400">exp {formatPct(summary.expectedHitRate)}</div>
      <div
        className={
          units === null
            ? "text-slate-500"
            : units > 0
              ? "text-emerald-600 dark:text-emerald-400"
              : units < 0
                ? "text-rose-600 dark:text-rose-400"
                : ""
        }
      >
        {formatUnits(units)}
      </div>
      <div className="text-slate-500 dark:text-slate-400">
        ({summary.pricedPicks < summary.picks ? `${summary.pricedPicks}/` : ""}
        {summary.picks})
      </div>
    </td>
  );
}

function Row({
  label,
  tiers,
  columns,
  bold,
}: {
  label: ReactNode;
  tiers: Partial<Record<Confidence, Summary>>;
  columns: Confidence[];
  bold?: boolean;
}) {
  return (
    <tr className={`border-t border-slate-200 dark:border-slate-800 ${bold ? "bg-slate-50 dark:bg-slate-800/50" : ""}`}>
      <th
        scope="row"
        className={`whitespace-nowrap px-2 py-1.5 text-left align-top ${bold ? "font-semibold" : "font-normal"}`}
      >
        {label}
      </th>
      {columns.map((t) => (
        <Cell key={t} summary={tiers[t]} />
      ))}
    </tr>
  );
}

function BacktestTable({ data }: { data: Backtest }) {
  const [filters, setFilters] = useState<PickFilterState>(DEFAULT_PICK_FILTERS);

  const marketOptions = useMemo(
    () => Array.from(new Set(data.picks.map((p) => p.market_label))).sort(),
    [data]
  );
  const filtered = useMemo(() => data.picks.filter((p) => matchesPickFilters(p, filters)), [data, filters]);
  const columns = useMemo(
    () => (filters.confidence === "All" ? TIERS : [filters.confidence]),
    [filters.confidence]
  );
  const overall = useMemo(() => byTier(filtered), [filtered]);
  const weeks = useMemo(
    () =>
      data.weeks
        .map((w) => ({
          ...w,
          tiers: byTier(filtered.filter((p) => p.season === w.season && p.week === w.week)),
        }))
        .filter((w) => columns.some((t) => w.tiers[t])),
    [data, filtered, columns]
  );

  return (
    <>
      <PickFilters filters={filters} onChange={setFilters} marketOptions={marketOptions} />
      {filtered.length === 0 ? (
        <p>No backtested picks match these filters.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs tabular-nums">
            <thead>
              <tr className="text-left text-slate-500 dark:text-slate-400">
                <th className="px-2 py-1 font-medium">Week</th>
                {columns.map((t) => (
                  <th key={t} className="px-2 py-1 font-medium">
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-slate-700 dark:text-slate-300">
              <Row label="All" tiers={overall} columns={columns} bold />
              {weeks.map((w) => (
                <Row
                  key={`${w.season}-${w.week}`}
                  label={
                    <>
                      Wk {w.week}
                      {w.backfilled && <span className="text-slate-500 dark:text-slate-400">*</span>}
                    </>
                  }
                  tiers={w.tiers}
                  columns={columns}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-slate-500 dark:text-slate-400">
        Each cell: hit rate, the hit rate the market&apos;s odds expected, units won betting 1 unit on
        each, and picks counted (&quot;12/89&quot; means only 12 of 89 had a recorded price to compute
        units from).
        {data.weeks.some((w) => w.backfilled) && (
          <>
            {" "}
            * Rebuilt afterwards from historical odds for training; these picks were never posted
            live, so they aren&apos;t in the Track Record.
          </>
        )}{" "}
        A backtest flatters a model; expect live results to land lower.
      </p>
    </>
  );
}

// Tucked away as a collapsed section at the bottom of the Confidence
// explanation; only fetched once someone actually opens it.
export default function ConfidenceBacktest() {
  const [data, setData] = useState<Backtest | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    if (data || error) return;
    fetchConfidenceBacktest()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }

  return (
    <details
      className="mt-3"
      onToggle={(e) => {
        if ((e.currentTarget as HTMLDetailsElement).open) load();
      }}
    >
      <summary className="cursor-pointer text-xs text-slate-500 underline decoration-dotted dark:text-slate-400">
        Backtest by week
      </summary>
      <div className="mt-2 space-y-2 text-xs">
        <p>
          Today&apos;s confidence model replayed on every graded week. Each week is rated by a
          model trained only on the <em>other</em> weeks, so no week is graded by a model that
          already saw how it turned out. Covers every player prop listed (not Anytime TD); the
          filters work the same as the Track Record&apos;s.
        </p>
        {error && <p className="text-rose-600 dark:text-rose-400">Couldn&apos;t load the backtest: {error}</p>}
        {!data && !error && <p>Loading…</p>}
        {data && data.weeks.length === 0 && <p>Not enough graded picks yet.</p>}
        {data && data.weeks.length > 0 && <BacktestTable data={data} />}
      </div>
    </details>
  );
}
