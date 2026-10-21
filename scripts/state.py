"""Monitoring state under data/state/: per-source health and the pipeline run log.

Everything here is committed to a public repo, so nothing secret may be written.
"""
import datetime as dt
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state"
HEALTH = STATE / "health.json"
RUNS = STATE / "runs.jsonl"
UTC = dt.timezone.utc


def now_iso():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


def load_json(path, default):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def update_health(section, status, path=HEALTH):
    """Store one source's latest status, carrying the failure streak and last success forward."""
    health = load_json(path, {})
    prev = health.get(section, {})
    ok = bool(status.get("ok"))
    health[section] = {
        **status,
        "ok": ok,
        "consecutive_failures": 0 if ok else prev.get("consecutive_failures", 0) + 1,
        "last_ok": status.get("at") if ok else prev.get("last_ok"),
    }
    write_json(path, health)
    return health[section]


def append_run(entry, path=RUNS, keep=500):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines.append(json.dumps(entry, ensure_ascii=False))
    path.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")


def recent_runs(path=RUNS, n=12):
    path = pathlib.Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows
