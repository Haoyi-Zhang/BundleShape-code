#!/usr/bin/env python3
"""Produce a bounded inert-web-bundle certificate without rendering content."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.producer_core import EnvironmentFailure, make_certificate
from src.checker_core import verify_certificate
from src import limits
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("left", type=Path)
    p.add_argument("right", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    try:
        cert = make_certificate(args.left, args.right)
        verdict = verify_certificate(args.left, args.right, cert)
    except (EnvironmentFailure, OSError) as exc:
        print(f"environment-error: {exc}", file=sys.stderr)
        return 3
    if not verdict.get("accepted"):
        print(json.dumps(verdict, sort_keys=True), file=sys.stderr)
        return 3 if verdict.get("status") == "environment-error" else 2
    text = json.dumps(cert, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(text.encode("utf-8")) > limits.MAX_CERT_BYTES:
        print("certificate-too-large", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except FileExistsError as exc:
            raise SystemExit(f"refusing to overwrite existing output: {args.output}") from exc
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
