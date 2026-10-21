import json
import unittest

from tests import helpers  # noqa: F401
import changed

POSTS = '{"id": "1", "text": "Day 15/ reset", "likes": 10}\n'
EVENTS = json.dumps([{"id": "9", "kind": "reset", "ts": "2026-10-20T06:33:48Z", "title": "Day 15/"}])
ALERTS = json.dumps({"bootstrapped_at": "x", "seen": ["reset:9"], "alerts": [],
                     "summary": {"checked_at": "2026-10-21T09:00:00+00:00"}})
HEALTH = json.dumps({"feed": {"ok": True, "consecutive_failures": 0, "at": "2026-10-21T09:00:00+00:00"}})
BASE = {"data/processed/posts.jsonl": POSTS, "data/processed/resets.json": EVENTS,
        "data/state/alerts.json": ALERTS, "data/state/health.json": HEALTH}


def diff(**updates):
    new = dict(BASE)
    for name, text in updates.items():
        path = next(p for p in BASE if p.endswith(name.replace("_", ".", 1)))
        new[path] = text
    return changed.changed(old=BASE.get, new=new.get)


class ChangedTest(unittest.TestCase):
    def test_timestamps_and_counts_alone_do_not_commit(self):
        self.assertEqual(diff(
            posts_jsonl='{"id": "1", "text": "Day 15/ reset", "likes": 99}\n',
            alerts_json=ALERTS.replace("09:00", "09:05"),
            health_json=HEALTH.replace("09:00", "09:05"),
        ), [])

    def test_new_post_commits(self):
        self.assertEqual(diff(posts_jsonl=POSTS + '{"id": "2", "text": "I demand a reset"}\n'),
                         ["data/processed/posts.jsonl"])

    def test_new_alert_key_commits(self):
        self.assertEqual(diff(alerts_json=ALERTS.replace('["reset:9"]', '["reset:9", "reset:10"]')),
                         ["data/state/alerts.json"])

    def test_failure_streak_commits_until_capped(self):
        def health(n):
            return json.dumps({"feed": {"ok": n == 0, "consecutive_failures": n}})
        self.assertEqual(changed.changed(old={**BASE, "data/state/health.json": health(2)}.get,
                                         new={**BASE, "data/state/health.json": health(3)}.get),
                         ["data/state/health.json"])
        self.assertEqual(changed.changed(old={**BASE, "data/state/health.json": health(3)}.get,
                                         new={**BASE, "data/state/health.json": health(4)}.get), [])

    def test_missing_file_at_head_commits(self):
        self.assertEqual(changed.changed(old={**BASE, "data/state/alerts.json": None}.get, new=BASE.get),
                         ["data/state/alerts.json"])


if __name__ == "__main__":
    unittest.main()
