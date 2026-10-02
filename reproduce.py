#!/usr/bin/env python3
"""Sequential clean reproduction of the ten retained outputs; no network."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import resource
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("reproduced"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = args.out.resolve()
    if any(out == protected or protected in out.parents
           for protected in (root / "results", root / "evidence")):
        parser.error("choose a fresh output directory, not the retained results")
    out.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    cap = 512 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    commands = [
        ["generate_fixtures.py"], ["test.py", "--out", str(out)],
        ["evaluate.py", "--out", str(out)], ["static_assurance.py", "--out", str(out)],
        ["repair_acceptance.py", "--out", str(out)],
        ["verify_results.py", "--actual", str(out), "--expected", str(root/"results")],
    ]
    for command in commands:
        print("RUN", command[0], flush=True)
        try:
            subprocess.run([sys.executable, str(root/command[0]), *command[1:]],
                           env=env, check=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print(f"reproduction failed: {exc}", file=sys.stderr)
            return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
