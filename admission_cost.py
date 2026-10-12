#!/usr/bin/env python3
"""Closing-token admission comparison on the 24 supplied generated bases only."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from html.parser import HTMLParser
import json
from pathlib import Path
import platform
import statistics
import time
from unittest.mock import patch

from src import producer_core, checker_core
from src.output_paths import write_text_exclusive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    paths = sorted((root / "fixtures/owned").glob("fixture-*"))
    if len(paths) != 24 or not all((p / "bundle.json").is_file() for p in paths):
        parser.error("the comparison requires the 24 supplied generated bases")
    if args.output.exists():
        parser.error("choose a fresh result path")
    expected = [producer_core.parse_bundle(p).canonical_bytes for p in paths]
    samples = {key: {"wall_seconds": [], "cpu_seconds": []} for key in
               ("strict_closing_tokens", "standard_library_closing_tokens")}
    agreement = 0
    for repeat in range(5):
        modes = list(samples) if repeat % 2 == 0 else list(reversed(samples))
        for mode in modes:
            wall, cpu = time.perf_counter(), time.process_time()
            actual = []
            for core in (producer_core, checker_core):
                # Only this ordinary admitted-data comparison restores the
                # library tokenizer; production and checker APIs stay strict.
                context = (patch.object(core._HTMLCollector, "parse_endtag", HTMLParser.parse_endtag)
                           if mode == "standard_library_closing_tokens" else nullcontext())
                with context:
                    actual.append([core.parse_bundle(p).canonical_bytes for p in paths])
            samples[mode]["wall_seconds"].append(time.perf_counter() - wall)
            samples[mode]["cpu_seconds"].append(time.process_time() - cpu)
            if any(values != expected for values in actual):
                raise RuntimeError("closing-token modes changed admitted canonical records")
            agreement += sum(len(values) for values in actual)
    for values in samples.values():
        values["median_wall_seconds"] = statistics.median(values["wall_seconds"])
        values["median_cpu_seconds"] = statistics.median(values["cpu_seconds"])
    files = [f for p in paths for f in p.rglob("*") if f.is_file()]
    result = {
        "input_kind": "24 supplied generated owned bases; no natural-source inputs",
        "bundles": len(paths), "html_files": sum(f.suffix == ".html" for f in files),
        "resources": len(files) - len(paths),
        "input_bytes_including_manifests": sum(f.stat().st_size for f in files),
        "admitted_by_each_core": 24, "repeats_per_mode": 5, "cores_per_repeat": 2,
        "canonical_agreements": agreement, "samples": samples,
        "operation": "full parse_bundle admission and canonical construction for each base and each core",
        "comparison": "only the closing-token method is switched to HTMLParser.parse_endtag; no old full-parser claim",
        "order": "alternating mode order; same process; warm local filesystem; no CPU affinity",
        "python": platform.python_version(), "platform": platform.system(),
        "scope": "no browser, natural coverage, scaling, peak memory or comparative detector effectiveness inference",
    }
    write_text_exclusive(args.output, json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
