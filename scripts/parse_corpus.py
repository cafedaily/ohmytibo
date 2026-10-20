#!/usr/bin/env python3
"""Parse cached tiboreset.com day pages into a JSONL corpus of Tibo's posts."""
import glob
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAYS = ROOT / "data" / "raw" / "days"
OUT = ROOT / "data" / "processed" / "posts.jsonl"

ARTICLE = re.compile(r'<article class="log-item xp-row".*?</article>', re.S)
TAG = re.compile(r"<[^>]+>")


def clean(fragment):
    txt = re.sub(r"<br\s*/?>", "\n", fragment)
    txt = TAG.sub("", txt)
    return html.unescape(txt).strip()


def parse_article(a):
    m = re.search(r'data-id="(\d+)"', a)
    if not m:
        return None
    pid = m.group(1)
    tm = re.search(r'<time class="log-item-abs" datetime="([^"]+)"', a)
    if not tm:
        return None
    ts = tm.group(1)
    is_reply = 'data-reply="1"' in a
    reply_to = None
    rm = re.search(r'<p class="help xp-replying">Replying to\s*<a [^>]*>@?([^<]+)</a>', a)
    if rm:
        reply_to = rm.group(1).strip()
    pm = re.search(r'<span class="pill ([^"]*)">([^<]*)</span>', a)
    pill = pm.group(2).strip() if pm else ""
    pill_kind = pm.group(1).strip() if pm else ""
    tm2 = re.search(r'<p class="log-item-text[^"]*">(.*?)</p>', a, re.S)
    text = clean(tm2.group(1)) if tm2 else ""
    cm = re.search(r'<p class="help xp-counts"[^>]*>([\d,]+) replies · ([\d,]+) reposts · ([\d,]+) likes</p>', a)
    counts = {
        "replies": int(cm.group(1).replace(",", "")),
        "reposts": int(cm.group(2).replace(",", "")),
        "likes": int(cm.group(3).replace(",", "")),
    } if cm else {}
    counts_as_of = None
    cam = re.search(r'xp-counts" title="Counts as of ([^"]+)"', a)
    if cam:
        counts_as_of = cam.group(1)
    return {
        "id": pid,
        "ts": ts,
        "date": ts[:10],
        "hour": int(ts[11:13]),
        "is_reply": is_reply,
        "reply_to": reply_to,
        "pill": pill,
        "pill_kind": pill_kind,
        "text": text,
        "url": f"https://x.com/thsottiaux/status/{pid}",
        **counts,
        "counts_as_of": counts_as_of,
    }


def main():
    seen = {}
    for fp in sorted(glob.glob(str(DAYS / "*.html"))):
        src = pathlib.Path(fp).read_text(encoding="utf-8", errors="replace")
        for a in ARTICLE.findall(src):
            rec = parse_article(a)
            if rec:
                rec["source_file"] = pathlib.Path(fp).name
                seen[rec["id"]] = rec
    rows = sorted(seen.values(), key=lambda r: r["ts"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    dates = sorted({r["date"] for r in rows})
    print(f"{len(rows)} posts, {len(dates)} days, {dates[0]} .. {dates[-1]}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
