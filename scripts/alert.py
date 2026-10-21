#!/usr/bin/env python3
"""Turn pipeline output into push alerts and keep an honest record of what was delivered.

Channels are read from the environment (GitHub Actions secrets); none is required:
  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL, BARK_URL, ALERT_WEBHOOK_URL.

An alert is "sent" only when every configured channel accepted it, "partial" when
some did. With no channel configured it stays "pending" with reason "no_channel"
(shown on the dashboard's status card) - it is never recorded as delivered. Pending
alerts are retried on later runs and expire after TTL_HOURS without a delivery.

  python scripts/alert.py            detect, deliver, update data/state/alerts.json
  python scripts/alert.py --dry-run  print what would be sent; send nothing, write nothing
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import state  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
STATE_FILE = state.STATE / "alerts.json"
CST = dt.timezone(dt.timedelta(hours=8))

CHANNELS = (
    ("telegram", ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")),
    ("discord", ("DISCORD_WEBHOOK_URL",)),
    ("bark", ("BARK_URL",)),
    ("webhook", ("ALERT_WEBHOOK_URL",)),
)
SECRET_KEYS = [k for _, keys in CHANNELS for k in keys]
P24_THRESHOLDS = (0.30, 0.60)
EVENT_MAX_AGE_HOURS = 48  # older events that surface late are logged, not pushed
TTL_HOURS = 12
MAX_ATTEMPTS = 6
FEED_FAILURE_STREAK = 3
KEEP_ALERTS = 200
KEEP_SEEN = 2000


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def bjt(iso):
    return parse_ts(iso).astimezone(CST).strftime("%m-%d %H:%M")


def configured(env):
    return [name for name, keys in CHANNELS if all(env.get(k) for k in keys)]


def redact(msg, env):
    for k in SECRET_KEYS:
        v = env.get(k) or ""
        if len(v) >= 4:
            msg = msg.replace(v, "***")
    return msg


# ---------------------------------------------------------------- detection

def candidates(fc, events, health, now):
    """Every alert the current data justifies, keyed so each fires once."""
    out = []
    p24 = fc.get("p_24h", 0)
    for e in events:
        if e["kind"] not in ("reset", "banked"):
            continue
        age_h = (now - parse_ts(e["ts"])).total_seconds() / 3600
        out.append({
            "key": f"{e['kind']}:{e.get('id') or e['ts']}",
            "kind": e["kind"],
            "title": "检测到全局重置" if e["kind"] == "reset" else "检测到 banked 重置发放",
            "body": f"北京时间 {bjt(e['ts'])} · {e['title'][:160]}",
            "url": e.get("url") or e.get("mirror_url", ""),
            "stale": age_h > EVENT_MAX_AGE_HOURS,
        })
    promise = fc.get("pending_promise")
    if promise:
        out.append({
            "key": f"promise:{promise['id']}",
            "kind": "promise",
            "title": "出现未兑现的重置承诺",
            "body": f"北京时间 {bjt(promise['ts'])} · {promise['text'][:160]} · 24h 概率 {p24:.0%}",
            "url": f"https://x.com/thsottiaux/status/{promise['id']}",
        })
    for th in P24_THRESHOLDS:
        if p24 >= th:
            body = f"越过 {th:.0%} 阈值 · 距上次重置 {fc.get('hours_since_last_reset', 0):.0f} 小时"
            if fc.get("modal_reset_at"):
                body += f" · 峰值时点北京时间 {bjt(fc['modal_reset_at'])}"
            out.append({
                "key": f"p24:{round(th * 100)}:{fc.get('last_reset')}",  # once per threshold per reset cycle
                "kind": "probability",
                "title": f"24 小时重置概率升至 {p24:.0%}",
                "body": body,
                "url": "",
            })
    for s in (fc.get("signals") or {}).get("items", []):
        if not s.get("after_last_reset"):
            continue
        if s["kind"] in ("announce", "related") or (s.get("forward") and s["kind"] != "mention"):
            out.append({
                "key": f"signal:{s['id']}",
                "kind": "signal",
                "title": f"重置信号 · {s['label']}",
                "body": f"北京时间 {bjt(s['ts'])} · {s['text'][:160]}",
                "url": s.get("url", ""),
            })
    for section in ("feed", "corpus"):
        h = (health or {}).get(section) or {}
        if h.get("consecutive_failures", 0) >= FEED_FAILURE_STREAK:
            out.append({
                "key": f"health:{section}:{h.get('last_ok')}",
                "kind": "health",
                "title": f"数据源连续 {h['consecutive_failures']} 次抓取失败（{section}）",
                "body": f"上次成功 {bjt(h['last_ok']) if h.get('last_ok') else '无记录'} · {h.get('error') or ''}"[:200],
                "url": "",
            })
    return out


def detect(st, fc, events, health, now):
    """New alerts for this run. The first run only records what already exists."""
    seen = list(st.get("seen", []))  # insertion order, so trimming drops the oldest keys
    known = set(seen)
    found = candidates(fc, events, health, now)
    bootstrap = not st.get("bootstrapped_at")
    fresh = []
    for c in found:
        if c["key"] in known:
            continue
        known.add(c["key"])
        seen.append(c["key"])
        if bootstrap or c.pop("stale", False):
            continue
        fresh.append({**c, "created_at": now.isoformat(timespec="seconds"),
                      "status": "pending", "reason": None, "attempts": 0, "deliveries": {}})
    if bootstrap:
        st["bootstrapped_at"] = now.isoformat(timespec="seconds")
    st["seen"] = seen[-KEEP_SEEN:]
    return fresh


# ---------------------------------------------------------------- delivery

def http_post(url, payload, timeout=15):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8",
                                          "User-Agent": "ohmytibo-alert"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status >= 300:
            raise RuntimeError(f"HTTP {r.status}")


def message(alert):
    lines = [f"OH MY TIBO · {alert['title']}", alert["body"]]
    if alert.get("url"):
        lines.append(alert["url"])
    return "\n".join(x for x in lines if x)


def send(channel, alert, env, post=http_post):
    text = message(alert)
    if channel == "telegram":
        post(f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage",
             {"chat_id": env["TELEGRAM_CHAT_ID"], "text": text, "disable_web_page_preview": True})
    elif channel == "discord":
        post(env["DISCORD_WEBHOOK_URL"], {"content": text[:1900]})
    elif channel == "bark":
        payload = {"title": f"OH MY TIBO · {alert['title']}", "body": alert["body"], "group": "ohmytibo"}
        if alert.get("url"):
            payload["url"] = alert["url"]
        post(env["BARK_URL"].rstrip("/"), payload)
    elif channel == "webhook":
        post(env["ALERT_WEBHOOK_URL"], {k: alert.get(k) for k in ("key", "kind", "title", "body", "url", "created_at")})
    else:
        raise ValueError(f"unknown channel {channel}")


def deliver(st, channels, env, now, post=http_post):
    for a in st["alerts"]:
        if a["status"] not in ("pending", "partial"):
            continue
        age_h = (now - parse_ts(a["created_at"])).total_seconds() / 3600
        if age_h > TTL_HOURS or a["attempts"] >= MAX_ATTEMPTS:
            if a["status"] == "pending":
                a["status"] = "expired"
            continue
        if not channels:
            a["reason"] = "no_channel"
            continue
        a["attempts"] += 1
        for ch in channels:
            if a["deliveries"].get(ch, {}).get("ok"):
                continue
            try:
                send(ch, a, env, post)
                a["deliveries"][ch] = {"ok": True, "at": now.isoformat(timespec="seconds")}
            except Exception as exc:
                err = redact(f"{type(exc).__name__}: {exc}", env)[:160]
                a["deliveries"][ch] = {"ok": False, "at": now.isoformat(timespec="seconds"), "error": err}
        oks = [ch for ch in channels if a["deliveries"].get(ch, {}).get("ok")]
        if len(oks) == len(channels):
            a["status"], a["reason"] = "sent", None
        elif oks:
            a["status"], a["reason"] = "partial", "channel_error"
        else:
            a["status"], a["reason"] = "pending", "channel_error"


def summary(st, channels, now):
    week = now - dt.timedelta(days=7)
    recent = [a for a in st["alerts"] if parse_ts(a["created_at"]) >= week]
    sent = [a for a in st["alerts"] if a["status"] in ("sent", "partial")]
    last_sent = max(sent, key=lambda a: a["created_at"]) if sent else None
    return {
        "checked_at": now.isoformat(timespec="seconds"),
        "channels": channels,
        "configured": bool(channels),
        "pending": sum(1 for a in st["alerts"] if a["status"] in ("pending", "partial")),
        "undelivered_7d": sum(1 for a in recent if a["status"] in ("pending", "expired")),
        "last_sent": {k: last_sent[k] for k in ("title", "created_at", "status")} if last_sent else None,
        "recent": [{k: a.get(k) for k in ("title", "kind", "created_at", "status", "reason")}
                   for a in sorted(st["alerts"], key=lambda a: a["created_at"], reverse=True)[:6]],
    }


def run(fc, events, health, st, env, now, post=http_post):
    st.setdefault("alerts", [])
    fresh = detect(st, fc, events, health, now)
    st["alerts"].extend(fresh)
    channels = configured(env)
    deliver(st, channels, env, now, post)
    st["alerts"] = st["alerts"][-KEEP_ALERTS:]
    st["summary"] = summary(st, channels, now)
    return fresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    fc = state.load_json(PROC / "forecast.json", {})
    events = state.load_json(PROC / "resets.json", [])
    health = state.load_json(state.HEALTH, {})
    st = state.load_json(STATE_FILE, {})
    env = dict(os.environ)
    if args.dry_run:
        for c in candidates(fc, events, health, now):
            if c["key"] not in set(st.get("seen", [])) and not c.get("stale"):
                print("[dry-run]", message(c).replace("\n", " | "))
        return
    fresh = run(fc, events, health, st, env, now)
    state.write_json(STATE_FILE, st)
    s = st["summary"]
    via = ",".join(s["channels"]) or "none"
    for a in fresh:
        print(f"alert [{a['status']}{'/' + a['reason'] if a['reason'] else ''}] via {via}: {a['title']}")
    if not s["configured"]:
        print(f"no alert channel configured; {s['pending']} alert(s) pending, nothing recorded as sent")
    print(f"alerts: {len(fresh)} new, {s['pending']} pending, channels={via}")


if __name__ == "__main__":
    main()
