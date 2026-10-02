"""Deterministic tiny bundles for exhaustive orbit checking."""
from __future__ import annotations

import json
import posixpath
import shutil
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _rel(source: str, target: str, fragment: str | None = None) -> str:
    value = posixpath.relpath(target, posixpath.dirname(source) or ".")
    return value + (("#" + fragment) if fragment else "")


def emit_tiny_bundle(destination: str | Path, family: int, variant: int) -> None:
    """Emit one member of an eight-way alpha/path/ordering orbit."""
    root = Path(destination)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    path_sets = [
        ("index.html", "detail.html"),
        ("home.html", "pages/info.html"),
        ("site/start.html", "site/doc.html"),
        ("entry.html", "docs/detail.html"),
    ]
    root_path, detail_path = path_sets[variant % len(path_sets)]
    ids = ("root-id", "detail-id") if variant < 4 else (f"u{family}", f"v{family}")
    classes = ("page", "panel") if variant % 2 == 0 else (f"c{family}", f"d{family}")
    reverse_attrs = bool(variant & 1)
    reverse_classes = bool(variant & 2)
    compact = bool(variant & 4)
    root_tag = ["main", "article", "section", "div"][family % 4]
    child_tag = ["p", "span", "small", "strong"][family % 4]

    def attrs(items: list[tuple[str, str]]) -> str:
        if reverse_attrs:
            items = list(reversed(items))
        return " ".join(f'{k}="{v}"' for k, v in items)

    class_value = " ".join(reversed(classes) if reverse_classes else classes)
    href = _rel(root_path, detail_path, ids[1])
    root_parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Tiny {family}</title>",
        "</head>",
        f'<body class="{classes[0]}">',
        f'<{root_tag} {attrs([("id", ids[0]), ("class", class_value)])}>',
        f"<{child_tag}>family-{family}</{child_tag}>",
        f'<a {attrs([("href", href), ("title", "details")])}>open</a>',
        f"</{root_tag}>",
        "</body>",
        "</html>",
    ]
    detail_parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Detail {family}</title>",
        "</head>",
        f'<body class="{classes[0]}">',
        f'<section {attrs([("id", ids[1]), ("class", classes[1])])}>',
        f"<p>detail-{family}</p>",
        "</section>",
        "</body>",
        "</html>",
    ]
    if variant == 7:
        root_parts.insert(4, "<!-- ignored tiny comment -->")
    sep = "" if compact else "\n"
    _write(root / root_path, sep.join(root_parts) + ("" if compact else "\n"))
    _write(root / detail_path, sep.join(detail_parts) + ("" if compact else "\n"))
    listed = [root_path, detail_path]
    if reverse_attrs:
        listed.reverse()
    manifest = {"format": "iwb-1", "root": root_path, "resources": listed}
    _write(root / "bundle.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def emit_tiny_suite(destination: str | Path, families: int = 8, variants: int = 8) -> list[dict[str, object]]:
    root = Path(destination)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    records: list[dict[str, object]] = []
    for family in range(families):
        for variant in range(variants):
            path = root / f"family-{family:02d}" / f"variant-{variant:02d}"
            emit_tiny_bundle(path, family, variant)
            records.append({"family": family, "variant": variant, "path": str(path)})
    return records

# A second tiny family exercises CSS selector/declaration normalization, local
# URL rewriting, an image asset, and four-way resource bijections.
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c020000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082"
)


def emit_tiny_css_bundle(destination: str | Path, family: int, variant: int) -> None:
    root = Path(destination)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    path_sets = [
        ("index.html", "detail.html", "base.css", "dot.png"),
        ("home.html", "docs/info.html", "css/theme.css", "media/pixel.png"),
        ("site/start.html", "site/more.html", "site/core.css", "site/mark.png"),
        ("entry.html", "page.html", "presentation.css", "asset.png"),
    ]
    root_path, detail_path, css_path, asset_path = path_sets[variant % 4]
    ids = ("title", "detail") if variant < 4 else (f"a{family}", f"b{family}")
    classes = ("page", "panel") if variant % 2 == 0 else (f"x{family}", f"y{family}")
    reverse = bool(variant & 1)
    reverse_classes = bool(variant & 2)
    compact = bool(variant & 4)

    def attrs(items: list[tuple[str, str]]) -> str:
        if reverse:
            items = list(reversed(items))
        return " ".join(f'{k}="{v}"' for k, v in items)

    root_classes = " ".join(reversed(classes) if reverse_classes else classes)
    css_href = _rel(root_path, css_path)
    detail_href = _rel(root_path, detail_path, ids[1])
    asset_src = _rel(root_path, asset_path)
    root_parts = [
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        f"<title>CSS tiny {family}</title>",
        f'<link {attrs([("rel", "stylesheet"), ("href", css_href)])}>',
        "</head>", f'<body class="{classes[0]}">',
        f'<main {attrs([("id", ids[0]), ("class", root_classes)])}>',
        f"<p>css-family-{family}</p>",
        f'<a href="{detail_href}">detail</a>',
        f'<img {attrs([("src", asset_src), ("alt", "local marker")])}>',
        "</main>", "</body>", "</html>",
    ]
    detail_parts = [
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        f"<title>Detail {family}</title>",
        f'<link rel="stylesheet" href="{_rel(detail_path, css_path)}">',
        "</head>", f'<body class="{classes[0]}">',
        f'<section id="{ids[1]}" class="{classes[1]}"><p>detail-css-{family}</p></section>',
        "</body>", "</html>",
    ]
    selectors = [f"#{ids[0]}", f".{classes[1]}"]
    declarations = [
        ("color", ["#123", "#234", "#345", "#456"][family % 4]),
        ("background-image", f'url("{_rel(css_path, asset_path)}")'),
        ("padding-left", f"{family + 1}px"),
    ]
    second = [("margin-top", "2px"), ("line-height", "1.4")]
    if reverse:
        selectors.reverse(); declarations.reverse(); second.reverse()
    css_parts = [
        ", ".join(selectors) + "{" + ";".join(f"{k}:{v}" for k, v in declarations) + ";}",
        f".{classes[0]}" + "{" + ";".join(f"{k}:{v}" for k, v in second) + ";}",
    ]
    sep = "" if compact else "\n"
    _write(root / root_path, sep.join(root_parts) + ("" if compact else "\n"))
    _write(root / detail_path, sep.join(detail_parts) + ("" if compact else "\n"))
    _write(root / css_path, sep.join(css_parts) + ("" if compact else "\n"))
    asset = root / asset_path; asset.parent.mkdir(parents=True, exist_ok=True); asset.write_bytes(_TINY_PNG)
    listed = [root_path, detail_path, css_path, asset_path]
    if reverse:
        listed.reverse()
    _write(root / "bundle.json", json.dumps({"format": "iwb-1", "root": root_path, "resources": listed}, indent=2, sort_keys=True) + "\n")


def emit_tiny_css_suite(destination: str | Path, families: int = 4, variants: int = 8) -> list[dict[str, object]]:
    root = Path(destination)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    records: list[dict[str, object]] = []
    for family in range(families):
        for variant in range(variants):
            path = root / f"family-{family:02d}" / f"variant-{variant:02d}"
            emit_tiny_css_bundle(path, family, variant)
            records.append({"family": family, "variant": variant, "path": str(path)})
    return records
