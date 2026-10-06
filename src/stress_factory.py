"""Bounded deterministic large fixtures for resource accounting."""
from __future__ import annotations

import json
import posixpath
from pathlib import Path

from .fixture_factory import PNG_1X1
from .output_paths import fresh_directory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _rel(source: str, target: str) -> str:
    return posixpath.relpath(target, posixpath.dirname(source) or ".")


def emit_stress_bundle(
    destination: str | Path,
    *,
    pages: int = 16,
    blocks_per_page: int = 75,
    transformed: bool = False,
) -> dict[str, int]:
    root = Path(destination)
    fresh_directory(root)
    root_path = "site/home.html" if transformed else "index.html"
    css_path = "site/css/theme.css" if transformed else "styles/main.css"
    asset_path = "site/media/dot.png" if transformed else "assets/dot.png"
    page_paths = [
        (f"site/pages/p{i:02d}.html" if transformed else f"pages/page-{i:02d}.html")
        for i in range(pages)
    ]
    name = lambda prefix, i: f"z{prefix}{i}" if transformed else f"{prefix}{i}"
    root_class = name("class", 0)

    links = []
    for i, page in enumerate(page_paths):
        links.append(f'<a href="{_rel(root_path, page)}#{name("id", i * blocks_per_page)}">page {i}</a>')
    root_html = "\n".join([
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        "<title>Stress fixture</title>",
        f'<link rel="stylesheet" href="{_rel(root_path, css_path)}">',
        "</head>", f'<body class="{root_class}">', "<nav>", *links, "</nav>",
        "</body>", "</html>", "",
    ])
    _write(root / root_path, root_html)

    total_blocks = pages * blocks_per_page
    for pidx, page in enumerate(page_paths):
        parts = [
            "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
            f"<title>Page {pidx}</title>",
            f'<link href="{_rel(page, css_path)}" rel="stylesheet">',
            "</head>", f'<body class="{root_class}">',
        ]
        for j in range(blocks_per_page):
            k = pidx * blocks_per_page + j
            attrs = [("id", name("id", k)), ("class", name("class", k + 1))]
            if transformed:
                attrs.reverse()
            rendered = " ".join(f'{a}="{b}"' for a, b in attrs)
            parts.extend([
                f"<section {rendered}>",
                f"<p>bounded block {k}</p>",
                "</section>",
            ])
        parts.extend(["</body>", "</html>", ""])
        _write(root / page, "\n".join(parts))

    rules = []
    order = list(range(total_blocks))
    for k in order:
        declarations = [
            ("color", f"#{(k % 8) + 1}{(k % 8) + 1}{(k % 8) + 1}"),
            ("margin-top", f"{k % 7}px"),
            ("padding-left", f"{k % 5}px"),
        ]
        if k == 0:
            declarations.append(("background-image", f'url("{_rel(css_path, asset_path)}")'))
        if transformed:
            declarations.reverse()
        body = ";".join(f"{p}:{v}" for p, v in declarations) + ";"
        rules.append(f".{name('class', k + 1)}{{{body}}}")
    _write(root / css_path, "\n".join(rules) + "\n")
    asset = root / asset_path
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(PNG_1X1)

    resources = [root_path, css_path, asset_path, *page_paths]
    if transformed:
        resources = list(reversed(resources))
    manifest = {"format": "iwb-1", "root": root_path, "resources": resources}
    _write(root / "bundle.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {
        "content_pages": pages,
        "root_html_pages": 1,
        "html_resources": pages + 1,
        "blocks": total_blocks,
        "ids": total_blocks,
        "classes": total_blocks + 1,
        "css_rules": total_blocks,
        "css_declarations": total_blocks * 3 + 1,
        "resources": pages + 3,
    }
