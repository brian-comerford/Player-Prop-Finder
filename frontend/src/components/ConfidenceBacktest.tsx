import { useState, type ReactNode } from "react";
import { fetchConfidenceBacktest } from "../lib/data";
import { formatPct, formatUnits } from "../lib/format";
import type { BacktestSummary, BacktestTiers, ConfidenceBacktest as Backtest } from "../lib/types";

const TIERS = ["High", "Medium", "Low"] as const;

function Cell({ summary }: { summary: BacktestSummary | undefined }) {
  if (!summary) return <td className="px-2 py-1.5 text-slate-400">—</td>;
  const beat = summary.hit_rate > summary.expected_hit_rate;
  const units = summary.units;
  return (
    <td className="whitespace-nowrap px-2 py-1.5 align-top">
      <div className={`font-semibold ${beat ? "text-emerald-600 dark:text-emerald-400" : ""}`}>
        {formatPct(summary.hit_rate)}
      </div>
      <div className="text-slate-500 dark:text-slate-400">exp {formatPct(summary.expected_hit_rate)}</div>
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
        ({summary.priced_picks < summary.picks ? `${summary.priced_picks}/` : ""}
        {summary.picks})
      </div>
    </td>
  );
}

function Row({ label, tiers, bold }: { label: ReactNode; tiers: BacktestTiers; bold?: boolean }) {
  return (
    <tr className={`border-t border-slate-200 dark:border-slate-800 ${bold ? "bg-slate-50 dark:bg-slate-800/50" : ""}`}>
      <th scope="row" className={`whitespace-nowrap px-2 py-1.5 text-left align-top ${bold ? "font-semibold" : "font-normal"}`}>
        {label}
      </th>
      {TIERS.map((t) => (
        <Cell key={t} summary={tiers[t]} />
      ))}
    </tr>
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
          already saw how it turned out. Covers every player prop listed (not Anytime TD), before
          any Min. edge filter.
        </p>
        {error && <p className="text-rose-600 dark:text-rose-400">Couldn&apos;t load the backtest: {error}</p>}
        {!data && !error && <p>Loading…</p>}
        {data && data.weeks.length === 0 && <p>Not enough graded picks yet.</p>}
        {data && data.weeks.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs tabular-nums">
                <thead>
                  <tr className="text-left text-slate-500 dark:text-slate-400">
                    <th className="px-2 py-1 font-medium">Week</th>
                    {TIERS.map((t) => (
                      <th key={t} className="px-2 py-1 font-medium">
                        {t}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="text-slate-700 dark:text-slate-300">
                  <Row label="All" tiers={data.overall} bold />
                  {data.weeks.map((w) => (
                    <Row
                      key={`${w.season}-${w.week}`}
                      label={
                        <>
                          Wk {w.week}
                          {w.backfilled && <span className="text-slate-500 dark:text-slate-400">*</span>}
                        </>
                      }
                      tiers={w.tiers}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-slate-500 dark:text-slate-400">
              Each cell: hit rate, the hit rate the market&apos;s odds expected, and units won
              betting 1 unit on each (picks counted; &quot;12/89&quot; means only 12 of 89 had a
              recorded price to compute units from).
              {data.weeks.some((w) => w.backfilled) && (
                <>
                  {" "}
                  * Rebuilt afterwards from historical odds for training; these picks were never
                  posted live, so they aren&apos;t in the Track Record.
                </>
              )}{" "}
              A backtest flatters a model; expect live results to land lower.
            </p>
          </>
        )}
      </div>
    </details>
  );
}
