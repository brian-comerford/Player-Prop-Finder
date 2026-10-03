import { useMemo, useState } from "react";
import type { Confidence, GradedPick, TrackRecord, TrackRecordDetail } from "../lib/types";
import { pillClass } from "../lib/format";
import { useLockBodyScroll } from "../lib/useLockBodyScroll";

const CONFIDENCE_TIERS: Confidence[] = ["High", "Medium", "Low"];
const CONFIDENCE_OPTIONS: Array<Confidence | "All"> = ["All", "High", "Medium", "Low"];

interface WeekGroup {
  season: number;
  week: number;
  picks: GradedPick[];
  hits: number;
}

function pct(hitRate: number): string {
  return `${Math.round(hitRate * 100)}%`;
}

function pickLabel(p: GradedPick): string {
  if (p.line === null) return p.side === "over" ? "Anytime TD" : "No TD";
  return `${p.side === "over" ? "Over" : "Under"} ${p.line}`;
}

function actualLabel(p: GradedPick): string {
  if (p.line === null) return p.actual_value > 0 ? "TD" : "No TD";
  return p.actual_value.toString();
}

// detail.picks arrives sorted most-recent-week-first; grouping preserves
// that order without re-sorting.
function groupByWeek(picks: GradedPick[]): WeekGroup[] {
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

export default function TrackRecordSection({
  trackRecord,
  fetchDetail,
  label = "Track record",
}: {
  trackRecord: TrackRecord | null;
  fetchDetail: () => Promise<TrackRecordDetail>;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<TrackRecordDetail | null>(null);
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
        {label}: {pct(overall.hit_rate)} ({overall.hits}/{overall.picks})
      </button>

      {open && (
        <TrackRecordPanel
          trackRecord={trackRecord}
          detail={detail}
          loading={loading}
          error={error}
          label={label}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}

function TrackRecordPanel({
  trackRecord,
  detail,
  loading,
  error,
  label,
  onClose,
}: {
  trackRecord: TrackRecord;
  detail: TrackRecordDetail | null;
  loading: boolean;
  error: string | null;
  label: string;
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
        // minEdge at its floor (0%) means "no edge filter" -- some graded
        // picks carry a negative edge (the model still grades whichever
        // side it liked better even when neither side looked profitable),
        // and those should still count by default so the unfiltered
        // totals here match the overall summary above, not silently drop
        // picks before the user has touched the slider.
        (minEdge <= 0 || p.edge >= minEdge) &&
        (confidence === "All" || p.confidence === confidence) &&
        // No bet types selected means "All" -- same as before this was
        // multi-select, just expressed as an empty set instead of a
        // sentinel string.
        (markets.size === 0 || markets.has(p.market_label))
    );
  }, [detail, minEdge, confidence, markets]);

  const filteredSummary = useMemo(() => {
    const n = filteredPicks.length;
    const hits = filteredPicks.filter((p) => p.hit).length;
    return { n, hits, hitRate: n > 0 ? hits / n : 0 };
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
          <h2 className="text-xl font-bold">{label}</h2>
          <button
            onClick={onClose}
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
          <strong>{pct(overall.hit_rate)}</strong> of picks have hit ({overall.hits}/{overall.picks})
          {trackRecord.weeks_graded > 0 && (
            <>
              {" "}
              across {trackRecord.weeks_graded} graded {trackRecord.weeks_graded === 1 ? "week" : "weeks"}
            </>
          )}
          {trackRecord.week_in_progress &&
            (trackRecord.weeks_graded > 0 ? " plus this week's games as they finish" : " so far this week")}
          {trackRecord.weeks_graded < 4 && " — still an early sample"}
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
          <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">Loading graded picks…</p>
        )}
        {error && (
          <p className="py-4 text-sm text-red-600 dark:text-red-400">Couldn't load pick details ({error}).</p>
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
                    <strong>{pct(filteredSummary.hitRate)}</strong> of matching picks have hit (
                    {filteredSummary.hits}/{filteredSummary.n})
                  </>
                ) : (
                  "No graded picks match these filters."
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
                              <th className="py-1.5 pl-3 pr-2">Player</th>
                              <th className="py-1.5 pr-2">Market</th>
                              <th className="py-1.5 pr-2">Pick</th>
                              <th className="py-1.5 pr-2">Edge</th>
                              <th className="py-1.5 pr-2">Actual</th>
                              <th className="py-1.5 pr-2">Result</th>
                            </tr>
                          </thead>
                          <tbody>
                            {g.picks.map((p, i) => (
                              <tr key={i} className="border-b border-slate-100 last:border-0 dark:border-slate-800/60">
                                <td className="py-1.5 pl-3 pr-2">
                                  {p.player_name}
                                  <span className="text-slate-400 dark:text-slate-500">
                                    {" "}
                                    · {p.team} vs {p.opponent}
                                  </span>
                                </td>
                                <td className="py-1.5 pr-2">{p.market_label}</td>
                                <td className="py-1.5 pr-2">{pickLabel(p)}</td>
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
