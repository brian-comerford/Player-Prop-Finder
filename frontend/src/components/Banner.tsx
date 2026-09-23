import type { Confidence, Meta, TrackRecord } from "../lib/types";

const CONFIDENCE_TIERS: Confidence[] = ["High", "Medium", "Low"];

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const hours = Math.round(diffMs / 3_600_000);
  if (hours < 1) return "less than an hour ago";
  if (hours === 1) return "1 hour ago";
  if (hours < 48) return `${hours} hours ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function pct(hitRate: number): string {
  return `${Math.round(hitRate * 100)}%`;
}

export default function Banner({ meta, trackRecord }: { meta: Meta; trackRecord: TrackRecord | null }) {
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
      {trackRecord?.overall && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
          <strong>Track record:</strong> {pct(trackRecord.overall.hit_rate)} of picks have hit (
          {trackRecord.overall.hits}/{trackRecord.overall.picks}) across {trackRecord.weeks_graded}{" "}
          graded {trackRecord.weeks_graded === 1 ? "week" : "weeks"}
          {trackRecord.weeks_graded < 4 && " — still an early sample, see the Info tab"}
          {CONFIDENCE_TIERS.some((tier) => trackRecord.by_confidence[tier]) && (
            <>
              {" · "}
              {CONFIDENCE_TIERS.filter((tier) => trackRecord.by_confidence[tier])
                .map((tier) => `${tier} ${pct(trackRecord.by_confidence[tier]!.hit_rate)}`)
                .join(" · ")}
            </>
          )}
        </div>
      )}
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
      <p className="text-xs text-slate-400 dark:text-slate-600">
        This app costs approximately $30 per month to keep up to date. If you use it and enjoy
        it, a small donation would be appreciated &mdash; @Brian-Comerford-1 on Venmo.
      </p>
    </div>
  );
}
