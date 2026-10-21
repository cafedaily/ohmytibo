import datetime as dt
import unittest

from tests import helpers  # noqa: F401
import alert

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 20, 7, 0, tzinfo=UTC)
FC = {"p_24h": 0.11, "last_reset": "2026-10-18T00:00:00+00:00", "hours_since_last_reset": 55,
      "modal_reset_at": "2026-10-22T20:10:00+00:00", "signals": {"items": []}}
OLD = [{"id": "100", "ts": "2026-10-18T00:00:00Z", "kind": "reset", "title": "old reset",
        "url": "https://x.com/thsottiaux/status/100"}]
NEW = OLD + [{"id": "2112432076767289678", "ts": "2026-10-20T06:33:48Z", "kind": "reset",
              "title": "Day 15/ ... and reset. Enjoy.", "url": "https://x.com/thsottiaux/status/2112432076767289678"}]


class Recorder:
    def __init__(self, fail_hosts=()):
        self.calls, self.fail_hosts = [], fail_hosts

    def __call__(self, url, payload, timeout=15):
        if any(h in url for h in self.fail_hosts):
            raise RuntimeError(f"HTTP 500 from {url}")
        self.calls.append((url, payload))


def bootstrapped():
    st = {}
    alert.run(FC, OLD, {}, st, {}, T0)
    return st


class AlertTest(unittest.TestCase):
    def test_first_run_only_records_existing_events(self):
        st = {}
        fresh = alert.run(FC, OLD, {}, st, {}, T0)
        self.assertEqual(fresh, [])
        self.assertIn("reset:100", st["seen"])
        self.assertTrue(st["bootstrapped_at"])

    def test_no_channel_is_never_recorded_as_sent(self):
        st = bootstrapped()
        fresh = alert.run(FC, NEW, {}, st, {}, T0 + dt.timedelta(minutes=10))
        self.assertEqual(len(fresh), 1)
        a = st["alerts"][0]
        self.assertEqual(a["status"], "pending")
        self.assertEqual(a["reason"], "no_channel")
        self.assertEqual(a["deliveries"], {})
        self.assertFalse(st["summary"]["configured"])
        self.assertIsNone(st["summary"]["last_sent"])
        self.assertEqual(st["summary"]["pending"], 1)

    def test_pending_alert_is_delivered_once_a_channel_appears(self):
        st = bootstrapped()
        alert.run(FC, NEW, {}, st, {}, T0 + dt.timedelta(minutes=10))
        post = Recorder()
        env = {"DISCORD_WEBHOOK_URL": "https://discord.example/hook/abc"}
        alert.run(FC, NEW, {}, st, env, T0 + dt.timedelta(hours=2), post)
        self.assertEqual(st["alerts"][0]["status"], "sent")
        self.assertEqual(len(post.calls), 1)
        self.assertIn("检测到全局重置", post.calls[0][1]["content"])
        alert.run(FC, NEW, {}, st, env, T0 + dt.timedelta(hours=3), post)
        self.assertEqual(len(post.calls), 1, "a sent alert is not sent again")

    def test_pending_alert_expires_after_ttl(self):
        st = bootstrapped()
        alert.run(FC, NEW, {}, st, {}, T0 + dt.timedelta(minutes=10))
        alert.run(FC, NEW, {}, st, {}, T0 + dt.timedelta(hours=alert.TTL_HOURS + 1))
        self.assertEqual(st["alerts"][0]["status"], "expired")
        self.assertEqual(st["summary"]["undelivered_7d"], 1)

    def test_partial_delivery_retries_only_the_failed_channel(self):
        st = bootstrapped()
        env = {"DISCORD_WEBHOOK_URL": "https://discord.example/hook/abc",
               "BARK_URL": "https://bark.example/SECRETKEY"}
        alert.run(FC, NEW, {}, st, env, T0 + dt.timedelta(minutes=10), Recorder(fail_hosts=("bark",)))
        a = st["alerts"][0]
        self.assertEqual(a["status"], "partial")
        self.assertNotIn("SECRETKEY", a["deliveries"]["bark"]["error"])
        retry = Recorder()
        alert.run(FC, NEW, {}, st, env, T0 + dt.timedelta(minutes=20), retry)
        self.assertEqual([u for u, _ in retry.calls], ["https://bark.example/SECRETKEY"])
        self.assertEqual(a["status"], "sent")

    def test_late_surfacing_old_event_is_not_pushed(self):
        st = bootstrapped()
        late = OLD + [{"id": "50", "ts": "2026-10-01T00:00:00Z", "kind": "banked", "title": "old banked"}]
        self.assertEqual(alert.run(FC, late, {}, st, {}, T0 + dt.timedelta(minutes=10)), [])
        self.assertIn("banked:50", st["seen"])

    def test_probability_threshold_fires_once_per_reset_cycle(self):
        st = bootstrapped()
        hot = {**FC, "p_24h": 0.42}
        fresh = alert.run(hot, OLD, {}, st, {}, T0 + dt.timedelta(minutes=10))
        self.assertEqual([a["kind"] for a in fresh], ["probability"])
        self.assertEqual(alert.run(hot, OLD, {}, st, {}, T0 + dt.timedelta(minutes=20)), [])

    def test_feed_failure_streak_alerts(self):
        st = bootstrapped()
        health = {"feed": {"consecutive_failures": 3, "last_ok": "2026-10-20T01:00:00+00:00", "error": "URLError"}}
        fresh = alert.run(FC, OLD, health, st, {}, T0 + dt.timedelta(minutes=10))
        self.assertEqual([a["kind"] for a in fresh], ["health"])


if __name__ == "__main__":
    unittest.main()
