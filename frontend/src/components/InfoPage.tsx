import type { ReactNode } from "react";
import type { ThemeChoice } from "../lib/useTheme";

const THEME_OPTIONS: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
        {children}
      </div>
    </section>
  );
}

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <dt className="font-mono text-sm font-semibold text-slate-800 dark:text-slate-200">{term}</dt>
      <dd className="mt-1 text-sm text-slate-600 dark:text-slate-400">{children}</dd>
    </div>
  );
}

export default function InfoPage({
  theme,
  onThemeChange,
}: {
  theme: ThemeChoice;
  onThemeChange: (theme: ThemeChoice) => void;
}) {
  return (
    <div className="space-y-8 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 sm:p-6">
      <Section title="Appearance">
        <p>
          Defaults to your device's own light/dark setting. Override it here if you'd rather
          this page stay one way regardless of your system theme.
        </p>
        <div className="inline-flex overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
          {THEME_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onThemeChange(value)}
              aria-pressed={theme === value}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                theme === value
                  ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                  : "bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section title="What this page is doing">
        <p>
          For each player and stat (a "market"), the app builds its own projection from that
          player's recent games, then compares it to the sportsbook's line and odds. When the
          model's estimate disagrees with what the odds imply, that gap is the "edge" &mdash;
          the table is sorted to put the biggest gaps first.
        </p>
        <p>
          This is a statistical estimate, not a prediction of what will happen. Small sample
          sizes, injuries, and last-minute usage changes can all make the model wrong. Treat it
          as a starting point for your own research, not a signal to bet on by itself.
        </p>
        <p>
          Before any of that, every player is checked against real play-by-play data for a
          confirmed recent snap. A player who hasn't taken a snap in roughly the last month
          (injury, retirement, or otherwise) is left out entirely, no matter how good their
          older stats look &mdash; a strong game log from a year ago doesn't mean much if
          they're not actually playing right now.
        </p>
        <p>
          Players are also checked against the official weekly injury report. Anyone listed as{" "}
          <strong>Out</strong> or <strong>Doubtful</strong> is left out of these results the same
          way, since they're unlikely to play at all. A player listed as{" "}
          <strong>Questionable</strong> still shows up (that designation is genuinely uncertain,
          not a reliable "won't play" signal) but gets a small{" "}
          <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
            Q
          </span>{" "}
          badge next to their name &mdash; the projection is built purely from past stats, so it
          has no way to know about a game-status question like that on its own.
        </p>
      </Section>

      <Section title="Table columns">
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Term term="Line">
            The sportsbook's over/under for that stat (e.g. 65 rushing yards). Blank for
            "Anytime TD," which is a yes/no market with no number line.
          </Term>
          <Term term="Pick">
            The side (over/under, or "yes" for Anytime TD) the model estimates is priced in the
            bettor's favor &mdash; i.e. whichever side has the larger edge.
          </Term>
          <Term term="Book">
            Which source the line and odds came from: DraftKings, FanDuel, or Kalshi (a
            federally-regulated prediction market, not a sportsbook &mdash; its "odds" are
            derived from a contract price rather than posted directly). When neither a book nor
            an API key is configured, this reads "Sample."
          </Term>
          <Term term="Odds">
            The odds for the picked side, in American format, from whichever book is shown in
            the Book column. Negative numbers (e.g. -110) show how much you'd need to stake to
            win $100; positive numbers (e.g. +130) show how much a $100 stake would win.
          </Term>
          <Term term="Model %">
            The model's estimated probability that the picked side happens, based on the
            player's recent performance and an opponent-strength adjustment. The number in
            parentheses (e.g. "50.0% (-100)") is that same probability converted to the
            American odds it would imply with no vig &mdash; not a real price from any book,
            just a way to compare the model's view against the book's price in the same units.
          </Term>
          <Term term="Book %">
            The sportsbook's implied probability for that side, after removing the "vig"
            (the built-in house edge baked into both sides of a line) &mdash; see below.
          </Term>
          <Term term="Edge">
            Model % minus Book %. A +15% edge means the model thinks that outcome is 15
            percentage points more likely than the sportsbook's price suggests. Bigger isn't
            automatically better &mdash; a huge edge on a thin sample is a red flag, not a lock
            (see Confidence).
          </Term>
          <Term term={'Confidence & the game count (e.g. "7g")'}>
            How much the model trusts its own projection, based on how many recent games it
            had to work with (shown as e.g. "7g" = 7 games) and how consistent the player's
            output has been game to game.
            <ul className="ml-4 mt-2 list-disc space-y-1">
              <li><strong>High</strong>: 8+ games, and fairly consistent output.</li>
              <li><strong>Medium</strong>: 5+ games, or more variable output.</li>
              <li><strong>Low</strong>: fewer games or highly volatile numbers &mdash; treat these projections loosely.</li>
            </ul>
            Where available, this also shifts by one tier based on whether ESPN's own,
            independently-computed weekly projection agrees or disagrees &mdash; see
            &quot;ESPN 2nd opinion&quot; below.
          </Term>
        </dl>
      </Section>

      <Section title="The trend arrow next to a player's name">
        <p>
          A small arrow appears next to a player's name when there's a notable hit-rate pattern
          worth knowing &mdash; tap it to expand. It only shows up when the model finds one, so
          most rows won't have it. Two kinds of trends can appear:
        </p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <strong>Recent form</strong>, e.g. "Over 3.5 receptions in 8 of last 10 games"
            &mdash; how often the player would have cleared today's line over their last 10
            games.
          </li>
          <li>
            <strong>Matchup-specific</strong>, e.g. "Over 3.5 receptions in 6 of 7 games vs.
            bottom-half defenses" &mdash; the same idea, narrowed to games against defenses that
            rank in the bottom half for this stat and position (see Opponent factor below). For
            an Under, this instead checks games against top-half defenses, since a tougher
            defense is what makes an Under more likely to hit.
          </li>
        </ul>
        <p>
          These are descriptive hit-rate stats, not a separate prediction &mdash; they're there
          to show your own eyes the pattern behind the model's number, so you can judge whether
          it's a real trend or a coincidence.
        </p>
      </Section>

      <Section title="Inside the detail view">
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Term term="Projection">
            The model's projected value for that stat this game: the player's recency-weighted
            average, adjusted by the opponent factor below. Recent games count more than older
            ones, and on top of that, games from the current season count more than games from a
            previous one even at the same recency &mdash; a new season can mean a new role, a new
            team, or coming back from an injury, so last season's stats are a weaker stand-in for
            what a player will do now than this season's own games are.
          </Term>
          <Term term="Opponent factor">
            How much the upcoming opponent inflates or suppresses this stat compared to a
            league-average defense, e.g. 1.15x means that defense allows about 15% more of
            this stat than average. Capped to a modest range so one unusual game can't swing it
            too far. Computed specifically for the player's own position when there's enough
            sample &mdash; e.g. a defense's rushing/receiving-TD funnel to running backs is
            judged separately from its funnel to wide receivers and tight ends, so a running
            back's receiving production is compared to what that defense allows to running
            backs, not to wideouts. Falls back to an all-positions blended factor when the
            position-specific sample is too thin.
          </Term>
          <Term term="ESPN 2nd opinion">
            Where ESPN publishes its own weekly fantasy projection for this player and stat, it
            shows up here as an outside sanity check, with a plain read on how closely it
            lines up with this app's own number: &quot;agrees,&quot; &quot;roughly agrees,&quot;
            or &quot;disagrees.&quot; Two independently-built projections landing in the same
            place is modest evidence the number isn't a fluke, and a real disagreement is a
            reason for more caution &mdash; each shifts Confidence by at most one tier, in that
            direction, never overriding it outright. Missing for players ESPN hasn't projected
            for that week yet.
          </Term>
        </dl>
      </Section>

      <Section title="What's a 'no-vig' probability, and why it's not 100%?">
        <p>
          Sportsbook odds always add up to more than 100% probability across both sides of a
          bet &mdash; that extra margin is the "vig" (the house's built-in edge), typically
          3&ndash;5%. "Book %" strips that margin back out so it's an apples-to-apples
          comparison against the model's own probability, rather than comparing the model to an
          artificially inflated number.
        </p>
      </Section>

      <Section title="Where the data comes from">
        <p>
          Player stats and schedules come from{" "}
          <a
            className="underline"
            href="https://github.com/nflverse/nflverse-data"
            target="_blank"
            rel="noreferrer"
          >
            nflverse
          </a>
          , a free public NFL data project. Sportsbook lines come from{" "}
          <a className="underline" href="https://the-odds-api.com/" target="_blank" rel="noreferrer">
            The Odds API
          </a>{" "}
          when configured, restricted to DraftKings and FanDuel specifically (whichever of the
          two has the better price for a given line) so what you see matches what you could
          actually bet, rather than a blended number from books you may not have access to.
          Kalshi markets, where available for a given player and stat, are pulled directly from{" "}
          <a className="underline" href="https://kalshi.com/" target="_blank" rel="noreferrer">
            Kalshi's
          </a>{" "}
          public API and shown as a separate row alongside the sportsbook line, so you can
          compare the two. If no odds source is configured at all, the app shows clearly-labeled
          sample odds instead (built from real stats, but with synthetic lines) so the page
          still has something to show. Everything refreshes automatically about once a day.
        </p>
      </Section>

      <Section title="Not betting advice">
        <p>
          This tool models publicly available stats against sportsbook pricing for informational
          and educational purposes. It doesn't account for injuries, weather, coaching decisions,
          or anything else that happened after data was last refreshed. Please gamble responsibly,
          and only where it's legal to do so.
        </p>
      </Section>
    </div>
  );
}
