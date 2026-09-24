import type { GameProp } from "../lib/types";
import { confidenceColorClass, edgeColorClass, formatBook, formatOdds, formatPct, formatPctWithOdds } from "../lib/format";
import { sideBook, sideEdge, sideImpliedProb, sideLabel, sideModelProb, sidePrice } from "../lib/gameOdds";

function gamePropKey(p: GameProp): string {
  return `${p.matchup}-${p.segment}-${p.market}-${p.book_a}`;
}

export default function GamesTable({
  props,
  onSelect,
}: {
  props: GameProp[];
  onSelect: (prop: GameProp) => void;
}) {
  if (props.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No game bets match the current filters. Try lowering the minimum edge.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="w-full min-w-[780px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-100 text-left text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <th className="px-3 py-2 font-medium">Matchup</th>
            <th className="px-3 py-2 font-medium">Segment</th>
            <th className="px-3 py-2 font-medium">Market</th>
            <th className="px-3 py-2 font-medium">Pick</th>
            <th className="px-3 py-2 font-medium">Book</th>
            <th className="px-3 py-2 font-medium">Odds</th>
            <th className="px-3 py-2 font-medium">Model %</th>
            <th className="px-3 py-2 font-medium">Book %</th>
            <th className="px-3 py-2 font-medium">Edge</th>
            <th className="px-3 py-2 font-medium">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {props.map((p) => {
            const side = p.recommended_side;
            return (
              <tr
                key={gamePropKey(p)}
                onClick={() => onSelect(p)}
                className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 dark:border-slate-800/60 dark:hover:bg-slate-900/60"
              >
                <td className="px-3 py-2">
                  <div className="font-medium">{p.matchup}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {p.time_slot ?? p.game_date}
                  </div>
                </td>
                <td className="px-3 py-2">{p.segment_label}</td>
                <td className="px-3 py-2">{p.market_label}</td>
                <td className="px-3 py-2 font-medium">{sideLabel(p, side)}</td>
                <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                  {formatBook(sideBook(p, side))}
                </td>
                <td className="px-3 py-2">{formatOdds(sidePrice(p, side))}</td>
                <td className="px-3 py-2">{formatPctWithOdds(sideModelProb(p, side))}</td>
                <td className="px-3 py-2">{formatPct(sideImpliedProb(p, side))}</td>
                <td className={`px-3 py-2 ${edgeColorClass(sideEdge(p, side) ?? 0)}`}>
                  {formatPct(sideEdge(p, side))}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColorClass(p.confidence)}`}
                  >
                    {p.confidence}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
