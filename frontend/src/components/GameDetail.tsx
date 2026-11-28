import type { GameProp } from "../lib/types";
import { formatBook, formatOdds, formatPct, formatPctWithOdds } from "../lib/format";
import { sideBook, sideEdge, sideImpliedProb, sideLabel, sideModelProb, sidePrice } from "../lib/gameOdds";
import Sheet from "./Sheet";
import PickButton, { PickedNote } from "./PickButton";
import { gamePickKey, gameSnapshot, usePicks } from "../lib/usePicks";

export default function GameDetail({ prop, onClose }: { prop: GameProp; onClose: () => void }) {
  const side = prop.recommended_side;
  const { picks, toggle } = usePicks();
  const snapshot = picks[gamePickKey(prop)];

  return (
    <Sheet
      onClose={onClose}
      title={prop.matchup}
      subtitle={
        <>
          {prop.segment_label} &middot; {prop.market_label}
          {prop.time_slot && <> &middot; {prop.time_slot}</>}
        </>
      }
    >
      <div className="mb-5 space-y-2">
        <PickButton variant="block" picked={!!snapshot} onToggle={() => toggle(gamePickKey(prop), () => gameSnapshot(prop))} />
        {snapshot && (
          <PickedNote
            snapshot={snapshot}
            current={gameSnapshot(prop)}
          />
        )}
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
    </Sheet>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-100 p-2.5 dark:bg-slate-800">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${highlight ? "text-emerald-700 dark:text-emerald-400" : ""}`}>
        {value}
      </div>
    </div>
  );
}
