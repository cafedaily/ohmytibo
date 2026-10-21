#!/usr/bin/env python3
"""Decide whether a fast refresh run changed anything worth a commit.

Fast runs (every 5 minutes) always redeploy the page, but commit only when stored
data moved: a new or edited post, a new or changed feed event, alert state (seen
keys, delivery records), or a source flipping between ok and failing. Timestamps,
engagement counts and recomputed probabilities alone do not count; the next full
run commits them. Prints "yes" or "no"; the reasons go to stderr.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def at_head(path):
    r = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def in_tree(path):
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.exists() else None


def posts_key(text):
    rows = (json.loads(line) for line in text.splitlines() if line.strip())
    return {(r["id"], r.get("text")) for r in rows}


def events_key(text):
    return {(e.get("id"), e["kind"], e["ts"], e.get("title")) for e in json.loads(text)}


def alerts_key(text):
    d = json.loads(text)
    return d.get("bootstrapped_at"), d.get("seen"), d.get("alerts")


def health_key(text):
    # the streak is capped so a long outage commits three times, not every run
    return {k: (v.get("ok"), min(v.get("consecutive_failures", 0), 3)) for k, v in json.loads(text).items()}


CHECKS = {
    "data/processed/posts.jsonl": posts_key,
    "data/processed/resets.json": events_key,
    "data/state/alerts.json": alerts_key,
    "data/state/health.json": health_key,
}


def changed(old=at_head, new=in_tree):
    reasons = []
    for path, key in CHECKS.items():
        a, b = old(path), new(path)
        if a is None or b is None:
            if a != b:
                reasons.append(path)
            continue
        try:
            if key(a) != key(b):
                reasons.append(path)
        except (ValueError, KeyError, AttributeError):
            reasons.append(path)
    return reasons


def main():
    reasons = changed()
    print("yes" if reasons else "no")
    if reasons:
        print("changed: " + ", ".join(reasons), file=sys.stderr)


if __name__ == "__main__":
    main()
