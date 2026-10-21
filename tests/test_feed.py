import unittest

from tests import helpers  # noqa: F401
import fetch_reset_log as feed

FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>[Reset] Day 15/ Nevermind, we're still cooking... and reset.</title>
  <link rel="alternate" href="https://tiboreset.com/r/k3x9"/>
  <link rel="via" href="https://x.com/thsottiaux/status/2112432076767289678"/>
  <id>tag:tiboreset.com,2026:k3x9</id>
  <published>2026-10-20T06:33:48Z</published>
  <category term="reset"/>
</entry>
<entry>
  <title>[Banked] A new banked Codex reset landed on our monitoring accounts.</title>
  <link href="https://tiboreset.com/r/b77q" rel="alternate"/>
  <id>tag:tiboreset.com,2026:b77q</id>
  <published>2026-09-29T18:53:14Z</published>
  <category term="banked"/>
</entry>
<entry>
  <title>The banked reset Tibo announced landed on our monitoring accounts.</title>
  <id>tag:tiboreset.com,2026:n1</id>
  <published>2026-10-07T23:24:55Z</published>
  <category term="note"/>
</entry>
</feed>"""


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.rows = {r["ts"]: r for r in feed.parse(FEED)}

    def test_via_link_gives_x_status_id(self):
        r = self.rows["2026-10-20T06:33:48Z"]
        self.assertEqual(r["id"], "2112432076767289678")
        self.assertEqual(r["source"], "x")
        self.assertEqual(r["url"], "https://x.com/thsottiaux/status/2112432076767289678")
        self.assertEqual(r["kind"], "reset")
        self.assertTrue(r["title"].startswith("Day 15/"))

    def test_mirror_entry_without_via_keeps_mirror_id(self):
        r = self.rows["2026-09-29T18:53:14Z"]
        self.assertEqual(r["id"], "r-b77q")
        self.assertEqual(r["source"], "mirror")
        self.assertEqual(r["url"], "https://tiboreset.com/r/b77q")
        self.assertEqual(r["kind"], "banked")

    def test_entry_without_links_gets_stable_id(self):
        r = self.rows["2026-10-07T23:24:55Z"]
        self.assertTrue(r["id"].startswith("h-"))
        self.assertEqual(r["id"], {x["ts"]: x for x in feed.parse(FEED)}[r["ts"]]["id"])

    def test_no_entry_is_dropped(self):
        self.assertEqual(len(self.rows), 3)


class MergeTest(unittest.TestCase):
    def test_stored_rows_survive_when_they_leave_the_feed(self):
        old = [{"id": "111", "ts": "2026-06-28T23:54:07Z", "kind": "reset", "title": "old"}]
        rows, added = feed.merge(old, feed.parse(FEED), "2026-10-21T00:00:00+00:00")
        self.assertIn("111", {r["id"] for r in rows})
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(added), 3)
        self.assertEqual([r["ts"] for r in rows], sorted(r["ts"] for r in rows))

    def test_legacy_row_without_id_is_replaced_not_duplicated(self):
        legacy = [{"id": "", "ts": "2026-09-29T18:53:14Z", "kind": "banked", "title": "x", "url": ""}]
        rows, added = feed.merge(legacy, feed.parse(FEED), "2026-10-21T00:00:00+00:00")
        banked = [r for r in rows if r["kind"] == "banked"]
        self.assertEqual(len(banked), 1)
        self.assertEqual(banked[0]["id"], "r-b77q")
        self.assertNotIn(banked[0], added)

    def test_rerun_is_idempotent_and_keeps_first_seen(self):
        rows, _ = feed.merge([], feed.parse(FEED), "2026-10-21T00:00:00+00:00")
        again, added = feed.merge(rows, feed.parse(FEED), "2026-10-21T03:00:00+00:00")
        self.assertEqual(added, [])
        self.assertEqual(len(again), 3)
        self.assertTrue(all(r["first_seen"] == "2026-10-21T00:00:00+00:00" for r in again))


if __name__ == "__main__":
    unittest.main()
