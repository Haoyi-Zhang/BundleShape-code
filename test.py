#!/usr/bin/env python3
"""Run bounded regression tests; output paths are relative to the caller's cwd."""
import argparse
import json
from pathlib import Path
import time
import unittest
import tempfile
from src.output_paths import fresh_directory, write_text_exclusive

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path)
    p.add_argument("--suite", choices=("tests", "regressions"), default="tests")
    args = p.parse_args()
    if args.out:
        fresh_directory(args.out)
        temp = args.out.resolve() / "temporary-fixtures"
        temp.mkdir()
        tempfile.tempdir = str(temp)
    start = time.perf_counter()
    here = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(here / args.suite))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {"tests_run": result.testsRun, "failures": len(result.failures),
               "errors": len(result.errors), "skipped": len(result.skipped),
               "successful": result.wasSuccessful(), "wall_seconds": round(time.perf_counter()-start,6)}
    if args.out:
        write_text_exclusive(args.out/"unit-summary.json", json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
