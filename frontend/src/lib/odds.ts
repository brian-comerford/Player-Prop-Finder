import type { Prop } from "./types";

export function sidePrice(prop: Prop, side: "over" | "under"): number | null {
  return side === "over" ? prop.price_over : prop.price_under;
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
