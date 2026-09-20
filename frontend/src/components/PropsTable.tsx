import { Fragment, useState } from "react";
import type { Prop } from "../lib/types";
import { confidenceColorClass, edgeColorClass, formatLine, formatOdds, formatPct } from "../lib/format";
import { isBinaryMarket, sideEdge, sideImpliedProb, sideModelProb, sidePrice } from "../lib/odds";

function propKey(p: Prop): string {
  return `${p.player_name}-${p.market}`;
}

export default function PropsTable({
  props,
  onSelect,
}: {
  props: Prop[];
  onSelect: (prop: Prop) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (props.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No props match the current filters. Try lowering the minimum edge.
      </div>
    );
  }

  const toggleExpanded = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

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
            const key = propKey(p);
            const hasTrends = p.trends.length > 0;
            const isExpanded = expanded.has(key);
            return (
              <Fragment key={key}>
                <tr
                  onClick={() => onSelect(p)}
                  className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 dark:border-slate-800/60 dark:hover:bg-slate-900/60"
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      {hasTrends ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleExpanded(key);
                          }}
                          aria-label={isExpanded ? "Hide trends" : "Show trends"}
                          aria-expanded={isExpanded}
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-400 hover:bg-slate-200 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                        >
                          <span
                            className={`inline-block text-xs transition-transform ${isExpanded ? "rotate-90" : ""}`}
                          >
                            &#9656;
                          </span>
                        </button>
                      ) : (
                        <span className="h-5 w-5 shrink-0" aria-hidden="true" />
                      )}
                      <div>
                        <div className="font-medium">{p.player_name}</div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {p.position} &middot; {p.team} vs {p.opponent}
                        </div>
                      </div>
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
                {hasTrends && isExpanded && (
                  <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-800/60 dark:bg-slate-900/40">
                    <td colSpan={9} className="px-3 py-2 pl-11">
                      <ul className="space-y-1 text-xs text-slate-600 dark:text-slate-400">
                        {p.trends.map((trend, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <span className="mt-0.5 text-emerald-500">&#8226;</span>
                            <span>{trend}</span>
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
