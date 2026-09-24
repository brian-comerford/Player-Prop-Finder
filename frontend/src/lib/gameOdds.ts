import type { GameProp, GameSide } from "./types";

export function sideLabel(prop: GameProp, side: GameSide): string {
  return side === "a" ? prop.side_a_label : prop.side_b_label;
}

export function sidePrice(prop: GameProp, side: GameSide): number | null {
  return side === "a" ? prop.price_a : prop.price_b;
}

export function sideBook(prop: GameProp, side: GameSide): string | null {
  return side === "a" ? prop.book_a : prop.book_b;
}

export function sideEdge(prop: GameProp, side: GameSide): number | null {
  return side === "a" ? prop.edge_a : prop.edge_b;
}

export function sideModelProb(prop: GameProp, side: GameSide): number {
  return side === "a" ? prop.model_prob_a : prop.model_prob_b;
}

export function sideImpliedProb(prop: GameProp, side: GameSide): number | null {
  return side === "a" ? prop.implied_prob_a : prop.implied_prob_b;
}
