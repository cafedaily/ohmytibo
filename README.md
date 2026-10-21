# OH MY TIBO

Follow [@thsottiaux](https://x.com/thsottiaux) — Tibo, OpenAI's Codex & ChatGPT lead — and the thing he is famous for: **usage resets**.

This repo tracks his public posts and replies, models when the next Codex/ChatGPT usage reset is likely, and turns his replies into a hot-word / topic picture.

Live dashboard: **https://cafedaily.github.io/ohmytibo/** — published to GitHub Pages by the `refresh` workflow:

- **Fast run, every 5 minutes:** fetches the mirror's pages for today and yesterday plus the reset feed (three requests), recomputes, sends alerts, and redeploys the page. It commits only when stored data moved: a new post, a new feed event, alert state, or a source going down or recovering (`scripts/changed.py`).
- **Full run, every 3 hours:** rescans the last 60 day pages to refresh engagement counts, and always commits.

GitHub runs scheduled jobs late under load, so expect 5–15 minutes in practice. The header light turns amber after 20 minutes without new data and red after an hour.

## What it does

- **Reset forecast** — discrete-time hazard model over days-since-last-reset, softened with a triangular kernel, spread across hours and weekdays by his historical rhythm, and pulled forward when a live promise ("by EOD", "tomorrow") is pending without a reset. Walk-forward backtest ships with the output.
- **Hot words** — unigrams and adjacent bigrams from the last 7 days, scored against the previous 28 days as a baseline (log2 lift), with the originating post attached.
- **Topics** — reset/quota, models, Codex tooling, plans/pricing, growth milestones, reliability, and the 28-day ship-or-reset series.
- **Rhythm** — daily original-vs-reply volume with reset and banked days marked, plus how often reset vocabulary ("reset", "banked", "EOD", "usage") appears per week.
- **Reset signals** — recent reset chatter that is not a verified reset: the feed's announce / related / note entries, posts the mirror tags "Reset" or "Reset talk", and untagged posts that say "reset". Listed with a 24h/72h/7d count and a level against the prior 28 days. The hazard model does not read them.
- **Monitoring** — per-source health, a run log, push alerts, and a status card on the dashboard (see below).

## Data

No X API access is used. Sources:

- `https://tiboreset.com/X-posts/YYYY-MM-DD` — per-day mirror of his public posts and replies (text, timestamps, engagement counts).
- `https://tiboreset.com/feed.xml` — Atom feed of verified reset / banked-reset events.

Both belong to an independent tracker, not OpenAI. Each run refetches the last 60 days the mirror exposes; the reset log goes back to July 2026.

Both stored datasets are append-only. The feed only carries its latest ~50 entries, so `resets.json` keeps every event it has ever seen and updates entries by id. Entries the mirror observed itself, with no `rel="via"` link to an X post, are kept under the mirror's `/r/<id>`. Posts whose day page was not refetched stay in `posts.jsonl`.

## Run it

```bash
python scripts/pipeline.py 60   # full run; `1` for a fast run (today and yesterday only)
```

That fetches the day pages, parses them into `data/processed/posts.jsonl`, refreshes the reset feed, recomputes the forecast, hot words and signals, sends alerts, and renders `site/index.html`. Each run is appended to `data/state/runs.jsonl`; a failed step skips the steps that depend on it and the run exits non-zero.

Individual stages:

```bash
python scripts/fetch_corpus.py --days 60
python scripts/parse_corpus.py
python scripts/fetch_reset_log.py
python scripts/analyze.py
python scripts/alert.py            # add --dry-run to print without sending or saving state
python scripts/build_site.py
```

Tests (stdlib only; they also run before every scheduled refresh):

```bash
python -m unittest discover -s tests
```

Preview locally:

```bash
python -m http.server 8765 --directory site
```

## Dashboard

`site/index.html` is a single, fully client-rendered page:

- **Three.js starfield** — a 2,200-point particle shell that drifts behind the content, pauses when the tab is hidden, and renders a single still frame under `prefers-reduced-motion`.
- **Live numbers** — the 24h probability animates on a gradient ring, a countdown ticks down to the modal reset slot, and a Beijing-time clock runs in the header.
- **Interactive charts** — hover/focus tooltips on every mark, 14/30/all range switching and series toggling on the activity chart, and a high-frequency / surging switch on the hot-word chart.
- **Self-refresh** — `site/data.json` is re-fetched on visibility change and every 2 minutes (throttled to once a minute), so a new deploy shows up without a manual reload.

The page ships a baked-in JSON payload, so it still renders with the CDN or `data.json` unreachable.

## Alerts

`scripts/alert.py` pushes:
- new verified resets and banked deliveries
- a new unfulfilled promise ("by EOD", "tomorrow")
- the 24h probability crossing 30% or 60% (once per reset cycle)
- feed `announce` / `related` signals, and forward-looking signals, posted since the last reset
- three consecutive fetch failures for the feed or the post mirror

Configure any of these repository secrets (Settings → Secrets and variables → Actions):

| Channel | Secrets |
|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL` |
| Bark | `BARK_URL` (e.g. `https://api.day.app/<key>`) |
| Generic JSON webhook | `ALERT_WEBHOOK_URL` |

Delivery is recorded per channel in `data/state/alerts.json`:
- An alert is `sent` only when every configured channel accepted it, and `partial` when some did; failed channels are retried on later runs.
- With no channel configured, an alert stays `pending` (reason `no_channel`). It is never recorded as sent, and the dashboard's status card says that alert channels are not configured.
- Alerts not delivered within 12 hours become `expired`.
- The first run only records the events that already exist, so it does not replay history.

## Outputs

| File | Contents |
|---|---|
| `data/processed/posts.jsonl` | One record per post: id, UTC timestamp, text, reply target, reset pill, engagement counts |
| `data/processed/resets.json` | Reset / banked / note events from the feed |
| `data/processed/forecast.json` | Probabilities (24h/48h/72h/7d), hazard table, hourly curve, backtest |
| `data/processed/hotwords.json` | Top terms, surge terms, phrases, topics, mentions, reset lexicon |
| `data/processed/metrics.json` | Dashboard summary + daily series |
| `data/state/health.json` | Latest status per source (feed, corpus, pipeline) with failure streaks |
| `data/state/runs.jsonl` | One line per committed pipeline run (full runs, and fast runs that changed data): mode, steps, durations, failures |
| `data/state/alerts.json` | Alert keys already seen, alert delivery records, summary for the dashboard |
| `site/index.html` | The dashboard (static shell + inline payload) |
| `site/data.json` | Refreshable payload consumed by the dashboard |

## Caveats

- All dashboard times are Beijing time (UTC+8); the raw data stays UTC.
- Reset times are the feed's published times. For a few events that is Tibo's post time rather than the moment the mirror saw the reset land.
- A 7-day hot-word window over ~30 posts is noisy; the lift column is a lead, not a verdict.
- Backtest skill hovers near the base rate. Resets are driven by launches, incidents and milestone pressure, so the model is a prior — read the pending-promise line before the percentage.
- Unofficial. Not affiliated with OpenAI, Tibo, or the trackers above.
