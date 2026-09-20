import type { Prop } from "../lib/types";
import { confidenceColorClass, edgeColorClass, formatLine, formatOdds, formatPct } from "../lib/format";
import { isBinaryMarket, sideEdge, sideImpliedProb, sideModelProb, sidePrice } from "../lib/odds";

export default function PropsTable({
  props,
  onSelect,
}: {
  props: Prop[];
  onSelect: (prop: Prop) => void;
}) {
  if (props.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No props match the current filters. Try lowering the minimum edge.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="w-full min-w-[840px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-100 text-left text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <th className="px-3 py-2 font-medium">Player</th>
            <th className="px-3 py-2 font-medium">Market</th>
            <th className="px-3 py-2 font-medium">Line</th>
            <th className="px-3 py-2 font-medium">Pick</th>
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
            const binary = isBinaryMarket(p);
            return (
              <tr
                key={`${p.player_name}-${p.market}`}
                onClick={() => onSelect(p)}
                className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 dark:border-slate-800/60 dark:hover:bg-slate-900/60"
              >
                <td className="px-3 py-2">
                  <div className="font-medium">{p.player_name}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {p.position} &middot; {p.team} vs {p.opponent}
                  </div>
                </td>
                <td className="px-3 py-2">{p.market_label}</td>
                <td className="px-3 py-2">{formatLine(p.line)}</td>
                <td className="px-3 py-2 uppercase">{binary ? "Yes" : side}</td>
                <td className="px-3 py-2">{formatOdds(sidePrice(p, side))}</td>
                <td className="px-3 py-2">{formatPct(sideModelProb(p, side))}</td>
                <td className="px-3 py-2">{formatPct(sideImpliedProb(p, side))}</td>
                <td className={`px-3 py-2 ${edgeColorClass(sideEdge(p, side) ?? 0)}`}>
                  {formatPct(sideEdge(p, side))}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColorClass(p.confidence)}`}
                  >
                    {p.confidence} &middot; {p.sample_games}g
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
