# Player Prop Finder

A static web app that projects NFL player stat lines from recent performance
and opponent strength, compares that projection to sportsbook player-prop
odds, and surfaces the bets that look mispriced (positive "edge").

It's deployed on **GitHub Pages**, which only serves static files, so there
is no server and no database. Instead, a scheduled GitHub Action re-runs the
whole data pipeline once a day, builds the site, and deploys it.

**This is a statistical modeling tool, not betting advice.** Sample sizes
are small, injuries and usage change week to week, and no model captures
everything a sportsbook prices in. Bet responsibly, or don't bet at all.

## How it works

```
scripts/fetch_stats.py   Downloads free, public NFL player game logs and the
                          season schedule from nflverse (no API key needed).

scripts/fetch_odds.py    Fetches player-prop odds from The Odds API for the
                          upcoming week's games (needs ODDS_API_KEY).
                          Falls back to clearly-labeled SAMPLE odds -- built
                          from real player stats but with synthetic lines --
                          if no key is configured, so the app works out of
                          the box.

scripts/analyze.py       The value model:
                          1. Builds a recency-weighted mean/std of each
                             player's stat over their last ~17 games
                             (current + previous season).
                          2. Adjusts the projection by an opponent-defense
                             factor (how much that defense allows in this
                             stat vs. league average).
                          3. Converts the model's over/under (or anytime-TD)
                             probability against the sportsbook line, and
                             separately de-vigs the sportsbook's own odds
                             into a fair implied probability.
                          4. Edge = model probability - book's no-vig
                             implied probability. Props are ranked by edge.

frontend/                A React + Vite + Tailwind app that fetches the
                          generated data/*.json and renders a filterable,
                          sortable table plus a per-player detail view with
                          a recent-games-vs-line chart (Recharts).
```

Data flows one way: Python scripts write `data/*.json` -> the frontend
build copies it into `frontend/public/data/` -> Vite bundles it into the
static site. Nothing is fetched live from the browser, so no API key is
ever exposed to site visitors.

## Markets modeled

Passing yards, passing TDs, rushing yards, receptions, receiving yards,
combined rush+receiving yards, and anytime TD (rushing/receiving only --
not a QB's own passing TDs).

## Running the pipeline locally

```bash
cd scripts
pip install -r requirements.txt
python generate_data.py        # writes ../data/props.json, meta.json, etc.
```

Set `ODDS_API_KEY` in your environment first if you want live odds instead
of the sample fallback:

```bash
export ODDS_API_KEY=your_key_here
python generate_data.py
```

## Running the frontend locally

```bash
cd frontend
npm install
npm run dev       # runs `sync-data` first, then starts Vite on localhost
```

`npm run sync-data` copies `../data/*.json` into `frontend/public/data/` --
run the pipeline above at least once first, or `npm run dev`/`npm run build`
will do it for you automatically (but will fail if `../data/props.json`
doesn't exist yet).

## Deploying

The included workflow (`.github/workflows/deploy.yml`) does everything:
runs the data pipeline, builds the frontend, and deploys to GitHub Pages.
It fires on every push to `main`, once a day on a schedule, and can be run
manually from the Actions tab.

To enable it:

1. In the repo's **Settings -> Pages**, set **Source** to "GitHub Actions".
2. (Optional, for live odds) Sign up for a free key at
   [the-odds-api.com](https://the-odds-api.com/) and add it as a repository
   secret named `ODDS_API_KEY` (**Settings -> Secrets and variables ->
   Actions**). Without it, the site runs in sample-odds mode automatically
   -- still using real player stats, just with synthetic lines instead of
   real sportsbook prices.
3. Push to `main`, or run the workflow manually, to trigger the first
   deploy.

The free tier of The Odds API is 500 credits/month, which comfortably
covers one refresh per day; raise the schedule's cron frequency only if
you're on a paid plan.

## Known limitations

- **Data freshness depends on nflverse's release cadence.** The pipeline
  detects the latest season it has player stats for and matches it against
  the schedule's next unplayed week; if the stats feed briefly lags the
  schedule feed (which can happen right after games are played), the
  projections use the most recent season actually available.
- The opponent-defense adjustment is a simple "average allowed vs. league
  average" ratio, not a full opponent-adjusted efficiency model.
- Early in a season, sample sizes are small; the "Confidence" label
  (Low/Medium/High) reflects that, and games played is shown alongside it.
