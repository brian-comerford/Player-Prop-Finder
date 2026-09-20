import type { ReactNode } from "react";

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

export default function InfoPage() {
  return (
    <div className="space-y-8 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 sm:p-6">
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
          <Term term="Odds">
            The sportsbook's American odds for the picked side. Negative numbers (e.g. -110)
            show how much you'd need to stake to win $100; positive numbers (e.g. +130) show
            how much a $100 stake would win.
          </Term>
          <Term term="Model %">
            The model's estimated probability that the picked side happens, based on the
            player's recent performance and an opponent-strength adjustment.
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
          </Term>
        </dl>
      </Section>

      <Section title="Inside the detail view">
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Term term="Projection">
            The model's projected value for that stat this game: the player's recency-weighted
            average, adjusted by the opponent factor below.
          </Term>
          <Term term="Opponent factor">
            How much the upcoming opponent inflates or suppresses this stat compared to a
            league-average defense, e.g. 1.15x means that defense allows about 15% more of
            this stat than average. Capped to a modest range so one unusual game can't swing it
            too far.
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
          , a free public NFL data project. Odds come from{" "}
          <a className="underline" href="https://the-odds-api.com/" target="_blank" rel="noreferrer">
            The Odds API
          </a>{" "}
          when configured, aggregated across sportsbooks to the best available price at the
          consensus line. If no odds feed is configured, the app shows clearly-labeled sample
          odds instead (built from real stats, but with synthetic lines) so the page still has
          something to show. Everything refreshes automatically about once a day.
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
