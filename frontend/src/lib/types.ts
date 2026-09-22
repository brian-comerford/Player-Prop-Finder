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
