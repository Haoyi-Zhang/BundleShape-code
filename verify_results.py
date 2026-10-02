#!/usr/bin/env python3
"""Compare two evaluation directories while excluding run-specific telemetry."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


EXACT = [
    "variant-results.csv",
    "baseline-summary.csv",
    "variant-summary.json",
    "coupling-control.json",
    "mutation-summary.json",
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized(name: str, obj: Any) -> Any:
    obj = json.loads(json.dumps(obj))
    if name == "combination-summary.json":
        obj.pop("wall_seconds", None)
    elif name == "oracle-summary.json":
        obj.pop("wall_seconds", None)
        for suite in obj.get("suites", []):
            suite.pop("wall_seconds", None)
    elif name == "stress-summary.json":
        for key in [
            "five_run_wall_seconds", "five_run_cpu_seconds", "median_wall_seconds",
            "median_cpu_seconds", "process_peak_rss_kib", "swap_observed_kib",
        ]:
            obj.pop(key, None)
    elif name == "unit-summary.json":
        obj.pop("wall_seconds", None)
    elif name == "evaluation-summary.json":
        if "campaign" in obj:
            obj["campaign"].pop("wall_seconds", None)
            obj["campaign"].pop("cpu_seconds", None)
        if "combination_campaign" in obj:
            obj["combination_campaign"].pop("wall_seconds", None)
        if "tiny_oracle" in obj:
            obj["tiny_oracle"].pop("wall_seconds", None)
            for suite in obj["tiny_oracle"].get("suites", []):
                suite.pop("wall_seconds", None)
        if "stress" in obj:
            for key in [
                "five_run_wall_seconds", "five_run_cpu_seconds", "median_wall_seconds",
                "median_cpu_seconds", "process_peak_rss_kib", "swap_observed_kib",
            ]:
                obj["stress"].pop(key, None)
    return obj


def telemetry_valid(obj: Any) -> bool:
    """Measurements are not expected to be identical, but must be well-formed."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.endswith(("seconds", "rss_kib")):
                values = value if isinstance(value, list) else [value]
                if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
                    return False
                if key == "process_peak_rss_kib" and value > 512 * 1024:
                    return False
            elif key == "swap_observed_kib" and value not in (None, 0):
                return False
            if not telemetry_valid(value):
                return False
    elif isinstance(obj, list):
        return all(telemetry_valid(v) for v in obj)
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--actual", required=True, type=Path)
    p.add_argument("--expected", required=True, type=Path)
    args = p.parse_args()
    mismatches = []
    for name in EXACT:
        a = args.actual / name; e = args.expected / name
        if not a.exists() or not e.exists() or a.read_bytes() != e.read_bytes():
            mismatches.append(name)
    for name in ["combination-summary.json", "oracle-summary.json", "stress-summary.json", "unit-summary.json", "evaluation-summary.json"]:
        a = args.actual / name; e = args.expected / name
        if (not a.exists() or not e.exists() or not telemetry_valid(load(a))
                or normalized(name, load(a)) != normalized(name, load(e))):
            mismatches.append(name)
    result = {"matched": not mismatches, "mismatches": mismatches, "compared": len(EXACT) + 5}
    print(json.dumps(result, sort_keys=True))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
