#!/usr/bin/env python3
"""Run the whole ohmytibo pipeline: fetch -> parse -> analyze -> alert -> render.

Every run is appended to data/state/runs.jsonl. A failed step stops the steps that
depend on it, the alert step still runs on whatever data exists, and the process
exits non-zero so the scheduled job shows red.
"""
import subprocess
import sys
import pathlib
import time

import state

HERE = pathlib.Path(__file__).resolve().parent
# (script, steps it needs to have succeeded)
STEPS = [
    ("fetch_corpus.py", ()),
    ("parse_corpus.py", ()),  # a failed fetch still leaves the stored corpus to parse
    ("fetch_reset_log.py", ()),
    ("analyze.py", ("parse_corpus.py", "fetch_reset_log.py")),
    ("alert.py", ()),
    ("build_site.py", ("analyze.py",)),
]
OPTIONAL = {"fetch_corpus.py", "alert.py"}  # failures are recorded but do not fail the run


def main():
    days = sys.argv[1] if len(sys.argv) > 1 else "60"
    started = time.monotonic()
    at = state.now_iso()
    results = {}
    log = []
    for step, needs in STEPS:
        if any(results.get(n) is False for n in needs):
            results[step] = None
            log.append({"step": step, "ok": None, "skipped": True})
            print(f"\n=== {step} === skipped (depends on a failed step)", flush=True)
            continue
        args = [sys.executable, str(HERE / step)]
        if step == "fetch_corpus.py":
            args += ["--days", days]
        if step == "build_site.py":
            # the page shows this run's status, so record it before rendering
            record(at, started, log, provisional=True)
        print(f"\n=== {step} ===", flush=True)
        t0 = time.monotonic()
        proc = subprocess.run(args, cwd=HERE.parent)
        ok = proc.returncode == 0
        results[step] = ok
        log.append({"step": step, "ok": ok, "code": proc.returncode, "seconds": round(time.monotonic() - t0, 1)})
        if not ok:
            print(f"{step} failed with code {proc.returncode}", flush=True)
    failed = record(at, started, log)
    if failed:
        raise SystemExit(f"failed: {', '.join(failed)}")


def record(at, started, log, provisional=False):
    failed = [r["step"] for r in log if r["ok"] is False and r["step"] not in OPTIONAL]
    entry = {"at": at, "seconds": round(time.monotonic() - started, 1), "ok": not failed,
             "failed": failed, "warnings": [r["step"] for r in log if r["ok"] is False and r["step"] in OPTIONAL],
             "steps": log}
    if provisional:
        entry["provisional"] = True
    runs = state.recent_runs(n=1)
    if runs and runs[-1].get("at") == at and runs[-1].get("provisional"):
        # replace this run's provisional entry with the final one
        lines = state.RUNS.read_text(encoding="utf-8").splitlines()[:-1]
        state.RUNS.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    state.append_run(entry)
    state.update_health("pipeline", {"at": at, "ok": not failed, "failed": failed})
    return failed


if __name__ == "__main__":
    main()
