"""Tiny exhaustive orbit oracle for the declared bundle relation.

The oracle deliberately does not call the certificate checker and never compares
canonical forms.  It reuses the producer's admitted parse tree only, enumerates
all total resource/ID/class bijections within a small cap, and evaluates the
relation with separate matching code below.  It is exponential and is therefore
used only for the frozen tiny suites.
"""
from __future__ import annotations

from itertools import permutations
import posixpath
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from .producer_core import ParsedBundle, parse_bundle



def _resource_maps(left: ParsedBundle, right: ParsedBundle) -> Iterator[dict[str, str]]:
    if len(left.resources) != len(right.resources):
        return
    if left.resources[left.root]["kind"] != right.resources[right.root]["kind"]:
        return
    left_rest = [p for p in left.resources if p != left.root]
    right_rest = [p for p in right.resources if p != right.root]
    for target_order in permutations(right_rest):
        mapping = {left.root: right.root, **dict(zip(left_rest, target_order))}
        if all(left.resources[a]["kind"] == right.resources[b]["kind"] for a, b in mapping.items()):
            yield mapping


def _symbol_maps(left: list[str], right: list[str]) -> Iterator[dict[str, str]]:
    if len(left) != len(right):
        return
    for target_order in permutations(right):
        yield dict(zip(left, target_order))


def _resolve(base_path: str, raw: str) -> tuple[str, str | None]:
    """Resolve an already-admitted local reference without importing checker code."""
    parts = urlsplit(raw.strip())
    target = base_path if not parts.path else posixpath.normpath(
        posixpath.join(posixpath.dirname(base_path), parts.path)
    )
    return target, parts.fragment or None


def _is_escaped(text: str, index: int) -> bool:
    count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        count += 1
        cursor -= 1
    return bool(count % 2)


def _rewrite_css_urls(value: str, mapper: Any) -> str:
    """Independent url() scanner for already-admitted CSS values."""
    replacements: list[tuple[int, int, str]] = []
    quote: str | None = None
    i = 0
    while i < len(value):
        ch = value[i]
        if quote is not None:
            if ch == quote and not _is_escaped(value, i):
                quote = None
            i += 1
            continue
        if ch in {"'", '"'}:
            quote = ch
            i += 1
            continue
        boundary = i == 0 or not (value[i - 1].isalnum() or value[i - 1] in {"_", "-"})
        if boundary and value[i:i + 4].lower() == "url(":
            start = i
            j = i + 4
            while j < len(value) and value[j].isspace():
                j += 1
            if value[j] in {"'", '"'}:
                delimiter = value[j]
                j += 1
                target_start = j
                while not (value[j] == delimiter and not _is_escaped(value, j)):
                    j += 1
                target = value[target_start:j]
                j += 1
                while value[j].isspace():
                    j += 1
                end = j + 1
            else:
                target_start = j
                while value[j] != ")":
                    j += 1
                target = value[target_start:j].strip()
                end = j + 1
            replacements.append((start, end, mapper(target)))
            i = end
            continue
        i += 1
    if not replacements:
        return value
    out: list[str] = []
    cursor = 0
    for start, end, replacement in replacements:
        out.extend((value[cursor:start], replacement))
        cursor = end
    out.append(value[cursor:])
    return "".join(out)


def _html_view(
    path: str,
    events: list[Any],
    resource_map: dict[str, str],
    id_map: dict[str, str],
    class_map: dict[str, str],
) -> tuple[Any, ...]:
    out: list[Any] = []
    for event in events:
        if event.kind in {"doctype", "end", "text"}:
            out.append((event.kind, event.data))
            continue
        tag, attrs, self_closing = event.data
        normalized: list[Any] = []
        for key, value in sorted(attrs):
            if key == "id":
                normalized.append((key, ("id", id_map[value])))
            elif key == "class":
                normalized.append((key, ("classes", tuple(sorted(class_map[n] for n in value.split())))))
            elif key in {"href", "src"}:
                target, fragment = _resolve(path, value)
                normalized.append((key, ("ref", resource_map[target], id_map[fragment] if fragment else None)))
            else:
                normalized.append((key, ("literal", value)))
        out.append(("start", tag, tuple(normalized), bool(self_closing)))
    return tuple(out)


def _css_view(
    path: str,
    rules: tuple[Any, ...],
    resource_map: dict[str, str],
    id_map: dict[str, str],
    class_map: dict[str, str],
) -> tuple[Any, ...]:
    out: list[Any] = []
    for rule in rules:
        selectors: list[tuple[str, ...]] = []
        for selector in rule.selectors:
            mapped: list[str] = []
            for token in selector:
                if token.startswith("#"):
                    mapped.append("#" + id_map[token[1:]])
                elif token.startswith("."):
                    mapped.append("." + class_map[token[1:]])
                else:
                    mapped.append(token)
            selectors.append(tuple(mapped))
        selectors.sort()
        declarations: list[tuple[str, str]] = []
        for prop, value in sorted(rule.declarations):
            def repl(raw_target: str) -> str:
                target, fragment = _resolve(path, raw_target)
                if fragment is not None:
                    return "url(@invalid-fragment)"
                return f"url(@{resource_map[target]})"

            declarations.append((prop, _rewrite_css_urls(value, repl)))
        out.append((tuple(selectors), tuple(declarations)))
    return tuple(out)


def _mapping_matches(
    left: ParsedBundle,
    right: ParsedBundle,
    resource_map: dict[str, str],
    id_map: dict[str, str],
    class_map: dict[str, str],
) -> bool:
    if resource_map.get(left.root) != right.root:
        return False
    identity_resources = {p: p for p in right.resources}
    identity_ids = {name: name for name in right.id_order}
    identity_classes = {name: name for name in right.class_order}
    for source_path, target_path in resource_map.items():
        source = left.resources[source_path]
        target = right.resources[target_path]
        if source["kind"] != target["kind"]:
            return False
        if source["kind"] == "asset":
            if source["bytes"] != target["bytes"]:
                return False
        elif source["kind"] == "html":
            if _html_view(source_path, source["events"], resource_map, id_map, class_map) != _html_view(
                target_path, target["events"], identity_resources, identity_ids, identity_classes
            ):
                return False
        elif source["kind"] == "css":
            if _css_view(source_path, source["rules"], resource_map, id_map, class_map) != _css_view(
                target_path, target["rules"], identity_resources, identity_ids, identity_classes
            ):
                return False
        else:
            return False
    return True


def exact_equivalent_parsed(
    left: ParsedBundle,
    right: ParsedBundle,
    *,
    max_trials: int = 200_000,
) -> tuple[bool, int]:
    """Return exact orbit membership and the number of candidate maps tried."""
    if len(left.id_order) != len(right.id_order) or len(left.class_order) != len(right.class_order):
        return False, 0
    trials = 0
    for rmap in _resource_maps(left, right):
        for imap in _symbol_maps(left.id_order, right.id_order):
            for cmap in _symbol_maps(left.class_order, right.class_order):
                trials += 1
                if trials > max_trials:
                    raise RuntimeError("tiny oracle trial cap exceeded")
                if _mapping_matches(left, right, rmap, imap, cmap):
                    return True, trials
    return False, trials


def exact_equivalent(
    left_dir: str | Path,
    right_dir: str | Path,
    *,
    max_trials: int = 200_000,
) -> tuple[bool, int]:
    return exact_equivalent_parsed(
        parse_bundle(left_dir), parse_bundle(right_dir), max_trials=max_trials
    )
