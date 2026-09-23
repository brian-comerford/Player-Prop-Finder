import type { Meta, Prop, TrackRecord } from "./types";

const base = import.meta.env.BASE_URL;

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${base}data/${path}?v=${Date.now()}`);
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status}`);
  }
  return res.json();
}

export function fetchProps(): Promise<Prop[]> {
  return fetchJson<Prop[]>("props.json");
}

export function fetchMeta(): Promise<Meta> {
  return fetchJson<Meta>("meta.json");
}

export function fetchTrackRecord(): Promise<TrackRecord> {
  return fetchJson<TrackRecord>("track_record.json");
}
