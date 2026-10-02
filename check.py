#!/usr/bin/env python3
"""Replay and validate an inert-web-bundle certificate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src import limits
from src.checker_core import verify_certificate


def load_json(path: Path) -> Any:
    with path.open("rb") as handle:
        raw = handle.read(limits.MAX_CERT_BYTES + 1)
    if len(raw) > limits.MAX_CERT_BYTES:
        raise ValueError("certificate exceeds byte cap")
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate JSON key {key!r}")
            out[key] = value
        return out
    return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("left", type=Path)
    p.add_argument("right", type=Path)
    p.add_argument("certificate", type=Path)
    args = p.parse_args()
    try:
        cert = load_json(args.certificate)
        verdict = verify_certificate(args.left, args.right, cert)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        verdict = {"accepted": False, "reason": f"certificate-input:{exc}"}
    print(json.dumps(verdict, sort_keys=True))
    return 3 if verdict.get("status") == "environment-error" else (0 if verdict.get("accepted") else 2)


if __name__ == "__main__":
    raise SystemExit(main())
