import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Prop } from "../lib/types";
import { formatBook, formatLine, formatOdds, formatPct, formatPctWithOdds } from "../lib/format";
import { isBinaryMarket, sideBook, sideEdge, sideImpliedProb, sideModelProb, sidePrice } from "../lib/odds";

const BAR_UP = "#22c55e";
const BAR_DOWN = "#94a3b8";

const AGREEMENT_LABEL: Record<"strong" | "moderate" | "split", string> = {
  strong: "agrees",
  moderate: "roughly agrees",
  split: "disagrees",
};

export default function PropDetail({ prop, onClose }: { prop: Prop; onClose: () => void }) {
  const side = prop.recommended_side;
  const binary = isBinaryMarket(prop);
  const chartData = [...prop.recent_games]
    .reverse()
    .map((g) => ({ label: `W${g.week}${g.season !== prop.recent_games[0].season ? ` '${String(g.season).slice(2)}` : ""} vs ${g.opponent_team}`, value: g.value }));

  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 sm:items-center" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl dark:bg-slate-900 sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold">{prop.player_name}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {prop.position} &middot; {prop.team} vs {prop.opponent} &middot; {prop.market_label}
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

        {prop.injury_status && (
          <div className="mb-5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
            <strong>{prop.injury_status}</strong> on this week's injury report &mdash; the
            projection below is based on past performance and doesn't know that, so treat this
            recommendation with extra caution until game status is confirmed.
          </div>
        )}

        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Line" value={formatLine(prop.line)} />
          <Stat label="Projection" value={prop.projected_value.toString()} />
          <Stat label={`${binary ? "Yes" : side.toUpperCase()} odds`} value={formatOdds(sidePrice(prop, side))} />
          <Stat label="Source" value={formatBook(sideBook(prop, side))} />
          <Stat label="Edge" value={formatPct(sideEdge(prop, side))} highlight />
          <Stat label="Model probability" value={formatPctWithOdds(sideModelProb(prop, side))} />
          <Stat label="Book implied (no-vig)" value={formatPct(sideImpliedProb(prop, side))} />
          <Stat label="Opponent factor" value={`${prop.defense_factor}x`} />
          <Stat label="Confidence" value={`${prop.confidence} (${prop.sample_games}g)`} />
          {prop.espn_projected_value !== null && (
            <Stat
              label="ESPN 2nd opinion"
              value={`${prop.espn_projected_value} (${AGREEMENT_LABEL[prop.espn_agreement ?? "moderate"]})`}
              highlight={prop.espn_agreement === "strong"}
            />
          )}
        </div>

        {prop.trends.length > 0 && (
          <div className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900 dark:bg-emerald-950/30">
            <p className="mb-1.5 text-xs font-medium text-emerald-800 dark:text-emerald-300">
              Notable trends
            </p>
            <ul className="space-y-1 text-sm text-emerald-900 dark:text-emerald-200">
              {prop.trends.map((trend, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-0.5">&#8226;</span>
                  <span>{trend}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {!binary && chartData.length > 0 && (
          <div className="h-56 w-full">
            <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">
              Recent games vs. line
            </p>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-800" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-30} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  formatter={(value: number) => [value, prop.market_label]}
                />
                {prop.line !== null && (
                  <ReferenceLine
                    y={prop.line}
                    stroke="#f59e0b"
                    strokeDasharray="4 4"
                    label={{ value: `Line ${prop.line}`, fontSize: 11, fill: "#f59e0b", position: "right" }}
                  />
                )}
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={prop.line !== null && d.value > prop.line ? BAR_UP : BAR_DOWN} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {binary && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Anytime TD is modeled as a scoring rate over recent games, adjusted for the
            opponent's touchdowns allowed, rather than a single-game distribution.
          </p>
        )}
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
