import datetime as dt
import unittest

from tests import helpers  # noqa: F401
import analyze

NOW = dt.datetime(2026, 10, 21, 8, 0, tzinfo=dt.timezone.utc)
EVENTS = [
    {"id": "1", "ts": "2026-10-10T00:00:00Z", "kind": "reset", "title": "older reset"},
    {"id": "9", "ts": "2026-10-20T06:33:48Z", "kind": "reset", "title": "Day 15/ ... and reset"},
    {"id": "7", "ts": "2026-10-17T16:20:57Z", "kind": "related", "title": "Day 13/ Le limit reset",
     "url": "https://x.com/thsottiaux/status/7"},
    {"id": "r-n1", "ts": "2026-10-19T23:24:55Z", "kind": "note", "title": "banked landed on our accounts",
     "url": "https://tiboreset.com/r/n1"},
]


def post(pid, ts, text, pill_kind=""):
    return {"id": pid, "ts": ts, "text": text, "pill_kind": pill_kind,
            "url": f"https://x.com/thsottiaux/status/{pid}"}


POSTS = [
    post("9", "2026-10-20T06:33:48Z", "Day 15/ Nevermind ... and reset. Enjoy.", "reset"),
    post("7", "2026-10-17T16:20:57Z", "Day 13/ Le limit reset https://t.co/x", "codex"),
    post("20", "2026-10-21T06:49:00Z", "I demand a reset", "codex"),
    post("21", "2026-10-21T07:00:00Z", "my reset button works fine, will reset by EOD"),
    post("22", "2026-10-21T07:30:00Z", "Shipping a new model"),
]


class SignalsTest(unittest.TestCase):
    def setUp(self):
        self.sg = analyze.signals(POSTS, EVENTS, now=NOW)
        self.by_id = {i["id"]: i for i in self.sg["items"]}

    def test_verified_reset_is_not_a_signal(self):
        self.assertNotIn("9", self.by_id)

    def test_reset_talk_without_deadline_is_listed(self):
        it = self.by_id["20"]
        self.assertEqual(it["kind"], "talk")
        self.assertTrue(it["after_last_reset"])
        self.assertFalse(it["forward"])

    def test_feed_and_page_copies_of_one_post_merge(self):
        it = self.by_id["7"]
        self.assertEqual(it["kind"], "related")
        self.assertEqual(sorted(it["sources"]), ["feed", "page"])
        self.assertFalse(it["after_last_reset"])

    def test_mirror_note_and_untagged_mention(self):
        self.assertEqual(self.by_id["r-n1"]["kind"], "note")
        self.assertEqual(self.by_id["21"]["kind"], "mention")
        self.assertTrue(self.by_id["21"]["forward"])
        self.assertNotIn("22", self.by_id)

    def test_counts(self):
        self.assertEqual(self.sg["count_24h"], 2)
        self.assertEqual(self.sg["since_last_reset"], 2)
        self.assertEqual([i["id"] for i in self.sg["items"]][:2], ["21", "20"])


if __name__ == "__main__":
    unittest.main()
