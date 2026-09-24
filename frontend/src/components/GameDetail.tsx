import type { GameProp } from "../lib/types";
import { formatBook, formatOdds, formatPct, formatPctWithOdds } from "../lib/format";
import { sideBook, sideEdge, sideImpliedProb, sideLabel, sideModelProb, sidePrice } from "../lib/gameOdds";

export default function GameDetail({ prop, onClose }: { prop: GameProp; onClose: () => void }) {
  const side = prop.recommended_side;

  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 sm:items-center" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl dark:bg-slate-900 sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold">{prop.matchup}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {prop.segment_label} &middot; {prop.market_label}
              {prop.time_slot && <> &middot; {prop.time_slot}</>}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Pick" value={sideLabel(prop, side)} />
          <Stat label="Odds" value={formatOdds(sidePrice(prop, side))} />
          <Stat label="Source" value={formatBook(sideBook(prop, side))} />
          <Stat label="Edge" value={formatPct(sideEdge(prop, side))} highlight />
          <Stat label="Model probability" value={formatPctWithOdds(sideModelProb(prop, side))} />
          <Stat label="Book implied (no-vig)" value={formatPct(sideImpliedProb(prop, side))} />
          <Stat label="Confidence" value={prop.confidence} />
          <Stat
            label="Sample size"
            value={`${prop.home_team} ${prop.sample_games_home}g / ${prop.away_team} ${prop.sample_games_away}g`}
          />
        </div>

        <div className="mb-5 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/60">
          <p className="mb-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            Model's own projection for this segment
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={`${prop.home_team} points`} value={prop.model_home_points.toString()} />
            <Stat label={`${prop.away_team} points`} value={prop.model_away_points.toString()} />
            <Stat label="Model total" value={prop.model_total.toString()} />
            <Stat
              label="Model margin"
              value={
                prop.model_margin_home >= 0
                  ? `${prop.home_team} +${prop.model_margin_home}`
                  : `${prop.away_team} +${Math.abs(prop.model_margin_home)}`
              }
            />
          </div>
        </div>

        <p className="text-sm text-slate-500 dark:text-slate-400">
          Projected from each team's own recency-weighted scoring rate (rushing TDs, passing TDs,
          field goals) adjusted for what the opponent's defense has allowed, the same
          matchup-factor approach used for player props &mdash; see the Info tab for how the
          model probability above is derived from that projection.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-100 p-2.5 dark:bg-slate-800">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`text-sm font-semibold ${highlight ? "text-emerald-600 dark:text-emerald-400" : ""}`}>
        {value}
      </div>
    </div>
  );
}
