"""Deliberately simpler comparison baselines and one unsafe ablation."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from . import limits
from .producer_core import parse_bundle, AdmissionError, _resolve_ref, _rewrite_css_urls
from .checker_core import _replay_positive

HTML_COMMENT = re.compile(rb"<!--.*?-->", re.S)
CSS_COMMENT = re.compile(rb"/\*.*?\*/", re.S)
SPACE = re.compile(rb"\s+")


def byte_inventory_equal(left_dir: str | Path, right_dir: str | Path) -> bool:
    def inventory(root: Path) -> list[tuple[str, bytes]]:
        return sorted(
            (p.relative_to(root).as_posix(), p.read_bytes())
            for p in root.rglob("*") if p.is_file()
        )
    return inventory(Path(left_dir)) == inventory(Path(right_dir))


def lexical_equal(left_dir: str | Path, right_dir: str | Path) -> bool:
    """Ignore comments and whitespace only; retain paths and all names/order."""
    def digest(root: Path) -> str:
        parts: list[bytes] = []
        for p in sorted((x for x in root.rglob("*") if x.is_file()), key=lambda x: x.relative_to(root).as_posix()):
            rel = p.relative_to(root).as_posix().encode()
            data = p.read_bytes()
            if p.suffix.lower() == ".html":
                data = HTML_COMMENT.sub(b"", data)
                data = SPACE.sub(b" ", data).strip()
            elif p.suffix.lower() == ".css":
                data = CSS_COMMENT.sub(b"", data)
                data = SPACE.sub(b" ", data).strip()
            parts.extend([rel, b"\0", data, b"\0"])
        return sha256(b"".join(parts)).hexdigest()
    return digest(Path(left_dir)) == digest(Path(right_dir))


def syntax_no_alpha_equal(left_dir: str | Path, right_dir: str | Path) -> bool:
    """Normalize admitted orderings, but retain original paths and names."""
    try:
        left = parse_bundle(left_dir)
        right = parse_bundle(right_dir)
        cert = {
            "resource_map": {x: x for x in left.resources},
            "id_map": {x: x for x in left.id_order},
            "class_map": {x: x for x in left.class_order},
        }
        _replay_positive(left, right, cert)
        return True
    except (AdmissionError, KeyError, ValueError):
        return False


def _local_maps(bundle: Any) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    ids: dict[str, dict[str, str]] = {}
    classes: dict[str, dict[str, str]] = {}
    for path in bundle.resource_order:
        res = bundle.resources[path]
        imap: dict[str, str] = {}
        cmap: dict[str, str] = {}
        if res["kind"] == "html":
            for event in res["events"]:
                if event.kind != "start":
                    continue
                _tag, attrs, _sc = event.data
                amap = dict(attrs)
                if "id" in amap and amap["id"] not in imap:
                    imap[amap["id"]] = f"i{len(imap)}"
                if "class" in amap:
                    for name in amap["class"].split():
                        if name not in cmap:
                            cmap[name] = f"c{len(cmap)}"
        elif res["kind"] == "css":
            for rule in res["rules"]:
                for selector in rule.selectors:
                    for token in selector:
                        if token.startswith("#") and token[1:] not in imap:
                            imap[token[1:]] = f"i{len(imap)}"
                        elif token.startswith(".") and token[1:] not in cmap:
                            cmap[token[1:]] = f"c{len(cmap)}"
        ids[path] = imap
        classes[path] = cmap
    return ids, classes


def local_alpha_signature(root_dir: str | Path) -> bytes:
    """Unsafe ablation: alpha-normalize each resource independently.

    Cross-resource occurrences are intentionally not tied to one global map.
    It is useful only as a negative control.
    """
    bundle = parse_bundle(root_dir)
    local_ids, local_classes = _local_maps(bundle)
    path_ids = bundle.resource_ids

    def target_local_id(target: str, fragment: str) -> str:
        return local_ids.get(target, {}).get(fragment, "unbound:" + fragment)

    resources: list[Any] = []
    for path in bundle.resource_order:
        res = bundle.resources[path]
        if res["kind"] == "asset":
            body: Any = [len(res["bytes"]), sha256(res["bytes"]).hexdigest()]
        elif res["kind"] == "html":
            body = []
            for event in res["events"]:
                if event.kind in {"doctype", "text", "end"}:
                    body.append([event.kind, event.data])
                    continue
                tag, attrs, self_closing = event.data
                attrs_out: list[Any] = []
                for key, value in sorted(attrs):
                    if key == "id":
                        val = ["id", local_ids[path][value]]
                    elif key == "class":
                        val = ["classes", sorted(local_classes[path][x] for x in value.split())]
                    elif key in limits.REFERENCE_ATTRS:
                        target, fragment = _resolve_ref(path, value, f"{path}@{key}")
                        target = path if target is None else target
                        val = ["ref", path_ids[target], target_local_id(target, fragment) if fragment else None]
                    else:
                        val = ["literal", value]
                    attrs_out.append([key, val])
                body.append(["start", tag, attrs_out, bool(self_closing)])
        else:
            body = []
            for rule in res["rules"]:
                sels: list[Any] = []
                for selector in rule.selectors:
                    mapped: list[str] = []
                    for token in selector:
                        if token.startswith("#"):
                            mapped.append("#" + local_ids[path][token[1:]])
                        elif token.startswith("."):
                            mapped.append("." + local_classes[path][token[1:]])
                        else:
                            mapped.append(token)
                    sels.append(mapped)
                sels.sort()
                decls: list[Any] = []
                for prop, value in sorted(rule.declarations):
                    location = f"{path}:{prop}"

                    def repl(raw_target: str) -> str:
                        target, fragment = _resolve_ref(path, raw_target, location)
                        if target is None or fragment is not None:
                            return "url(@bad)"
                        return f"url(@{path_ids[target]})"

                    decls.append([prop, _rewrite_css_urls(value, location, repl)])
                body.append([sels, decls])
        resources.append([path_ids[path], res["kind"], body])
    obj = [path_ids[bundle.root], resources]
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def local_alpha_equal(left_dir: str | Path, right_dir: str | Path) -> bool:
    try:
        return local_alpha_signature(left_dir) == local_alpha_signature(right_dir)
    except AdmissionError:
        return False
