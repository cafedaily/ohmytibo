# ohmytibo

Follow [@thsottiaux](https://x.com/thsottiaux) — Tibo, OpenAI's Codex & ChatGPT lead — and the thing he is famous for: **usage resets**.

This repo tracks his public posts and replies, models when the next Codex/ChatGPT usage reset is likely, and turns his replies into a hot-word / topic picture.

Live dashboard: open [site/index.html](site/index.html) after a build (or serve `site/` with any static server).

## What it does

- **Reset forecast** — discrete-time hazard model over days-since-last-reset, softened with a triangular kernel, spread across hours and weekdays by his historical rhythm, and pulled forward when a live promise ("by EOD", "tomorrow") is pending without a reset. Walk-forward backtest ships with the output.
- **Hot words** — unigrams and adjacent bigrams from the last 7 days, scored against the previous 28 days as a baseline (log2 lift), with the originating post attached.
- **Topics** — reset/quota, models, Codex tooling, plans/pricing, growth milestones, reliability, and the 28-day ship-or-reset series.
- **Rhythm** — daily original-vs-reply volume with reset days marked, plus how often reset vocabulary ("reset", "banked", "EOD", "usage") appears per week.

## Data

No X API access is used. Sources:

- `https://tiboreset.com/X-posts/YYYY-MM-DD` — per-day mirror of his public posts and replies (text, timestamps, engagement counts).
- `https://tiboreset.com/feed.xml` — Atom feed of verified reset / banked-reset events.

Both belong to an independent tracker, not OpenAI. The corpus is the last 60 days the mirror exposes; the reset log goes back to July 2026.

## Run it

```bash
python scripts/pipeline.py 60
```

That fetches the day pages, parses them into `data/processed/posts.jsonl`, refreshes the reset feed, recomputes the forecast and hot words, and renders `site/index.html`.

Individual stages:

```bash
python scripts/fetch_corpus.py --days 60
python scripts/parse_corpus.py
python scripts/fetch_reset_log.py
python scripts/analyze.py
python scripts/build_site.py
```

Preview locally:

```bash
python -m http.server 8765 --directory site
```

## Outputs

| File | Contents |
|---|---|
| `data/processed/posts.jsonl` | One record per post: id, UTC timestamp, text, reply target, reset pill, engagement counts |
| `data/processed/resets.json` | Reset / banked / note events from the feed |
| `data/processed/forecast.json` | Probabilities (24h/48h/72h/7d), hazard table, hourly curve, backtest |
| `data/processed/hotwords.json` | Top terms, surge terms, phrases, topics, mentions, reset lexicon |
| `data/processed/metrics.json` | Dashboard summary + daily series |
| `site/index.html` | The dashboard |

## Caveats

- All dashboard times are Beijing time (UTC+8); the raw data stays UTC.
- Reset times are announcement times, not the moment every account finishes propagating.
- A 7-day hot-word window over ~30 posts is noisy; the lift column is a lead, not a verdict.
- Backtest skill hovers near the base rate. Resets are driven by launches, incidents and milestone pressure, so the model is a prior — read the pending-promise line before the percentage.
- Unofficial. Not affiliated with OpenAI, Tibo, or the trackers above.
