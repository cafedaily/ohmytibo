#!/usr/bin/env python3
"""Reset forecast + hot-word extraction for @thsottiaux.

Inputs (data/processed/): posts.jsonl, resets.json
Outputs (data/processed/): forecast.json, hotwords.json, metrics.json
"""
import datetime as dt
import json
import math
import pathlib
import re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
UTC = dt.timezone.utc
CST = dt.timezone(dt.timedelta(hours=8))  # display timezone: Beijing
NOW = dt.datetime.now(UTC)

STOP = set("""a an the and or but if then than that this these those there here i you he she it we they
me my your his her its our their them us of to in on at for with without from by as is are was were be been being
do does did doing have has had having will would can could should shall may might must not no nor so such only own
same too very just also more most much many few some any all both each other another into over under about above below
up down out off again further once what which who whom whose when where why how get got gets getting make makes made
it's i'm you're we're they're don't doesn't didn't isn't aren't wasn't weren't can't couldn't won't wouldn't
im ive id youre weve theyve dont doesnt didnt isnt arent wasnt werent cant couldnt wont wouldnt
one two three new day days now still like really thing things way lot going go goes went good great thanks thank
know think want need see say said let lets us via per vs etc amp http https t.co www com""".split())

GENERIC = set("""today tomorrow yesterday day days week weeks month year time times small big large little
look looking looks request requests working worked work app apps thing things stuff people person
making make made come comes coming back call called try trying tried keep keeps kept put puts
first last next last same different right left way ways part parts number lot lots bit little
wanted able sure okay ok yes yeah wow haha lol hey hello thanks thank please sorry pretty
question answers answer post posts tweet tweets reply replies said says tell told
""".split())

TERM_KEEP = {
    "reset", "resets", "reseted", "usage", "codex", "chatgpt", "gpt", "pro", "plus", "business", "team",
    "work", "api", "model", "models", "context", "limit", "limits", "tokens", "token", "banked", "sol",
    "astra", "luna", "composer", "desktop", "app", "thread", "vote", "poll", "series", "ship", "day",
    "users", "active", "milestone", "outage", "incident", "attack", "credits", "refund", "compaction",
    "memory", "dashboard", "subscription", "subscriptions", "plan", "price", "pricing", "speed", "latency",
    "image", "images", "video", "audio", "voice", "search", "agent", "agents", "dots", "dot", "plugins",
    "apps", "partners", "devday", "launch", "enterprise", "edu", "students", "teachers", "security",
    "safety", "openai", "community", "feedback", "bug", "bugs", "fix", "fixes", "shipped", "ship",
    "faster", "cheaper", "quality", "capability", "capabilities", "reasoning", "coding", "engineer",
    "engineering", "sorry", "enjoy", "propagated", "window", "weekly", "monthly", "quota", "throttle",
}

TOPIC_RULES = [
    ("Reset / quota", ["reset", "resets", "reseted", "usage", "limit", "limits", "quota", "banked", "propagated", "window", "weekly"]),
    ("Models", ["gpt", "sol", "astra", "luna", "model", "models", "composer", "reasoning", "context"]),
    ("Codex / dev tooling", ["codex", "api", "desktop", "app", "thread", "agent", "agents", "coding", "engineer"]),
    ("Plans / pricing", ["pro", "plus", "business", "plan", "price", "pricing", "subscription", "subscriptions", "enterprise", "edu"]),
    ("Growth / milestones", ["users", "active", "milestone", "community", "starting", "waitlist"]),
    ("Reliability / incidents", ["outage", "incident", "attack", "downtime", "bug", "bugs", "fix", "fixes", "security"]),
    ("Ship-or-reset series", ["series", "vote", "poll", "shipped", "ship", "day"]),
]

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@[A-Za-z0-9_]+")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'+]{2,}")


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def local(iso_or_dt):
    """Timestamp in Beijing time (UTC+8)."""
    t = parse_ts(iso_or_dt) if isinstance(iso_or_dt, str) else iso_or_dt
    return t.astimezone(CST)


# ---------------------------------------------------------------- reset hazard

def reset_times(events):
    return sorted(parse_ts(e["ts"]) for e in events if e["kind"] == "reset")


def hazard_table(resets, horizon_days=21, now=None):
    """Daily hazard by days-since-last-reset, smoothed over neighbouring day buckets.

    hazard[k] = P(reset inside day [k, k+1) | no reset through day k).
    Intervals still open are censored; a triangular kernel (radius 1) keeps the
    thin per-bucket samples from producing spiky probabilities.
    """
    ref = now or NOW
    hits = Counter()
    exposure = Counter()
    for i, start in enumerate(resets):
        days = ((resets[i + 1] if i + 1 < len(resets) else ref) - start).total_seconds() / 86400
        for k in range(horizon_days):
            if days <= k:
                break
            exposure[k] += 1
        if i + 1 < len(resets):
            bucket = int(days)
            if bucket < horizon_days:
                hits[bucket] += 1
    table = {}
    for k in range(horizon_days):
        num = den = 0.0
        for j, weight in ((k - 1, 0.5), (k, 1.0), (k + 1, 0.5)):
            if 0 <= j < horizon_days:
                num += weight * (hits[j] + 0.4)
                den += weight * (exposure[j] + 1.6)
        table[k] = num / den if den else 0.02
    return table


def hour_weights(resets, halflife_days=60, now=None):
    """Smoothed hour-of-day prior, recency weighted."""
    w = defaultdict(float)
    for t in resets:
        age = ((now or NOW) - t).total_seconds() / 86400
        w[t.hour] += 0.5 ** (age / halflife_days)
    total = sum(w.values()) or 1.0
    return {h: w[h] / total for h in range(24)}


def weekday_weights(resets, halflife_days=60, now=None):
    w = defaultdict(float)
    for t in resets:
        age = ((now or NOW) - t).total_seconds() / 86400
        w[t.weekday()] += 0.5 ** (age / halflife_days)
    total = sum(w.values()) or 1.0
    return {d: w[d] / total for d in range(7)}


PROMISE_RE = re.compile(
    r"\b(by eod|eod|end of day|tomorrow|tonight|within the next|in the next|coming|landing|"
    r"will reset|going to reset|next week|soon|on its way|incoming)\b", re.I)


def pending_promise(posts, resets, lookback_hours=72):
    """A recent forward-looking reset commitment with no reset after it yet."""
    if not resets:
        return None
    last = resets[-1]
    for p in reversed(posts):
        t = parse_ts(p["ts"])
        if t <= last or (NOW - t).total_seconds() > lookback_hours * 3600:
            continue
        if re.search(r"\breset", p["text"], re.I) and PROMISE_RE.search(p["text"]):
            return {"id": p["id"], "ts": p["ts"], "text": p["text"][:180]}
    return None


def hourly_curve(resets, days_ahead=10, mult=1.0, now=None):
    ref = now or NOW
    hazard = hazard_table(resets, now=ref)
    hour_w = hour_weights(resets, now=ref)
    wd_w = weekday_weights(resets, now=ref)
    last = resets[-1]
    age_days = (ref - last).total_seconds() / 86400
    curve = []
    surv = 1.0
    cur = ref
    for step in range(days_ahead * 24):
        age = age_days + step / 24
        day_idx = int(age)
        h_day = min(0.95, hazard.get(day_idx, 0.02) * mult)
        # split the day's hazard over hours: shares sum to 1 inside the day
        weights = []
        for h in range(24):
            wd_ratio = (wd_w.get(cur.weekday(), 1 / 7) * 7) ** 0.2
            weights.append(hour_w[h] * wd_ratio)
        norm = sum(weights) or 1.0
        share = weights[cur.hour] / norm
        h_hour = 1 - (1 - h_day) ** share
        p = surv * h_hour
        surv *= (1 - h_hour)
        curve.append({"t": cur.isoformat(), "p": round(p, 6), "surv": round(surv, 6)})
        cur += dt.timedelta(hours=1)
    return curve


def p_within(curve, hours):
    if not curve:
        return 0.0
    idx = min(hours, len(curve)) - 1
    return 1 - curve[idx]["surv"]


def daily_curve(resets, days_ahead=21, mult=1.0, now=None):
    """Cumulative P(at least one reset by end of day d) using the day-level hazard."""
    ref = now or NOW
    hazard = hazard_table(resets, now=ref)
    last = resets[-1]
    age_days = (ref - last).total_seconds() / 86400
    curve = []
    surv = 1.0
    for step in range(days_ahead):
        age = age_days + step
        h = min(0.9, hazard.get(int(age), 0.02) * mult)
        surv *= (1 - h)
        curve.append({"date": (ref + dt.timedelta(days=step + 1)).date().isoformat(),
                      "p": round(min(1 - surv, 1 - surv), 4)})
    return curve


def daily_p_within(curve, days):
    if not curve:
        return 0.0
    return curve[min(days, len(curve)) - 1]["p"]


def forecast(resets, posts, days_ahead=10):
    hazard = hazard_table(resets)
    promise = pending_promise(posts, resets)
    mult = 1.35 if promise else 1.0  # a live commitment pulls probability forward

    curve = hourly_curve(resets, days_ahead, mult)
    p24, p48, p72 = p_within(curve, 24), p_within(curve, 48), p_within(curve, 72)
    p7d = p_within(curve, 7 * 24)
    best_day = max(range(days_ahead), key=lambda d: sum(c["p"] for c in curve[d * 24:(d + 1) * 24]))
    day_slice = curve[best_day * 24:(best_day + 1) * 24]
    best_hour = max(range(len(day_slice)), key=lambda i: day_slice[i]["p"])
    modal = parse_ts(day_slice[best_hour]["t"])
    last = resets[-1]

    total_gaps = [(b - a).total_seconds() / 86400 for a, b in zip(resets, resets[1:])]
    recent_gaps = total_gaps[-6:]
    return {
        "generated_at": NOW.isoformat(),
        "generated_at_local": local(NOW).strftime("%Y-%m-%d %H:%M"),
        "last_reset": last.isoformat(),
        "last_reset_local": local(last).strftime("%Y-%m-%d %H:%M"),
        "timezone": "UTC+8",
        "hours_since_last_reset": round((NOW - last).total_seconds() / 3600, 2),
        "reset_count": len(resets),
        "mean_gap_days": round(sum(total_gaps) / len(total_gaps), 2),
        "median_gap_days": round(sorted(total_gaps)[len(total_gaps) // 2], 2),
        "recent_mean_gap_days": round(sum(recent_gaps) / len(recent_gaps), 2),
        "p_24h": round(p24, 4),
        "p_48h": round(p48, 4),
        "p_72h": round(p72, 4),
        "p_7d": round(p7d, 4),
        "modal_reset_at": modal.isoformat(),
        "modal_reset_local": local(modal).strftime("%Y-%m-%d %H:%M"),
        "pending_promise": promise,
        "hazard_by_day": {str(k): round(v, 4) for k, v in hazard.items()},
        "hour_prior": {str(h): round(v, 4) for h, v in sorted(hour_weights(resets).items())},
        "weekly": [],
        "curve": curve,
    }


def weekly_rollup(curve):
    out = defaultdict(float)
    for c in curve:
        out[c["t"][:10]] += c["p"]
    return [{"date": d, "p": round(min(1.0, v), 4)} for d, v in sorted(out.items())]


# ---------------------------------------------------------------- reset signals

SIGNAL_LABELS = {
    "announce": "公告", "related": "相关", "reset_post": "重置帖",
    "talk": "重置话题", "note": "镜像备注", "mention": "提到重置",
}
SIGNAL_RANK = ["announce", "related", "reset_post", "talk", "note", "mention"]
RESET_WORD = re.compile(r"\breset", re.I)


def signals(posts, events, days=14, baseline_days=28, now=None):
    """Reset chatter that is not itself a verified reset.

    Sources: the mirror feed's announce / related / note entries, posts the mirror
    tags "Reset" or "Reset talk", and untagged posts that say "reset". Shown next
    to the forecast as a radar; the hazard model does not read them.
    """
    ref = now or NOW
    window_start = ref - dt.timedelta(days=days)
    base_start = ref - dt.timedelta(days=days + baseline_days)
    verified = {e["id"] for e in events if e["kind"] in ("reset", "banked") and e.get("id")}
    resets = reset_times(events)
    last = resets[-1] if resets else None
    found = {}

    def add(key, ts, kind, text, url, source, prefer_text=False):
        t = parse_ts(ts)
        if key in verified or t < base_start or t > ref:
            return
        cur = found.get(key)
        if cur is None:
            found[key] = {"id": key, "t": t, "kind": kind, "text": text, "url": url, "sources": [source]}
            return
        if SIGNAL_RANK.index(kind) < SIGNAL_RANK.index(cur["kind"]):
            cur["kind"] = kind
        if prefer_text and text:
            cur["text"], cur["url"] = text, url or cur["url"]
        if source not in cur["sources"]:
            cur["sources"].append(source)

    for e in events:
        if e["kind"] in ("announce", "related", "note"):
            add(e.get("id") or e["ts"], e["ts"], e["kind"], e["title"],
                e.get("url") or e.get("mirror_url", ""), "feed")
    for p in posts:
        if p.get("pill_kind") == "reset":
            kind = "reset_post"
        elif p.get("pill_kind") == "codex":
            kind = "talk"
        elif RESET_WORD.search(p["text"]):
            kind = "mention"
        else:
            continue
        add(p["id"], p["ts"], kind, p["text"], p["url"], "page", prefer_text=True)

    rows = sorted(found.values(), key=lambda r: r["t"], reverse=True)
    recent = [r for r in rows if r["t"] >= window_start]
    in_base = sum(1 for r in rows if r["t"] < window_start)
    base_per_day = in_base / baseline_days

    def count(hours):
        return sum(1 for r in recent if (ref - r["t"]).total_seconds() <= hours * 3600)

    c24 = count(24)
    if c24 >= max(3, 2 * base_per_day):
        level = "high"
    elif c24 >= max(1, base_per_day):
        level = "elevated"
    else:
        level = "quiet"
    items = [{
        "id": r["id"],
        "ts": r["t"].isoformat(),
        "ts_local": local(r["t"]).strftime("%Y-%m-%d %H:%M"),
        "kind": r["kind"],
        "label": SIGNAL_LABELS[r["kind"]],
        "text": r["text"] if len(r["text"]) <= 240 else r["text"][:239].rstrip() + "…",
        "url": r["url"],
        "sources": r["sources"],
        "forward": bool(PROMISE_RE.search(r["text"])),
        "after_last_reset": bool(last and r["t"] > last),
        "age_hours": round((ref - r["t"]).total_seconds() / 3600, 1),
    } for r in recent]
    return {
        "window_days": days,
        "count_24h": c24,
        "count_72h": count(72),
        "count_7d": count(24 * 7),
        "since_last_reset": sum(1 for i in items if i["after_last_reset"]),
        "baseline_per_day": round(base_per_day, 2),
        "level": level,
        "items": items[:40],
    }


# ---------------------------------------------------------------- backtest

def backtest(resets, posts, days=45):
    """Walk-forward: refit on resets strictly before each hour block, score next-24h probability."""
    if len(resets) < 8:
        return None
    start = max(resets[3], NOW - dt.timedelta(days=days))
    rows = []
    day = start
    while day < NOW - dt.timedelta(days=1):
        past = [t for t in resets if t <= day]
        if len(past) < 6:
            day += dt.timedelta(days=1)
            continue
        curve = daily_curve(past, days_ahead=1, now=day)
        p = daily_p_within(curve, 1)
        actual = 1 if any(day < t <= day + dt.timedelta(days=1) for t in resets) else 0
        rows.append((p, actual))
        day += dt.timedelta(days=1)
    return score(rows)


def score(rows):
    if not rows:
        return None
    brier = sum((p - a) ** 2 for p, a in rows) / len(rows)
    base = sum(a for _, a in rows) / len(rows)
    brier_base = sum((base - a) ** 2 for _, a in rows) / len(rows)
    eps = 1e-9
    ll = -sum(a * math.log(p + eps) + (1 - a) * math.log(1 - p + eps) for p, a in rows) / len(rows)
    ll_base = -sum(a * math.log(base + eps) + (1 - a) * math.log(1 - base + eps) for _, a in rows) / len(rows)
    return {
        "days": len(rows),
        "brier": round(brier, 4),
        "brier_baseline": round(brier_base, 4),
        "logloss": round(ll, 4),
        "logloss_baseline": round(ll_base, 4),
        "skill": round(1 - ll / ll_base, 3) if ll_base else None,
        "base_rate": round(base, 4),
    }


# ---------------------------------------------------------------- hot words

def tokens(text):
    text = URL_RE.sub(" ", text)
    return [w.lower().strip("'") for w in WORD_RE.findall(text)]


def terms(text):
    """Content tokens: mentions and handles are pulled out separately."""
    text = MENTION_RE.sub(" ", text)
    out = []
    for w in tokens(text):
        if len(w) < 3 or w.isdigit() or w in STOP or w in GENERIC:
            continue
        if "'" in w:
            w = w.split("'")[0]
            if len(w) < 3 or w in STOP or w in GENERIC:
                continue
        out.append(w)
    return out


def features(text):
    """Unigrams plus adjacent bigrams, so phrases like 'global reset' can surface."""
    uni = terms(text)
    bi = [f"{a} {b}" for a, b in zip(uni, uni[1:])]
    return uni + bi


def hotwords(posts, window_days=7):
    cut = NOW - dt.timedelta(days=window_days)
    base_cut = NOW - dt.timedelta(days=window_days + 28)
    recent, base = Counter(), Counter()
    recent_docs, base_docs = defaultdict(list), defaultdict(list)
    for p in posts:
        t = parse_ts(p["ts"])
        feats = features(p["text"])
        if t >= cut:
            recent.update(feats)
            for w in set(feats):
                recent_docs[w].append(p)
        elif t >= base_cut:
            base.update(feats)
            for w in set(feats):
                base_docs[w].append(p)
    n_recent, n_base = sum(recent.values()), sum(base.values())
    rows = []
    for w, c in recent.items():
        is_bigram = " " in w
        if c < (2 if is_bigram else 3):
            continue
        expected = (base[w] / n_base) * n_recent if n_base else 0.0
        lift = math.log2((c + 0.5) / (expected + 0.5))
        doc = recent_docs[w][0]
        rows.append({
            "term": w,
            "kind": "phrase" if is_bigram else "word",
            "count_7d": c,
            "count_28d_before": base[w],
            "lift": round(lift, 2),
            "docs": len(recent_docs[w]),
            "share": round(c / max(1, n_recent), 4),
            "sample": doc["text"][:180],
            "sample_url": doc["url"],
            "sample_ts": doc["ts"],
        })
    rows.sort(key=lambda r: (-r["lift"], -r["count_7d"]))
    surge = rows[:30]
    top = sorted([r for r in rows if r["kind"] == "word"], key=lambda r: -r["count_7d"])[:30]
    return {"window_days": window_days, "surge": surge, "top": top,
            "tokens_recent": n_recent, "tokens_base": n_base}


def mentions(posts, window_days=7):
    """Handles: who he replies to, and whom he names in post text."""
    cut = NOW - dt.timedelta(days=window_days)
    replies, named = Counter(), Counter()
    for p in posts:
        if parse_ts(p["ts"]) < cut:
            continue
        if p.get("reply_to"):
            replies[p["reply_to"]] += 1
        for h in MENTION_RE.findall(p["text"]):
            named[h.lstrip("@")] += 1
    rows = []
    for h in set(replies) | set(named):
        if h.lower() == "thsottiaux":  # self-replies in a thread are not "other accounts"
            continue
        rows.append({"handle": h, "replies": replies[h], "named": named[h],
                     "total": replies[h] + named[h]})
    rows.sort(key=lambda r: (-r["total"], -r["replies"]))
    return rows[:25]


def reset_lexicon(posts, window_days=14):
    """How reset language itself is moving: counts per week for the core terms."""
    words = ["reset", "resets", "reseted", "banked", "eod", "propagate", "propagated",
             "usage", "limit", "limits", "vote", "day", "series"]
    buckets = defaultdict(Counter)
    for p in posts:
        t = parse_ts(p["ts"])
        if (NOW - t).days > window_days * 4:
            continue
        week = (NOW - t).days // window_days
        low = p["text"].lower()
        for w in words:
            if re.search(rf"\b{w}\b", low):
                buckets[week][w] += 1
    out = []
    for week in sorted(buckets):
        out.append({"week": week, "label": "最近7天" if week == 0 else f"{week*7}天前",
                    **{w: buckets[week][w] for w in words}})
    return out


def reset_day_posts(posts, resets, limit=12):
    keys = {local(t).date().isoformat() for t in resets}
    rows = [p for p in posts if local(p["ts"]).date().isoformat() in keys
            and (p["pill"] or "reset" in p["text"].lower())]
    rows.sort(key=lambda p: p["ts"], reverse=True)
    return [{"ts": local(p["ts"]).strftime("%Y-%m-%d %H:%M"), "text": p["text"][:200], "url": p["url"],
             "likes": p.get("likes", 0), "replies": p.get("replies", 0)} for p in rows[:limit]]


def topics(posts, days=14):
    cut = NOW - dt.timedelta(days=days)
    out = []
    for name, keys in TOPIC_RULES:
        hits = [p for p in posts if parse_ts(p["ts"]) >= cut and any(k in p["text"].lower() for k in keys)]
        out.append({"topic": name, "posts": len(hits),
                    "share": round(len(hits) / max(1, sum(1 for p in posts if parse_ts(p["ts"]) >= cut)), 3),
                    "examples": [{"text": h["text"][:140], "url": h["url"], "ts": h["ts"]} for h in hits[:3]]})
    out.sort(key=lambda r: -r["posts"])
    return out


def daily_series(posts, resets, banked=()):
    per = defaultdict(lambda: {"posts": 0, "replies": 0, "likes": 0, "replies_received": 0})
    for p in posts:
        d = per[local(p["ts"]).date().isoformat()]
        d["posts"] += 1
        d["replies" if p["is_reply"] else "posts"] += 0  # keep original count below
        d["likes"] += p.get("likes", 0)
        d["replies_received"] += p.get("replies", 0)
    counts = Counter(local(p["ts"]).date().isoformat() for p in posts)
    reply_counts = Counter(local(p["ts"]).date().isoformat() for p in posts if p["is_reply"])
    reset_days = Counter(local(t).date().isoformat() for t in resets)
    banked_days = Counter(local(e["ts"]).date().isoformat() for e in banked)
    days = sorted(counts)
    return [{"date": d, "posts": counts[d], "replies": reply_counts[d],
             "likes": per[d]["likes"], "engagement_replies": per[d]["replies_received"],
             "reset": reset_days.get(d, 0), "banked": banked_days.get(d, 0)} for d in days]


def main():
    posts = load_jsonl(PROC / "posts.jsonl")
    events = json.loads((PROC / "resets.json").read_text(encoding="utf-8"))
    resets = reset_times(events)

    fc = forecast(resets, posts)
    fc["weekly"] = weekly_rollup(fc["curve"])
    fc["backtest"] = backtest(resets, posts)
    fc["signals"] = signals(posts, events)
    (PROC / "forecast.json").write_text(json.dumps(fc, ensure_ascii=False, indent=1), encoding="utf-8")

    hw = hotwords(posts)
    hw["topics"] = topics(posts)
    hw["mentions"] = mentions(posts)
    hw["reset_lexicon"] = reset_lexicon(posts)
    hw["reset_posts"] = reset_day_posts(posts, resets)
    (PROC / "hotwords.json").write_text(json.dumps(hw, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {
        "generated_at": NOW.isoformat(),
        "generated_at_local": local(NOW).strftime("%Y-%m-%d %H:%M"),
        "timezone": "UTC+8",
        "posts": len(posts),
        "replies": sum(1 for p in posts if p["is_reply"]),
        "days_covered": len({p["date"] for p in posts}),
        "first_post": posts[0]["ts"],
        "last_post": posts[-1]["ts"],
        "resets_tracked": len(resets),
        "p_24h": fc["p_24h"],
        "p_48h": fc["p_48h"],
        "modal_reset_at": fc["modal_reset_at"],
        "backtest": fc["backtest"],
        "top_terms": hw["top"][:12],
        "surge_terms": hw["surge"][:12],
        "topics": hw["topics"],
        "banked_tracked": sum(1 for e in events if e["kind"] == "banked"),
        "daily": daily_series(posts, resets, [e for e in events if e["kind"] == "banked"]),
    }
    (PROC / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"p24={fc['p_24h']:.2f} p48={fc['p_48h']:.2f} modal={fc['modal_reset_at']}")
    print(f"backtest={fc['backtest']}")
    sg = fc["signals"]
    print(f"signals: 24h={sg['count_24h']} 72h={sg['count_72h']} level={sg['level']} "
          f"since_last_reset={sg['since_last_reset']}")
    print(f"top: {[t['term'] for t in hw['top'][:12]]}")
    print(f"surge: {[t['term'] for t in hw['surge'][:12]]}")


if __name__ == "__main__":
    main()
