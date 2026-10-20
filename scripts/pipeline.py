#!/usr/bin/env python3
"""Run the whole ohmytibo pipeline: fetch -> parse -> analyze -> render."""
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
STEPS = ["fetch_corpus.py", "parse_corpus.py", "fetch_reset_log.py", "analyze.py", "build_site.py"]


def main():
    days = sys.argv[1] if len(sys.argv) > 1 else "60"
    for i, step in enumerate(STEPS):
        args = [sys.executable, str(HERE / step)]
        if step == "fetch_corpus.py":
            args += ["--days", days]
        print(f"\n=== {step} ===", flush=True)
        proc = subprocess.run(args, cwd=HERE.parent)
        if proc.returncode != 0:
            if step == "fetch_corpus.py":
                print("corpus fetch failed; continuing with cached pages")
                continue
            raise SystemExit(f"{step} failed with code {proc.returncode}")


if __name__ == "__main__":
    main()
