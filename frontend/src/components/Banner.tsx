import type { Meta } from "../lib/types";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const hours = Math.round(diffMs / 3_600_000);
  if (hours < 1) return "less than an hour ago";
  if (hours === 1) return "1 hour ago";
  if (hours < 48) return `${hours} hours ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export default function Banner({ meta }: { meta: Meta }) {
  const weekLabel =
    meta.upcoming_season && meta.upcoming_week
      ? `Week ${meta.upcoming_week}, ${meta.upcoming_season}`
      : "No upcoming games found";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <img src="logo.png" alt="" className="h-10 w-auto sm:h-12" />
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Player Prop Finder</h1>
        </div>
        <span className="text-sm text-slate-500 dark:text-slate-400">
          {weekLabel} &middot; updated {timeAgo(meta.generated_at)}
        </span>
      </div>
      <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-400">
        Projects each player's stat line from recency-weighted recent games and an
        opponent-defense adjustment, then compares that to the sportsbook's no-vig implied
        probability to surface lines that look mispriced. This is a statistical model, not
        betting advice &mdash; sample sizes are small and injuries/usage change fast. Bet
        responsibly.
      </p>
      {meta.inactive_players_excluded > 0 && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {meta.inactive_players_excluded} player(s) left out of these results because we
          couldn't confirm they've played recently (injury, retirement, etc.) &mdash; see the
          Info tab.
        </p>
      )}
      {meta.odds_source === "sample" && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
          <strong>Sample odds:</strong> no live sportsbook feed is configured, so the lines
          below are synthetic (generated from real player stats, not an actual book). Add an{" "}
          <code className="rounded bg-black/10 px-1 py-0.5 dark:bg-white/10">ODDS_API_KEY</code>{" "}
          secret to pull live odds &mdash; see the README.
        </div>
      )}
    </div>
  );
}
