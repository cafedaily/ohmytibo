#!/usr/bin/env python3
"""Fetch and parse the tiboreset.com Atom feed into a reset-event dataset."""
import datetime as dt
import html
import json
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "feed.xml"
OUT = ROOT / "data" / "processed" / "resets.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def fetch():
    req = urllib.request.Request("https://tiboreset.com/feed.xml", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        RAW.write_bytes(r.read())


def parse():
    s = RAW.read_text(encoding="utf-8")
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", s, re.S):
        def one(tag):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", e, re.S)
            return html.unescape(m.group(1)).strip() if m else ""

        pub = one("published")
        if not pub:
            continue
        cats = re.findall(r'<category term="([^"]+)"', e)
        kind = "reset" if "reset" in cats else ("banked" if "banked" in cats else
                                                ("announce" if "announce" in cats else
                                                 ("related" if "related" in cats else "note")))
        via = re.search(r'<link rel="via" href="([^"]+)"', e)
        pid = via.group(1).rsplit("/", 1)[-1] if via else ""
        title = one("title")
        title = re.sub(r"^\[[^\]]+\]\s*", "", title)
        out.append({
            "id": pid,
            "ts": pub,
            "date": pub[:10],
            "hour_utc": int(pub[11:13]),
            "minute_utc": int(pub[14:16]),
            "kind": kind,
            "title": title,
            "url": f"https://x.com/thsottiaux/status/{pid}" if pid else "",
        })
    out.sort(key=lambda r: r["ts"])
    return out


def main():
    try:
        fetch()
        print("fetched feed")
    except Exception as exc:  # keep working from the cached copy
        print(f"feed fetch failed ({exc}); using cache")
    rows = parse()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    resets = [r for r in rows if r["kind"] == "reset"]
    banked = [r for r in rows if r["kind"] == "banked"]
    print(f"{len(rows)} events: {len(resets)} resets, {len(banked)} banked -> {OUT}")


if __name__ == "__main__":
    main()
