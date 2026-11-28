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
    <>
      <ul className="space-y-2 sm:hidden">
        {props.map((p) => (
          <GameCard key={gamePropKey(p)} prop={p} onSelect={() => onSelect(p)} />
        ))}
      </ul>
    {/* Kept in the DOM on phones (hidden) for the Save image export. */}
    <div className="hidden overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 sm:block">
      <table className="w-full min-w-[780px] border-collapse text-sm tabular-nums">
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
    </>
  );
}

function GameCard({ prop: p, onSelect }: { prop: GameProp; onSelect: () => void }) {
  const side = p.recommended_side;
  const edge = sideEdge(p, side);
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className="press-subtle block w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-left active:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:active:bg-slate-800/60"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate font-semibold tracking-tight">{p.matchup}</div>
            <div className="truncate text-xs text-slate-500 dark:text-slate-400">
              {p.segment_label} &middot; {p.time_slot ?? p.game_date}
            </div>
          </div>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColorClass(p.confidence)}`}>
            {p.confidence}
          </span>
        </div>
        <div className="mt-2.5 flex items-baseline justify-between gap-2">
          <div className="min-w-0 text-[15px]">
            <span className="font-semibold">{sideLabel(p, side)}</span>{" "}
            <span className="text-slate-600 dark:text-slate-300">{p.market_label}</span>
          </div>
          <div className="shrink-0 text-right">
            <span className="font-semibold tabular-nums">{formatOdds(sidePrice(p, side))}</span>{" "}
            <span className="text-xs text-slate-500 dark:text-slate-400">{formatBook(sideBook(p, side))}</span>
          </div>
        </div>
        <dl className="mt-2 grid grid-cols-3 gap-2 text-xs tabular-nums">
          <div>
            <dt className="text-slate-500 dark:text-slate-400">Model</dt>
            <dd className="font-medium">{formatPct(sideModelProb(p, side))}</dd>
          </div>
          <div>
            <dt className="text-slate-500 dark:text-slate-400">Book</dt>
            <dd className="font-medium">{formatPct(sideImpliedProb(p, side))}</dd>
          </div>
          <div>
            <dt className="text-slate-500 dark:text-slate-400">Edge</dt>
            <dd className={`font-semibold ${edgeColorClass(edge ?? 0)}`}>{formatPct(edge)}</dd>
          </div>
        </dl>
      </button>
    </li>
  );
}
