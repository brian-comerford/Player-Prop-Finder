import { Fragment, useEffect, useState } from "react";
import type { Prop } from "../lib/types";
import {
  confidenceColorClass,
  edgeColorClass,
  formatBook,
  formatLine,
  formatOdds,
  formatPct,
  formatPctWithOdds,
} from "../lib/format";
import { useMediaQuery } from "../lib/useMediaQuery";
import { ChevronIcon } from "./Icons";
import { isBinaryMarket, sideBook, sideEdge, sideImpliedProb, sideModelProb, sidePrice } from "../lib/odds";

function propKey(p: Prop): string {
  // The same player/market can appear once per book (e.g. a DraftKings
  // line and a separate Kalshi line), so the book has to be part of the
  // key or those rows collide.
  return `${p.player_name}-${p.market}-${p.book_over}`;
}

// Phones get the list in batches: a full slate is ~1,000 props, far more
// than anyone scrolls through, and rendering every card up front makes the
// page slow to open on a phone.
const CARD_BATCH = 40;

export default function PropsTable({
  props,
  onSelect,
  showConfidence = true,
  onResetFilters,
  forceTable = false,
}: {
  props: Prop[];
  onSelect: (prop: Prop) => void;
  // Off for Anytime TD, which carries no confidence rating.
  showConfidence?: boolean;
  // Offered from the empty state.
  onResetFilters?: () => void;
  // Render the (hidden) table on phones too -- Save image exports it.
  forceTable?: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const wide = useMediaQuery("(min-width: 640px)");
  const [visible, setVisible] = useState(CARD_BATCH);
  useEffect(() => setVisible(CARD_BATCH), [props]);

  if (props.length === 0) {
    return <EmptyState noun="props" onReset={onResetFilters} />;
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
    <>
      {!wide && (
      <>
      <ul className="space-y-2">
        {props.slice(0, visible).map((p) => {
          const key = propKey(p);
          return (
            <PropCard
              key={key}
              prop={p}
              showConfidence={showConfidence}
              expanded={expanded.has(key)}
              onToggle={() => toggleExpanded(key)}
              onSelect={() => onSelect(p)}
            />
          );
        })}
      </ul>
      {visible < props.length && (
        <ShowMore
          remaining={props.length - visible}
          batch={CARD_BATCH}
          onClick={() => setVisible((v) => v + CARD_BATCH)}
        />
      )}
      </>
      )}
    {(wide || forceTable) && (
    <div className={`overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 ${wide ? "" : "hidden"}`}>
      <table className="w-full min-w-[840px] border-collapse text-sm tabular-nums">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-100 text-left text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <th className="px-3 py-2 font-medium">Player</th>
            <th className="px-3 py-2 font-medium">Market</th>
            <th className="px-3 py-2 font-medium">Line</th>
            <th className="px-3 py-2 font-medium">Pick</th>
            <th className="px-3 py-2 font-medium">Book</th>
            <th className="px-3 py-2 font-medium">Odds</th>
            <th className="px-3 py-2 font-medium">Model %</th>
            <th className="px-3 py-2 font-medium">Book %</th>
            <th className="px-3 py-2 font-medium">Edge</th>
            {showConfidence && <th className="px-3 py-2 font-medium">Confidence</th>}
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
                          <ChevronIcon
                            className={`transition-transform duration-200 ease-[var(--ease-out)] ${isExpanded ? "rotate-90" : ""}`}
                          />
                        </button>
                      ) : (
                        <span className="h-5 w-5 shrink-0" aria-hidden="true" />
                      )}
                      <div>
                        <div className="flex items-center gap-1.5 font-medium">
                          {p.player_name}
                          {p.injury_status && (
                            <span
                              title={p.injury_status}
                              aria-label={p.injury_status}
                              className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                            >
                              Q
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {p.position} &middot; {p.team} vs {p.opponent}
                          {p.time_slot && <> &middot; {p.time_slot}</>}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2">{p.market_label}</td>
                  <td className="px-3 py-2">{formatLine(p.line)}</td>
                  <td className="px-3 py-2 uppercase">{binary ? "Yes" : side}</td>
                  <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                    {formatBook(sideBook(p, side))}
                  </td>
                  <td className="px-3 py-2">{formatOdds(sidePrice(p, side))}</td>
                  <td className="px-3 py-2">{formatPctWithOdds(sideModelProb(p, side))}</td>
                  <td className="px-3 py-2">{formatPct(sideImpliedProb(p, side))}</td>
                  <td className={`px-3 py-2 ${edgeColorClass(sideEdge(p, side) ?? 0)}`}>
                    {formatPct(sideEdge(p, side))}
                  </td>
                  {showConfidence && (
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColorClass(p.confidence)}`}
                      >
                        {p.confidence}
                        {binary && <> &middot; {p.sample_games}g</>}
                      </span>
                    </td>
                  )}
                </tr>
                {hasTrends && isExpanded && (
                  <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-800/60 dark:bg-slate-900/40">
                    <td colSpan={showConfidence ? 10 : 9} className="px-3 py-2 pl-11">
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
    )}
    </>
  );
}

export function EmptyState({ noun, onReset }: { noun: string; onReset?: () => void }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center dark:border-slate-700">
      <p className="font-medium text-slate-700 dark:text-slate-200">No {noun} match these filters</p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Lowering the minimum edge or clearing a market or book usually brings some back.
      </p>
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="press mt-4 h-11 rounded-lg bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white sm:h-9"
        >
          Reset filters
        </button>
      )}
    </div>
  );
}

export function ShowMore({ remaining, batch, onClick }: { remaining: number; batch: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="press mt-2 h-11 w-full rounded-xl border border-slate-300 bg-white text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
    >
      Show {Math.min(batch, remaining)} more <span className="tabular-nums text-slate-500 dark:text-slate-400">({remaining} left)</span>
    </button>
  );
}

// The phone layout: one tappable card per prop, the pick and its price up
// top, the numbers behind it in a single row underneath.
function PropCard({
  prop: p,
  showConfidence,
  expanded,
  onToggle,
  onSelect,
}: {
  prop: Prop;
  showConfidence: boolean;
  expanded: boolean;
  onToggle: () => void;
  onSelect: () => void;
}) {
  const side = p.recommended_side;
  const binary = isBinaryMarket(p);
  const edge = sideEdge(p, side);
  return (
    <li className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect();
          }
        }}
        className="press-subtle block cursor-pointer px-3.5 py-3 active:bg-slate-50 dark:active:bg-slate-800/60"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 font-semibold tracking-tight">
              <span className="truncate">{p.player_name}</span>
              {p.injury_status && (
                // Spelled out: a title tooltip never shows on a touch screen.
                <span className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                  {p.injury_status}
                </span>
              )}
            </div>
            <div className="truncate text-xs text-slate-500 dark:text-slate-400">
              {p.position} &middot; {p.team} vs {p.opponent}
              {p.time_slot && <> &middot; {p.time_slot}</>}
            </div>
          </div>
          {showConfidence && (
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColorClass(p.confidence)}`}
            >
              {p.confidence}
            </span>
          )}
        </div>

        <div className="mt-2.5 flex items-baseline justify-between gap-2">
          <div className="min-w-0 text-[15px]">
            <span className="font-semibold uppercase">{binary ? "Yes" : side}</span>{" "}
            {!binary && <span className="font-semibold tabular-nums">{formatLine(p.line)}</span>}{" "}
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
      </div>

      {p.trends.length > 0 && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            className="flex min-h-[44px] w-full items-center gap-1.5 px-3.5 text-xs font-medium text-emerald-700 active:bg-slate-50 dark:text-emerald-400 dark:active:bg-slate-800/60"
          >
            <ChevronIcon
              className={`transition-transform duration-200 ease-[var(--ease-out)] ${expanded ? "rotate-90" : ""}`}
            />
            {p.trends.length} notable {p.trends.length === 1 ? "trend" : "trends"}
          </button>
          {expanded && (
            <ul className="reveal space-y-1 px-3.5 pb-3 text-xs text-slate-600 dark:text-slate-400">
              {p.trends.map((trend, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-0.5 text-emerald-500">&#8226;</span>
                  <span>{trend}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}
