import { useMemo, useState } from "react";
import type { Confidence, GameTrackRecordDetail, GradedGamePick, TrackRecord } from "../lib/types";
import { formatUnits, pillClass } from "../lib/format";
import { pickUnits } from "../lib/odds";
import { useLockBodyScroll } from "../lib/useLockBodyScroll";

const CONFIDENCE_TIERS: Confidence[] = ["High", "Medium", "Low"];
const CONFIDENCE_OPTIONS: Array<Confidence | "All"> = ["All", "High", "Medium", "Low"];

interface WeekGroup {
  season: number;
  week: number;
  picks: GradedGamePick[];
  hits: number;
}

function pct(hitRate: number): string {
  return `${Math.round(hitRate * 100)}%`;
}

function actualLabel(p: GradedGamePick): string {
  return `${p.actual_away_points}-${p.actual_home_points}`;
}

function groupByWeek(picks: GradedGamePick[]): WeekGroup[] {
  const groups: WeekGroup[] = [];
  const byKey = new Map<string, WeekGroup>();
  for (const p of picks) {
    const key = `${p.season}-${p.week}`;
    let group = byKey.get(key);
    if (!group) {
      group = { season: p.season, week: p.week, picks: [], hits: 0 };
      byKey.set(key, group);
      groups.push(group);
    }
    group.picks.push(p);
    if (p.hit) group.hits += 1;
  }
  return groups;
}

export default function GameTrackRecordSection({
  trackRecord,
  fetchDetail,
}: {
  trackRecord: TrackRecord | null;
  fetchDetail: () => Promise<GameTrackRecordDetail>;
}) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<GameTrackRecordDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!trackRecord?.overall) return null;
  const overall = trackRecord.overall;

  function handleOpen() {
    setOpen(true);
    if (!detail && !loading) {
      setLoading(true);
      fetchDetail()
        .then((d) => {
          setDetail(d);
          setError(null);
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
        .finally(() => setLoading(false));
    }
  }

  return (
    <div className="flex justify-center pb-4 pt-2">
      <button
        onClick={handleOpen}
        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        Track record: {pct(overall.hit_rate)} ({overall.hits}/{overall.picks})
        {overall.priced_picks > 0 && <> &middot; {formatUnits(overall.units)}</>}
      </button>

      {open && (
        <GameTrackRecordPanel
          trackRecord={trackRecord}
          detail={detail}
          loading={loading}
          error={error}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}

function GameTrackRecordPanel({
  trackRecord,
  detail,
  loading,
  error,
  onClose,
}: {
  trackRecord: TrackRecord;
  detail: GameTrackRecordDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  useLockBodyScroll();
  const overall = trackRecord.overall!;

  const [minEdge, setMinEdge] = useState(0);
  const [confidence, setConfidence] = useState<Confidence | "All">("All");
  const [markets, setMarkets] = useState<Set<string>>(new Set());
  const [expandedWeeks, setExpandedWeeks] = useState<Set<string>>(new Set());

  const marketOptions = useMemo(() => {
    if (!detail) return [];
    return Array.from(new Set(detail.picks.map((p) => p.market_label))).sort();
  }, [detail]);

  const filteredPicks = useMemo(() => {
    if (!detail) return [];
    return detail.picks.filter(
      (p) =>
        (minEdge <= 0 || p.edge >= minEdge) &&
        (confidence === "All" || p.confidence === confidence) &&
        (markets.size === 0 || markets.has(p.market_label))
    );
  }, [detail, minEdge, confidence, markets]);

  const filteredSummary = useMemo(() => {
    const n = filteredPicks.length;
    const hits = filteredPicks.filter((p) => p.hit).length;
    const unitResults = filteredPicks.map((p) => pickUnits(p.price, p.hit)).filter((u): u is number => u !== null);
    return {
      n,
      hits,
      hitRate: n > 0 ? hits / n : 0,
      units: unitResults.length > 0 ? unitResults.reduce((a, b) => a + b, 0) : null,
      pricedPicks: unitResults.length,
    };
  }, [filteredPicks]);

  const weekGroups = useMemo(() => groupByWeek(filteredPicks), [filteredPicks]);
  const filtersActive = minEdge > 0 || confidence !== "All" || markets.size > 0;

  function toggleWeek(key: string) {
    setExpandedWeeks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleMarket(m: string) {
    setMarkets((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else next.add(m);
      return next;
    });
  }

  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 sm:items-center" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl dark:bg-slate-900 sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <h2 className="text-xl font-bold">Track record</h2>
          <button
            onClick={onClose}
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
          <strong>{pct(overall.hit_rate)}</strong> of game bets have hit ({overall.hits}/{overall.picks})
          {trackRecord.weeks_graded > 0 && (
            <>
              {" "}
              across {trackRecord.weeks_graded} graded {trackRecord.weeks_graded === 1 ? "week" : "weeks"}
            </>
          )}
          {trackRecord.week_in_progress &&
            (trackRecord.weeks_graded > 0 ? " plus this week's games as they finish" : " so far this week")}
          {trackRecord.weeks_graded < 4 && " — still an early sample"}
          {overall.priced_picks > 0 && (
            <>
              {" · "}
              <strong>{formatUnits(overall.units)}</strong> on a flat 1-unit-per-pick basis
              {overall.priced_picks < overall.picks && ` (${overall.priced_picks} priced picks)`}
            </>
          )}
          {CONFIDENCE_TIERS.some((tier) => trackRecord.by_confidence[tier]) && (
            <>
              {" · "}
              {CONFIDENCE_TIERS.filter((tier) => trackRecord.by_confidence[tier])
                .map((tier) => `${tier} ${pct(trackRecord.by_confidence[tier]!.hit_rate)}`)
                .join(" · ")}
            </>
          )}
        </div>

        {loading && (
          <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">Loading graded bets…</p>
        )}
        {error && (
          <p className="py-4 text-sm text-red-600 dark:text-red-400">Couldn't load bet details ({error}).</p>
        )}

        {detail && (
          <>
            <div className="mb-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">
                    Min. edge: {(minEdge * 100).toFixed(0)}%
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={0.25}
                    step={0.01}
                    value={minEdge}
                    onChange={(e) => setMinEdge(Number(e.target.value))}
                    className="mt-2"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">Confidence</span>
                  <select
                    value={confidence}
                    onChange={(e) => setConfidence(e.target.value as Confidence | "All")}
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
                    onClick={() => setMarkets(new Set())}
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

            {filtersActive && (
              <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
                {filteredSummary.n > 0 ? (
                  <>
                    <strong>{pct(filteredSummary.hitRate)}</strong> of matching bets have hit (
                    {filteredSummary.hits}/{filteredSummary.n})
                    {filteredSummary.pricedPicks > 0 && (
                      <>
                        {" · "}
                        <strong>{formatUnits(filteredSummary.units)}</strong>
                      </>
                    )}
                  </>
                ) : (
                  "No graded bets match these filters."
                )}
              </div>
            )}

            <div className="space-y-2">
              {weekGroups.map((g) => {
                const key = `${g.season}-${g.week}`;
                const expanded = expandedWeeks.has(key);
                const hitRate = g.picks.length > 0 ? g.hits / g.picks.length : 0;
                return (
                  <div
                    key={key}
                    className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800"
                  >
                    <button
                      onClick={() => toggleWeek(key)}
                      className="flex w-full items-center justify-between gap-2 bg-slate-50 px-3 py-2 text-left text-sm font-medium hover:bg-slate-100 dark:bg-slate-900/60 dark:hover:bg-slate-800"
                    >
                      <span>
                        Week {g.week}, {g.season}
                      </span>
                      <span className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                        {pct(hitRate)} ({g.hits}/{g.picks.length})
                        <span className="text-xs">{expanded ? "▾" : "▸"}</span>
                      </span>
                    </button>

                    {expanded && (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800 dark:text-slate-400">
                              <th className="py-1.5 pl-3 pr-2">Matchup</th>
                              <th className="py-1.5 pr-2">Segment</th>
                              <th className="py-1.5 pr-2">Pick</th>
                              <th className="py-1.5 pr-2">Edge</th>
                              <th className="py-1.5 pr-2">Score</th>
                              <th className="py-1.5 pr-2">Result</th>
                            </tr>
                          </thead>
                          <tbody>
                            {g.picks.map((p, i) => (
                              <tr key={i} className="border-b border-slate-100 last:border-0 dark:border-slate-800/60">
                                <td className="py-1.5 pl-3 pr-2">{p.matchup}</td>
                                <td className="py-1.5 pr-2">{p.segment_label}</td>
                                <td className="py-1.5 pr-2">{p.side_label}</td>
                                <td className="py-1.5 pr-2">{pct(p.edge)}</td>
                                <td className="py-1.5 pr-2">{actualLabel(p)}</td>
                                <td
                                  className={`py-1.5 pr-2 font-medium ${
                                    p.hit
                                      ? "text-emerald-600 dark:text-emerald-400"
                                      : "text-red-500 dark:text-red-400"
                                  }`}
                                >
                                  {p.hit ? "Hit" : "Miss"}
                                  {p.margin !== null && (
                                    <span className="ml-1 font-normal text-slate-400 dark:text-slate-500">
                                      ({p.hit ? "by " : "missed by "}
                                      {Math.abs(p.margin)})
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
