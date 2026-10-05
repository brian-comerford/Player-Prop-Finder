import type { Prop } from "./types";

export function sidePrice(prop: Prop, side: "over" | "under"): number | null {
  return side === "over" ? prop.price_over : prop.price_under;
}

export function sideBook(prop: Prop, side: "over" | "under"): string | null {
  return side === "over" ? prop.book_over : prop.book_under;
}

export function sideEdge(prop: Prop, side: "over" | "under"): number | null {
  return side === "over" ? prop.edge_over : prop.edge_under;
}

export function sideModelProb(prop: Prop, side: "over" | "under"): number {
  return side === "over" ? prop.model_prob_over : prop.model_prob_under;
}

export function sideImpliedProb(prop: Prop, side: "over" | "under"): number | null {
  return side === "over" ? prop.implied_prob_over : prop.implied_prob_under;
}

export function isBinaryMarket(prop: Prop): boolean {
  return prop.market === "player_anytime_td";
}

// Mirrors scripts/common.py's pick_units -- profit/loss in units for a
// flat 1-unit bet at this price, or null if the price is unknown (a pick
// graded before prices were recorded).
export function pickUnits(price: number | null, hit: boolean): number | null {
  if (price === null) return null;
  if (!hit) return -1;
  return price > 0 ? price / 100 : 100 / -price;
}

// Total units won across a set of graded picks (player or game), plus how
// many of them actually had a recorded price -- units stays null when
// none do, rather than reporting a misleading 0, same convention as the
// server-side HitRateSummary.
export function sumUnits<T extends { price: number | null; hit: boolean }>(
  picks: T[]
): { units: number | null; pricedPicks: number } {
  const results = picks.map((p) => pickUnits(p.price, p.hit)).filter((u): u is number => u !== null);
  return {
    units: results.length > 0 ? results.reduce((a, b) => a + b, 0) : null,
    pricedPicks: results.length,
  };
}

// Mirrors scripts/common.py's prob_to_american -- the American odds that
// would exactly imply a given probability with no vig, e.g. 50% -> -100,
// 40% -> +150. Used to show the model's own probability in odds terms
// alongside the book's actual price, for a like-for-like comparison.
export function probToAmericanOdds(p: number | null): number | null {
  if (p === null || Number.isNaN(p)) return null;
  const clamped = Math.min(Math.max(p, 0.01), 0.99);
  return clamped >= 0.5
    ? Math.round((-100 * clamped) / (1 - clamped))
    : Math.round((100 * (1 - clamped)) / clamped);
}
