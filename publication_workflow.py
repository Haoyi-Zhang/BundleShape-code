#!/usr/bin/env python3
"""Reproducible owned release-review example using only the public CLI.

No browser, external site, network fetch, content rewrite, or deployment occurs.
Expected outcomes describe eleven authored controls, not population accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from src.output_paths import fresh_directory, write_text_exclusive

HERE = Path(__file__).resolve().parent
CONTROLS = (
    ("anchored-multiclass-rename", "equivalent", None),
    ("ordinary-unquoted-attributes", "equivalent", None),
    ("changed-publication-text", "different", None),
    ("changed-css-longhand", "different", None),
    ("document-local-id-reuse", "out-of-language", "duplicate-id"),
    ("simultaneously-new-classes", "out-of-language", "unanchored-class-set"),
    ("stray-start-tag-slash", "out-of-language", "bad-start-tag"),
    ("end-tag-attribute", "out-of-language", "bad-end-tag"),
    ("css-shorthand", "out-of-language", "unsupported-property"),
    ("css-adjacent-type-selector", "out-of-language", "unsupported-selector"),
    ("absent-endpoint", "environment-error", None),
)
ROUTES = {"equivalent": "same-structure", "different": "review-structural-change",
          "out-of-language": "unsupported-input", "environment-error": "retry-environment"}


def document(body: str, css: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>Reading notes</title>'
            f'<link rel="stylesheet" href="{css}"></head><body class="page">'
            + body + '</body></html>')


def emit(root: Path, control: str) -> None:
    fresh_directory(root)
    files = {
        "index.html": document('<section id="intro" class="page panel"><p title="Notes">'
                               'Reading notes</p><a href="child.html#details">Details</a></section>', 'style.css'),
        "child.html": document('<p id="details" class="panel">Details</p>', 'style.css'),
        "style.css": '.page > .panel, #intro{color:#234;row-gap:1px;column-gap:2px}',
    }
    if control == "anchored-multiclass-rename":
        # A single global renaming, with anchored class-set permutations.
        files = {name: text.replace('class="page panel"', 'class="panel page"')
                 for name, text in files.items()}
        for old, new in (("index.html", "home.html"), ("child.html", "notes.html"),
                         ("style.css", "theme.css"), ("intro", "opening"),
                         ("details", "entry"), ("panel", "card"), ("page", "layout")):
            files = {name.replace(old, new): text.replace(old, new) for name, text in files.items()}
    elif control == "ordinary-unquoted-attributes":
        files["index.html"] = files["index.html"].replace('lang="en"', 'lang=en').replace('title="Notes"', 'title=Notes')
    elif control == "changed-publication-text":
        files["index.html"] = files["index.html"].replace('Reading notes</p>', 'Revised notes</p>')
    elif control == "changed-css-longhand":
        files["style.css"] = files["style.css"].replace('color:#234', 'color:#345')
    elif control == "document-local-id-reuse":
        # Unique in each document but not in the IWB bundle; still unsupported.
        files["child.html"] = files["child.html"].replace('id="details"', 'id="intro"')
        files["index.html"] = files["index.html"].replace('child.html#details', 'child.html#intro')
    elif control == "simultaneously-new-classes":
        files["index.html"] = files["index.html"].replace('class="page"', 'class="page panel"', 1)
    elif control == "stray-start-tag-slash":
        files["index.html"] = files["index.html"].replace('<p title="Notes">', '<p / title="Notes">')
    elif control == "end-tag-attribute":
        files["index.html"] = files["index.html"].replace('</p>', '</p title="Notes">', 1)
    elif control == "css-shorthand":
        files["style.css"] = files["style.css"].replace('row-gap:1px;column-gap:2px', 'gap:1px')
    elif control == "css-adjacent-type-selector":
        files["style.css"] = files["style.css"].replace('.page > .panel, #intro', 'div*')
    elif control != "base":
        raise ValueError(control)
    for name, text in files.items():
        write_text_exclusive(root / name, text)
    write_text_exclusive(root / "bundle.json", json.dumps({
        "format": "iwb-1", "root": "home.html" if control == "anchored-multiclass-rename" else "index.html",
        "resources": list(files)}, sort_keys=True) + "\n")


def run_cli(script: str, *arguments: Path) -> dict:
    command = [sys.executable, "-B", str(HERE / script), *(str(p.resolve()) for p in arguments)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                               timeout=20, cwd=HERE,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return {"command": command, "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr}


def inventory(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True, help="fresh owned input/receipt directory")
    parser.add_argument("--out", type=Path, required=True, help="fresh compact evidence directory")
    args = parser.parse_args()
    work, out = args.work.resolve(), args.out.resolve()
    if work == out or work in out.parents or out in work.parents:
        parser.error("work and output must be disjoint")
    fresh_directory(work)
    fresh_directory(out)
    emit(work / "base", "base")
    records = []
    for name, expected, code in CONTROLS:
        left, right = work / "base", work / name
        if expected != "environment-error":
            emit(right, name)
        proposal = run_cli("certify.py", left, right)
        cert, verdict, replay = None, None, None
        if proposal["returncode"] == 0:
            cert = json.loads(proposal["stdout"])
            cert_path = work / (name + ".json")
            write_text_exclusive(cert_path, proposal["stdout"])
            replay = run_cli("check.py", left, right, cert_path)
            verdict = json.loads(replay["stdout"])
            observed = cert["decision"] if replay["returncode"] == 0 and verdict["accepted"] else "unaccepted"
        else:
            observed = ("environment-error" if proposal["returncode"] == 3
                        and proposal["stderr"].startswith("environment-error:")
                        and not proposal["stdout"] else "unaccepted")
        matched = observed == expected and (code is None or cert["witness"]["code"] == code)
        records.append({"name": name, "expected": expected, "expected_code": code,
                        "observed": observed, "route": ROUTES.get(observed, "stop-unaccepted"),
                        "matched": matched, "certificate": cert, "verdict": verdict,
                        "proposal": proposal, "replay": replay,
                        "input_sha256": {"left": inventory(left), "right": inventory(right)}})
    summary = {"format": "iwb-publication-workflow-1", "controls": len(records),
               "matched": sum(r["matched"] for r in records),
               "observed_counts": dict(sorted(Counter(r["observed"] for r in records).items())),
               "route_counts": dict(sorted(Counter(r["route"] for r in records).items())),
               "accepted_certificates": sum(r["verdict"] is not None and r["verdict"]["accepted"] for r in records),
               "scope": "eleven owned controls; no browser validation, natural-site coverage or timing estimate"}
    sources = ("publication_workflow.py", "certify.py", "check.py", "src/__init__.py",
               "src/producer_core.py", "src/checker_core.py", "src/limits.py", "src/output_paths.py")
    bindings = {"format": "iwb-workflow-bindings-1",
                "source_sha256": {f: sha256((HERE / f).read_bytes()).hexdigest() for f in sources},
                "environment": {"python": sys.version, "executable": sys.executable,
                                "platform": platform.platform(), "PYTHONDONTWRITEBYTECODE": "1"},
                "command": [sys.executable, "-B", str(Path(__file__).resolve()),
                            "--work", str(work), "--out", str(out)]}
    for name, value in (("controls.json", records), ("summary.json", summary), ("bindings.json", bindings)):
        write_text_exclusive(out / name, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if all(r["matched"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
