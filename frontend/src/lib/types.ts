export interface RecentGame {
  season: number;
  week: number;
  opponent_team: string;
  value: number;
}

export type Side = "over" | "under";
export type Confidence = "Low" | "Medium" | "High";

export interface Prop {
  player_name: string;
  position: string;
  team: string;
  opponent: string;
  matchup: string | null;
  game_date: string | null;
  time_slot: string | null;
  market: string;
  market_label: string;
  line: number | null;
  book_over: string | null;
  book_under: string | null;
  price_over: number | null;
  price_under: number | null;
  model_prob_over: number;
  model_prob_under: number;
  implied_prob_over: number | null;
  implied_prob_under: number | null;
  edge_over: number | null;
  edge_under: number | null;
  recommended_side: Side;
  recommended_edge: number;
  projected_value: number;
  defense_factor: number;
  sample_games: number;
  confidence: Confidence;
  recent_games: RecentGame[];
  trends: string[];
  injury_status: string | null;
  espn_projected_value: number | null;
  espn_agreement: "strong" | "moderate" | "split" | null;
  player_id: string;
}

export interface Meta {
  generated_at: string;
  baseline_season: number;
  upcoming_season: number | null;
  upcoming_week: number | null;
  odds_source: "live" | "sample";
  odds_fetched_at: string;
  prop_count: number;
  markets: Record<string, string>;
  inactive_players_excluded: number;
  matchups: string[];
  time_slots: string[];
}

export interface HitRateSummary {
  picks: number;
  hits: number;
  hit_rate: number;
}

export interface TrackRecord {
  overall: HitRateSummary | null;
  by_confidence: Partial<Record<Confidence, HitRateSummary>>;
  weeks_graded: number;
  updated_at: string;
}

export type GameSegment = "full" | "h1" | "h2";
export type GameMarket = "spread" | "total";
export type GameSide = "a" | "b";

export interface GameProp {
  matchup: string;
  home_team: string;
  away_team: string;
  game_date: string | null;
  time_slot: string | null;
  segment: GameSegment;
  segment_label: string;
  market: GameMarket;
  market_label: string;
  line: number | null;
  side_a_label: string;
  side_b_label: string;
  price_a: number | null;
  price_b: number | null;
  book_a: string | null;
  book_b: string | null;
  model_prob_a: number;
  model_prob_b: number;
  implied_prob_a: number | null;
  implied_prob_b: number | null;
  edge_a: number | null;
  edge_b: number | null;
  recommended_side: GameSide;
  recommended_edge: number;
  model_home_points: number;
  model_away_points: number;
  model_total: number;
  model_margin_home: number;
  sample_games_home: number;
  sample_games_away: number;
  confidence: Confidence;
}

export interface GameMeta {
  generated_at: string;
  upcoming_season: number | null;
  upcoming_week: number | null;
  odds_source: "live" | "none";
  odds_fetched_at: string | null;
  prop_count: number;
  segments: Record<string, string>;
}
