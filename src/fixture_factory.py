"""Owned benign fixture generation and deterministic metamorphic variants."""
from __future__ import annotations

import base64
import json
import posixpath
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from .output_paths import fresh_directory

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

THEMES = [
    ("Community Garden", "Seasonal planting notes", "Seed exchange"),
    ("Local Museum", "Gallery guide", "Open archive"),
    ("Course Handbook", "Weekly reading plan", "Office hours"),
    ("Public Library", "Neighborhood collections", "Reading room"),
    ("Science Club", "Experiment calendar", "Observation log"),
    ("Walking Trail", "Route information", "Habitat notes"),
]

PALETTES = [
    ("#234", "#eef", "#567"),
    ("#243", "#efe", "#586"),
    ("#342", "#ffe", "#875"),
    ("#324", "#fef", "#756"),
]

BASE_PATHS = {
    "root": "index.html",
    "detail": "pages/details.html",
    "css": "styles/base.css",
    "asset": "assets/dot.png",
}

PATH_SETS = [
    BASE_PATHS,
    {"root": "home.html", "detail": "docs/info.html", "css": "css/layout.css", "asset": "media/pixel.png"},
    {"root": "site/home.html", "detail": "site/more/detail.html", "css": "site/theme/core.css", "asset": "site/media/mark.png"},
    {"root": "entry.html", "detail": "detail.html", "css": "presentation.css", "asset": "mark.png"},
]

BASE_IDS = {"title": "title", "card": "card", "details": "details"}
BASE_CLASSES = {
    "page": "page", "header": "header", "heading": "heading", "card": "card",
    "accent": "accent", "link": "link", "image": "image", "detail": "detail",
    "note": "note",
}


@dataclass(frozen=True)
class Variant:
    name: str
    kind: str  # legal, different, rejected
    options: dict[str, Any]


LEGAL_VARIANTS = [
    Variant("path-rename", "legal", {"path_set": 1}),
    Variant("path-move", "legal", {"path_set": 2}),
    Variant("id-alpha", "legal", {"rename_ids": True}),
    Variant("class-alpha", "legal", {"rename_classes": True}),
    Variant("attribute-order", "legal", {"reverse_attrs": True}),
    Variant("class-token-order", "legal", {"reverse_classes": True}),
    Variant("declaration-order", "legal", {"reverse_decls": True}),
    Variant("selector-list-order", "legal", {"reverse_selectors": True}),
    Variant("format-and-comments", "legal", {"compact": True, "comments": True}),
    Variant("paths-and-names", "legal", {"path_set": 3, "rename_ids": True, "rename_classes": True}),
    Variant("all-orderings", "legal", {"reverse_attrs": True, "reverse_classes": True, "reverse_decls": True, "reverse_selectors": True, "comments": True}),
    Variant("combined-all", "legal", {"path_set": 2, "rename_ids": True, "rename_classes": True, "reverse_attrs": True, "reverse_classes": True, "reverse_decls": True, "reverse_selectors": True, "compact": True, "comments": True}),
]

INVALID_VARIANTS = [
    Variant("changed-text", "different", {"changed_text": True}),
    Variant("ordered-sibling-swap", "different", {"swap_siblings": True}),
    Variant("changed-css-value", "different", {"changed_css": True}),
    Variant("changed-selector", "different", {"changed_selector": True}),
    Variant("changed-asset", "different", {"changed_asset": True}),
    Variant("duplicate-id", "rejected", {"duplicate_id": True}),
    Variant("forbidden-form", "rejected", {"forbidden_form": True}),
    Variant("broken-reference", "rejected", {"broken_ref": True}),
]


def _rel(source: str, target: str, fragment: str | None = None) -> str:
    value = posixpath.relpath(target, posixpath.dirname(source) or ".")
    if fragment:
        value += "#" + fragment
    return value


def _attrs(items: list[tuple[str, str]], reverse: bool) -> str:
    if reverse:
        items = list(reversed(items))
    return " ".join(f'{k}="{v}"' for k, v in items)


def _classes(names: list[str], reverse: bool) -> str:
    return " ".join(reversed(names) if reverse else names)


def _renamed_ids(index: int, enabled: bool) -> dict[str, str]:
    if not enabled:
        return dict(BASE_IDS)
    return {key: f"id{index}_{i}" for i, key in enumerate(BASE_IDS)}


def _renamed_classes(index: int, enabled: bool) -> dict[str, str]:
    if not enabled:
        return dict(BASE_CLASSES)
    return {key: f"cl{index}_{i}" for i, key in enumerate(BASE_CLASSES)}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def emit_bundle(destination: str | Path, index: int, options: dict[str, Any] | None = None) -> None:
    """Emit one entirely owned, noninteractive, local-only bundle."""
    options = dict(options or {})
    dest = Path(destination)
    fresh_directory(dest)
    paths = dict(PATH_SETS[int(options.get("path_set", 0))])
    ids = _renamed_ids(index, bool(options.get("rename_ids")))
    classes = _renamed_classes(index, bool(options.get("rename_classes")))
    title, subtitle, detail_label = THEMES[index % len(THEMES)]
    fg, bg, accent_color = PALETTES[index % len(PALETTES)]
    reverse_attrs = bool(options.get("reverse_attrs"))
    reverse_classes = bool(options.get("reverse_classes"))
    compact = bool(options.get("compact"))

    css_href = _rel(paths["root"], paths["css"])
    detail_href = _rel(paths["root"], paths["detail"], ids["details"])
    asset_src = _rel(paths["root"], paths["asset"])
    css_href_detail = _rel(paths["detail"], paths["css"])

    link_attrs = _attrs([("rel", "stylesheet"), ("href", css_href)], reverse_attrs)
    body_class = _classes([classes["page"]], reverse_classes)
    header_class = _classes([classes["page"], classes["header"]], reverse_classes)
    accent_class = _classes([classes["card"], classes["accent"]], reverse_classes)
    image_attrs = _attrs([
        ("class", classes["image"]), ("src", asset_src), ("alt", "Decorative local marker"),
        ("width", "1"), ("height", "1"),
    ], reverse_attrs)
    title_attrs = _attrs([("id", ids["title"]), ("class", classes["heading"])], reverse_attrs)
    card_attrs = _attrs([("id", ids["card"]), ("class", classes["card"])], reverse_attrs)
    detail_link_attrs = _attrs([("class", classes["link"]), ("href", detail_href)], reverse_attrs)

    p1 = f"<p class=\"{accent_class}\">{subtitle}{' revised' if options.get('changed_text') else ''}</p>"
    p2 = f"<p>Fixture {index:02d} is an owned, inert publication sample.</p>"
    sibling_block = p2 + p1 if options.get("swap_siblings") else p1 + p2
    bad_form = '<form><input name="field"></form>' if options.get("forbidden_form") else ""
    if options.get("broken_ref"):
        image_attrs = image_attrs.replace(asset_src, "missing/not-present.png")

    root_parts = [
        "<!doctype html>", "<html lang=\"en\">", "<head>", "<meta charset=\"utf-8\">",
        f"<title>{title}</title>", f"<link {link_attrs}>", "</head>",
        f"<body class=\"{body_class}\">", f"<header class=\"{header_class}\">",
        f"<h1 {title_attrs}>{title}</h1>", "</header>", f"<main {card_attrs}>",
        sibling_block, f"<a {detail_link_attrs}>{detail_label}</a>", f"<img {image_attrs}>",
        bad_form, "</main>", "</body>", "</html>",
    ]
    if options.get("comments"):
        root_parts.insert(3, "<!-- inert formatting comment -->")
    root_html = "".join(root_parts) if compact else "\n".join(root_parts) + "\n"

    detail_id = ids["card"] if options.get("duplicate_id") else ids["details"]
    detail_parts = [
        "<!doctype html>", "<html lang=\"en\">", "<head>", "<meta charset=\"utf-8\">",
        f"<title>{detail_label}</title>", f"<link {_attrs([('rel','stylesheet'),('href',css_href_detail)], reverse_attrs)}>",
        "</head>", f"<body class=\"{classes['page']}\">",
        f"<article id=\"{detail_id}\" class=\"{classes['detail']}\">",
        f"<h2 class=\"{classes['heading']}\">{detail_label}</h2>",
        f"<p class=\"{classes['note']}\">Static explanatory text for fixture {index:02d}.</p>",
        "</article>", "</body>", "</html>",
    ]
    detail_html = "".join(detail_parts) if compact else "\n".join(detail_parts) + "\n"

    selectors = [f".{classes['heading']}", f"#{ids['title']}"]
    if options.get("reverse_selectors"):
        selectors.reverse()
    if options.get("changed_selector"):
        selectors[0] = f".{classes['note']}"
    rule1_decls = [("color", fg), ("font-weight", "700"), ("line-height", "1.2")]
    rule2_decls = [("background-color", bg), ("padding-top", f"{8 + index % 4}px"), ("padding-right", "10px"), ("padding-bottom", "8px"), ("padding-left", "10px")]
    rule3_decls = [("color", accent_color), ("text-decoration-line", "underline")]
    asset_from_css = _rel(paths["css"], paths["asset"])
    rule4_decls = [("background-image", f'url("{asset_from_css}")'), ("background-color", bg)]
    if options.get("changed_css"):
        rule2_decls[0] = ("background-color", "#000")
    if options.get("reverse_decls"):
        rule1_decls.reverse(); rule2_decls.reverse(); rule3_decls.reverse(); rule4_decls.reverse()

    def rule(selector: str, decls: list[tuple[str, str]]) -> str:
        if compact:
            return selector + "{" + ";".join(f"{k}:{v}" for k, v in decls) + ";}"
        return selector + " {\n" + "\n".join(f"  {k}: {v};" for k, v in decls) + "\n}"

    css_parts = [
        rule(", ".join(selectors), rule1_decls),
        rule(f".{classes['card']}", rule2_decls),
        rule(f".{classes['link']}", rule3_decls),
        rule(f".{classes['image']}", rule4_decls),
        rule(f".{classes['detail']} > .{classes['note']}", [("font-style", "italic"), ("margin-top", "4px")]),
    ]
    if options.get("comments"):
        css_parts.insert(0, "/* inert source comment */")
    css = "".join(css_parts) if compact else "\n\n".join(css_parts) + "\n"

    resources = [paths["root"], paths["detail"], paths["css"], paths["asset"]]
    manifest = {"format": "iwb-1", "root": paths["root"], "resources": resources}
    _write(dest / "bundle.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _write(dest / paths["root"], root_html)
    _write(dest / paths["detail"], detail_html)
    _write(dest / paths["css"], css)
    asset = PNG_1X1 + (b"changed" if options.get("changed_asset") else b"")
    asset_path = dest / paths["asset"]
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(asset)


def emit_owned_suite(destination: str | Path, count: int = 24) -> None:
    dest = Path(destination)
    fresh_directory(dest)
    for index in range(count):
        emit_bundle(dest / f"fixture-{index:02d}", index)


def emit_variant_suite(base_destination: str | Path, output_destination: str | Path, count: int = 24) -> list[dict[str, Any]]:
    # base_destination is accepted to make the derivation explicit; fixtures are
    # regenerated from the same owned specification rather than source rewriting.
    _ = Path(base_destination)
    out = Path(output_destination)
    fresh_directory(out)
    records: list[dict[str, Any]] = []
    for index in range(count):
        for variant in LEGAL_VARIANTS + INVALID_VARIANTS:
            path = out / f"fixture-{index:02d}" / variant.name
            emit_bundle(path, index, variant.options)
            records.append({"fixture": f"fixture-{index:02d}", "variant": variant.name, "kind": variant.kind, "path": str(path)})
    return records


def emit_global_coupling_pair(destination: str | Path) -> tuple[Path, Path]:
    """Two eligible bundles that match resource-locally but not globally."""
    dest = Path(destination)
    fresh_directory(dest)
    left = dest / "left"
    right = dest / "right"
    for root, names, swapped in [(left, ("a", "b"), False), (right, ("x", "y"), True)]:
        root.mkdir(parents=True)
        n0, n1 = names
        manifest = {"format": "iwb-1", "root": "index.html", "resources": ["index.html", "one.html", "two.html"]}
        _write(root / "bundle.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        _write(root / "index.html", "\n".join([
            "<!doctype html>", "<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Coupling</title></head>",
            f"<body><div class=\"{n0}\">A</div><div class=\"{n1}\">B</div>",
            "<a href=\"one.html\">One</a><a href=\"two.html\">Two</a></body></html>", ""
        ]))
        _write(root / "one.html", "\n".join([
            "<!doctype html>", "<html lang=\"en\"><head><meta charset=\"utf-8\"><title>One</title></head>",
            f"<body><div class=\"{n0}\">left</div><span class=\"{n1}\">right</span></body></html>", ""
        ]))
        a, b = (n1, n0) if swapped else (n0, n1)
        _write(root / "two.html", "\n".join([
            "<!doctype html>", "<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Two</title></head>",
            f"<body><div class=\"{a}\">left</div><span class=\"{b}\">right</span></body></html>", ""
        ]))
    return left, right
