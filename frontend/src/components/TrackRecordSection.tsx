import { useState } from "react";
import { fetchTrackRecordDetail } from "../lib/data";
import type { Confidence, GradedPick, TrackRecord, TrackRecordDetail } from "../lib/types";
import { useLockBodyScroll } from "../lib/useLockBodyScroll";

const CONFIDENCE_TIERS: Confidence[] = ["High", "Medium", "Low"];

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

export default function TrackRecordSection({ trackRecord }: { trackRecord: TrackRecord | null }) {
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
      fetchTrackRecordDetail()
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
      </button>

      {open && (
        <TrackRecordPanel
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

function TrackRecordPanel({
  trackRecord,
  detail,
  loading,
  error,
  onClose,
}: {
  trackRecord: TrackRecord;
  detail: TrackRecordDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  useLockBodyScroll();
  const overall = trackRecord.overall!;

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
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  <th className="py-1.5 pr-2">Wk</th>
                  <th className="py-1.5 pr-2">Player</th>
                  <th className="py-1.5 pr-2">Market</th>
                  <th className="py-1.5 pr-2">Pick</th>
                  <th className="py-1.5 pr-2">Actual</th>
                  <th className="py-1.5 pr-2">Result</th>
                </tr>
              </thead>
              <tbody>
                {detail.picks.map((p, i) => (
                  <tr key={i} className="border-b border-slate-100 dark:border-slate-800/60">
                    <td className="py-1.5 pr-2 text-slate-500 dark:text-slate-400">{p.week}</td>
                    <td className="py-1.5 pr-2">
                      {p.player_name}
                      <span className="text-slate-400 dark:text-slate-500">
                        {" "}
                        · {p.team} vs {p.opponent}
                      </span>
                    </td>
                    <td className="py-1.5 pr-2">{p.market_label}</td>
                    <td className="py-1.5 pr-2">{pickLabel(p)}</td>
                    <td className="py-1.5 pr-2">{actualLabel(p)}</td>
                    <td
                      className={`py-1.5 pr-2 font-medium ${
                        p.hit ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"
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
    </div>
  );
}
