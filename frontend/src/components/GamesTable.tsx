import { useEffect, useState } from "react";
import type { GameProp } from "../lib/types";
import { useMediaQuery } from "../lib/useMediaQuery";
import { EmptyState, ShowMore } from "./PropsTable";
import PickButton, { PickedNote } from "./PickButton";
import { gamePickKey, gameSnapshot, usePicks, type PickSnapshot } from "../lib/usePicks";
import { confidenceColorClass, edgeColorClass, formatBook, formatOdds, formatPct, formatPctWithOdds } from "../lib/format";
import { sideBook, sideEdge, sideImpliedProb, sideLabel, sideModelProb, sidePrice } from "../lib/gameOdds";

function gamePropKey(p: GameProp): string {
  return `${p.matchup}-${p.segment}-${p.market}-${p.book_a}`;
}

const CARD_BATCH = 40;

export default function GamesTable({
  props,
  onSelect,
  onResetFilters,
  forceTable = false,
}: {
  props: GameProp[];
  onSelect: (prop: GameProp) => void;
  onResetFilters?: () => void;
  // Render the (hidden) table on phones too -- Save image exports it.
  forceTable?: boolean;
}) {
  const wide = useMediaQuery("(min-width: 640px)");
  const { picks, toggle: togglePick } = usePicks();
  const [visible, setVisible] = useState(CARD_BATCH);
  useEffect(() => setVisible(CARD_BATCH), [props]);

  if (props.length === 0) {
    return <EmptyState noun="game bets" onReset={onResetFilters} />;
  }

  return (
    <>
      {!wide && (
        <>
          <ul className="space-y-2">
            {props.slice(0, visible).map((p) => (
              <GameCard
                key={gamePropKey(p)}
                prop={p}
                onSelect={() => onSelect(p)}
                picks={picks}
                onTogglePick={() => togglePick(gamePickKey(p), () => gameSnapshot(p))}
              />
            ))}
          </ul>
          {visible < props.length && (
            <ShowMore remaining={props.length - visible} batch={CARD_BATCH} onClick={() => setVisible((v) => v + CARD_BATCH)} />
          )}
        </>
      )}
    {(wide || forceTable) && (
    <div className={`overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 ${wide ? "" : "hidden"}`}>
      <table className="w-full min-w-[780px] border-collapse text-sm tabular-nums">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-100 text-left text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <th className="whitespace-nowrap px-3 py-2 font-medium">Matchup</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Segment</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Market</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Pick</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Book</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Odds</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Model %</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Book %</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Edge</th>
            <th className="whitespace-nowrap px-3 py-2 font-medium">Confidence</th>
            <th className="w-px px-2 py-2 font-medium" data-export-hide>
              <span className="sr-only">Picked</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {props.map((p) => {
            const side = p.recommended_side;
            const pickKey = gamePickKey(p);
            const picked = !!picks[pickKey];
            return (
              <tr
                key={gamePropKey(p)}
                onClick={() => onSelect(p)}
                className={`cursor-pointer border-b border-slate-100 last:border-0 dark:border-slate-800/60 ${
                  picked
                    ? "bg-emerald-50/70 hover:bg-emerald-50 dark:bg-emerald-950/25 dark:hover:bg-emerald-950/40"
                    : "hover:bg-slate-50 dark:hover:bg-slate-900/60"
                }`}
              >
                <td className="px-3 py-2">
                  <div className="font-medium">{p.matchup}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {p.time_slot ?? p.game_date}
                  </div>
                </td>
                <td className="px-3 py-2">{p.segment_label}</td>
                <td className="whitespace-nowrap px-3 py-2">{p.market_label}</td>
                <td className="px-3 py-2 font-medium">{sideLabel(p, side)}</td>
                <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                  {formatBook(sideBook(p, side))}
                </td>
                <td className="px-3 py-2">{formatOdds(sidePrice(p, side))}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatPctWithOdds(sideModelProb(p, side))}</td>
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
                <td className="w-px px-2 py-2" data-export-hide>
                  <PickButton variant="icon" picked={picked} onToggle={() => togglePick(pickKey, () => gameSnapshot(p))} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    )}
    </>
  );
}

function GameCard({
  prop: p,
  onSelect,
  picks,
  onTogglePick,
}: {
  prop: GameProp;
  onSelect: () => void;
  picks: Record<string, PickSnapshot>;
  onTogglePick: () => void;
}) {
  const side = p.recommended_side;
  const edge = sideEdge(p, side);
  const snapshot = picks[gamePickKey(p)];
  const picked = !!snapshot;
  return (
    <li
      className={`overflow-hidden rounded-xl border bg-white dark:bg-slate-900 ${
        picked ? "border-emerald-500 dark:border-emerald-600" : "border-slate-200 dark:border-slate-800"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="press-subtle block w-full px-3.5 py-3 text-left active:bg-slate-50 dark:active:bg-slate-800/60"
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
      {snapshot && (
        <PickedNote
          snapshot={snapshot}
          current={gameSnapshot(p)}
          className="-mt-1 px-3.5 pb-2.5"
        />
      )}
      <div className="flex justify-end border-t border-slate-100 dark:border-slate-800">
        <PickButton variant="footer" picked={picked} onToggle={onTogglePick} />
      </div>
    </li>
  );
}
