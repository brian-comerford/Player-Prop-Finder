import { useCallback, useSyncExternalStore } from "react";
import type { GameProp, Prop } from "./types";
import { isBinaryMarket, sideBook, sidePrice } from "./odds";
import { sideBook as gameSideBook, sideLabel as gameSideLabel, sidePrice as gameSidePrice } from "./gameOdds";

// The bets someone has marked as taken, remembered in this browser
// (localStorage) so they're still marked on the next visit. Each entry
// keeps a snapshot of the pick as it was when marked, so a line or price
// that moves afterwards can be shown against what they actually got.
export interface PickSnapshot {
  label: string; // e.g. "UNDER 64.5 Receiving Yards"
  side: string;
  line: number | null;
  price: number | null;
  book: string | null;
  markedAt: string;
}

const STORAGE_KEY = "my-picks-v1";
// Old weeks' marks are dropped so the list doesn't grow forever.
const KEEP_DAYS = 21;

type PickMap = Record<string, PickSnapshot>;

function read(): PickMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as PickMap;
    const cutoff = Date.now() - KEEP_DAYS * 86_400_000;
    return Object.fromEntries(Object.entries(parsed).filter(([, p]) => Date.parse(p.markedAt) >= cutoff));
  } catch {
    return {};
  }
}

let current: PickMap = typeof window === "undefined" ? {} : read();
const listeners = new Set<() => void>();

function write(next: PickMap) {
  current = next;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage blocked (e.g. some private modes): marks still work for
    // this visit, they just won't be remembered.
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  // Keep other open tabs in step.
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      current = read();
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

// One mark per player + market + game: the same prop listed at two books
// is one bet, and a line that moves keeps its mark.
export function propPickKey(p: Prop): string {
  return `prop:${p.player_id || p.player_name}:${p.market}:${p.game_date ?? ""}`;
}

export function gamePickKey(p: GameProp): string {
  return `game:${p.matchup}:${p.segment}:${p.market}:${p.game_date ?? ""}`;
}

export function propSnapshot(p: Prop): PickSnapshot {
  const side = p.recommended_side;
  const binary = isBinaryMarket(p);
  const sideText = binary ? "Yes" : side.toUpperCase();
  return {
    label: binary ? `${sideText} ${p.market_label}` : `${sideText} ${p.line ?? ""} ${p.market_label}`.replace(/\s+/g, " "),
    side: sideText,
    line: p.line,
    price: sidePrice(p, side),
    book: sideBook(p, side),
    markedAt: new Date().toISOString(),
  };
}

export function gameSnapshot(p: GameProp): PickSnapshot {
  const side = p.recommended_side;
  return {
    label: `${gameSideLabel(p, side)} ${p.market_label}`,
    side: gameSideLabel(p, side),
    line: p.line,
    price: gameSidePrice(p, side),
    book: gameSideBook(p, side),
    markedAt: new Date().toISOString(),
  };
}

export function usePicks() {
  const picks = useSyncExternalStore(subscribe, () => current, () => current);
  const toggle = useCallback((key: string, snapshot: () => PickSnapshot) => {
    const next = { ...current };
    if (next[key]) delete next[key];
    else next[key] = snapshot();
    write(next);
  }, []);
  return { picks, toggle };
}
