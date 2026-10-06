#!/usr/bin/env python3
"""Sequential clean reproduction of the ten retained outputs; no network."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from src.output_paths import fresh_directory, write_text_exclusive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("reproduced"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = args.out.resolve()
    if any(out == protected or protected in out.parents
           for protected in (root / "results", root / "evidence")):
        parser.error("choose a fresh output directory, not the retained results")
    fresh_directory(out)
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    cap = 512 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    commands = [
        ["generate_fixtures.py", "--out", str(out / "generated-fixtures")],
        ["test.py", "--out", str(out / "unit")],
        ["evaluate.py", "--out", str(out / "evaluation"), "--work", str(out / "campaign")],
        ["static_assurance.py", "--out", str(out / "static")],
        ["repair_acceptance.py", "--out", str(out / "repairs")],
        ["test.py", "--suite", "regressions", "--out", str(out / "supplemental")],
        ["verify_results.py", "--actual", str(out / "evaluation"), "--expected", str(root/"results"),
         "--expected-unit", str(root / "evidence" / "current-unit-summary.json")],
    ]
    receipts = []
    for index, command in enumerate(commands):
        if command[0] == "verify_results.py":
            # Copy the actual unit receipt without modifying any field.
            with (out / "evaluation" / "unit-summary.json").open("xb") as handle:
                handle.write((out / "unit" / "unit-summary.json").read_bytes())
        print("RUN", command[0], flush=True)
        started = time.perf_counter()
        argv = [sys.executable, "-B", str(root / command[0]), *command[1:]]
        try:
            with (out / f"{index:02d}-{Path(command[0]).stem}.log").open("xb") as log:
                completed = subprocess.run(argv, env=env, cwd=root, stdout=log,
                                           stderr=subprocess.STDOUT, timeout=120)
            status, timed_out = completed.returncode, False
        except subprocess.TimeoutExpired:
            status, timed_out = None, True
        receipts.append({"argv": argv, "exit_code": status, "timed_out": timed_out,
                         "wall_seconds": time.perf_counter() - started})
        print("EXIT", status, "TIMEOUT", timed_out, flush=True)
        if status != 0:
            write_text_exclusive(out / "commands.json", json.dumps(receipts, indent=2) + "\n")
            return 1
    write_text_exclusive(out / "commands.json", json.dumps(receipts, indent=2) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
