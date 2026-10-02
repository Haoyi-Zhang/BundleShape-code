#!/usr/bin/env python3
"""Print the canonical form of one admitted bundle for inspection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.producer_core import AdmissionError, EnvironmentFailure, canonical_digest, parse_bundle


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("bundle", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    try:
        parsed = parse_bundle(args.bundle)
        obj = {"digest": canonical_digest(parsed), "canonical": parsed.canonical_obj}
        code = 0
    except (EnvironmentFailure, OSError) as exc:
        obj = {"admitted": None, "status": "environment-error", "reason": str(exc)}
        code = 3
    except AdmissionError as exc:
        obj = {"admitted": False, "error": exc.as_dict()}
        code = 2
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
