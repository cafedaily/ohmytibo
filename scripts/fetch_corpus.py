#!/usr/bin/env python3
"""Fetch Tibo's (@thsottiaux) public posts/replies from the tiboreset.com mirror."""
import argparse
import datetime as dt
import pathlib
import re
import time
import urllib.error
import urllib.request

BASE = "https://tiboreset.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def get(url, retries=3):
    for i in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == retries - 1:
                raise
        except Exception:
            if i == retries - 1:
                raise
        time.sleep(2 + i * 3)
    return None


def day_url(d):
    return f"{BASE}/X-posts/{d.isoformat()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--out", default="data/raw/days")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(dt.timezone.utc).date()
    got = 0
    for i in range(args.days + 1):
        d = today - dt.timedelta(days=i)
        fp = out / f"{d.isoformat()}.html"
        if fp.exists() and not args.force and fp.stat().st_size > 5000:
            got += 1
            continue
        html = get(day_url(d))
        if html and 'class="log-item' in html:
            fp.write_text(html, encoding="utf-8")
            got += 1
            print(f"{d} ok {len(html)}")
        else:
            print(f"{d} empty/404")
        time.sleep(0.7)
    print(f"cached {got} day pages -> {out}")


if __name__ == "__main__":
    main()
