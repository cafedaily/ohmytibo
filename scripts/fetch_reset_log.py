#!/usr/bin/env python3
"""Fetch the tiboreset.com Atom feed and merge it into an append-only reset-event log.

The feed only carries the latest ~50 entries, so data/processed/resets.json is the
durable record: entries are added or updated by id and never dropped when they
age out of the feed. Entries the mirror observed itself (no rel="via" link to an
X post) are kept under the mirror's own id instead of being discarded.
"""
import hashlib
import html
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import state  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "feed.xml"
OUT = ROOT / "data" / "processed" / "resets.json"
FEED_URL = "https://tiboreset.com/feed.xml"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def fetch():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(body)
    return body.decode("utf-8", "replace")


def links(entry):
    """rel -> href for every <link> in an entry; Atom's default rel is "alternate"."""
    out = {}
    for attrs in re.findall(r"<link\b([^>]*?)/?>", entry):
        a = dict(re.findall(r'([\w:-]+)="([^"]*)"', attrs))
        if "href" in a:
            out.setdefault(a.get("rel", "alternate"), html.unescape(a["href"]))
    return out


def entry_id(rels, atom_id, published, title):
    """X status id from rel="via"; else the mirror's /r/<id>; else the Atom <id>; else a content hash."""
    via = rels.get("via", "")
    if via:
        return via.split("?")[0].rstrip("/").rsplit("/", 1)[-1], "x"
    m = re.search(r"/r/([A-Za-z0-9_-]+)", rels.get("alternate", ""))
    if m:
        return f"r-{m.group(1)}", "mirror"
    seed = atom_id or f"{published}|{title}"
    return "h-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12], "mirror"


def parse(text):
    out = []
    for e in re.findall(r"<entry\b[^>]*>(.*?)</entry>", text, re.S):
        def one(tag):
            m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", e, re.S)
            return html.unescape(m.group(1)).strip() if m else ""

        pub = one("published")
        if not pub:
            continue
        cats = re.findall(r'<category term="([^"]+)"', e)
        kind = "reset" if "reset" in cats else ("banked" if "banked" in cats else
                                                ("announce" if "announce" in cats else
                                                 ("related" if "related" in cats else "note")))
        title = re.sub(r"^\[[^\]]+\]\s*", "", one("title"))
        rels = links(e)
        pid, source = entry_id(rels, one("id"), pub, title)
        mirror_url = rels.get("alternate", "")
        out.append({
            "id": pid,
            "ts": pub,
            "date": pub[:10],
            "hour_utc": int(pub[11:13]),
            "minute_utc": int(pub[14:16]),
            "kind": kind,
            "title": title,
            "source": source,
            "url": f"https://x.com/thsottiaux/status/{pid}" if source == "x" else mirror_url,
            "mirror_url": mirror_url,
        })
    out.sort(key=lambda r: r["ts"])
    return out


def merge(existing, fresh, seen_at):
    """Fold fresh feed rows into the stored log without ever dropping a stored row.

    A fresh row replaces the stored row with the same id, or - for rows stored before
    mirror ids were backfilled (id "") - the stored row with the same timestamp and kind.
    """
    rows = [dict(r) for r in existing]
    by_id = {r["id"]: i for i, r in enumerate(rows) if r.get("id")}
    by_slot = {(r["ts"], r["kind"]): i for i, r in enumerate(rows)}
    added = []
    for f in fresh:
        i = by_id.get(f["id"])
        if i is None:
            i = by_slot.get((f["ts"], f["kind"]))
        if i is None:
            row = {**f, "first_seen": seen_at}
            by_id[row["id"]] = by_slot[(row["ts"], row["kind"])] = len(rows)
            rows.append(row)
            added.append(row)
        else:
            rows[i] = {**rows[i], **f, "first_seen": rows[i].get("first_seen")}
            by_id[f["id"]] = by_slot[(f["ts"], f["kind"])] = i
    rows.sort(key=lambda r: r["ts"])
    return rows, added


def main():
    now = state.now_iso()
    existing = state.load_json(OUT, [])
    status = {"at": now, "ok": False, "source": None, "entries": 0, "new": 0, "error": None}
    text = None
    try:
        text = fetch()
        status["source"] = "network"
    except Exception as exc:  # keep working from the cached copy or the stored log
        status["error"] = f"{type(exc).__name__}: {exc}"[:200]
        if RAW.exists():
            text = RAW.read_text(encoding="utf-8")
            status["source"] = "cache"
        print(f"feed fetch failed ({status['error']}); using {status['source'] or 'stored log only'}")
    fresh = parse(text) if text else []
    rows, added = merge(existing, fresh, now)
    status.update(ok=status["source"] == "network", entries=len(fresh), new=len(added), total=len(rows))
    state.write_json(OUT, rows)
    state.update_health("feed", status)
    resets = sum(1 for r in rows if r["kind"] == "reset")
    banked = sum(1 for r in rows if r["kind"] == "banked")
    print(f"feed {len(fresh)} entries, {len(added)} new; log {len(rows)} events: "
          f"{resets} resets, {banked} banked -> {OUT}")


if __name__ == "__main__":
    main()
