"""Producer-side IWB implementation.

The parsing/canonicalization core is a same-source module copy, not an
independently implemented parser. It never renders or executes webpage content.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
import posixpath
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit
import unicodedata

from . import limits

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,79}$")
TAG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PROP_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SELECTOR_TOKEN_RE = re.compile(r"([.#][A-Za-z_][A-Za-z0-9_-]*|\*|[A-Za-z][A-Za-z0-9-]*|>|\+|~|\s+)")


class AdmissionError(ValueError):
    def __init__(self, code: str, location: str, detail: str):
        super().__init__(f"{code} at {location}: {detail}")
        self.code = code
        self.location = location
        self.detail = detail if len(detail) <= 256 else detail[:240] + "...[truncated]"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "detail": self.detail}



class EnvironmentFailure(RuntimeError):
    """I/O, permission, or observed snapshot instability: no language verdict."""
    def __init__(self, code: str, location: str, detail: str):
        super().__init__(f"{code} at {location}: {detail}")
        self.code, self.location, self.detail = code, location, detail

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "detail": self.detail}


def _stat_signature(st: os.stat_result, *, cross_api: bool = False) -> tuple[int, ...]:
    # Windows runtimes may expose birth time as path-stat ctime but change time
    # as fstat ctime. Compare ctime within each API, never across those meanings.
    timestamp = (getattr(st, "st_birthtime_ns", 0)
                 if cross_api and os.name == "nt" else st.st_ctime_ns)
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, timestamp)


def _regular_stat(path: Path, location: str) -> os.stat_result:
    try:
        st = path.lstat()
    except OSError as exc:
        raise EnvironmentFailure("stat-failed", location, type(exc).__name__) from exc
    if stat.S_ISLNK(st.st_mode):
        raise AdmissionError("symlink", location, "symlinks are forbidden")
    if not stat.S_ISREG(st.st_mode):
        raise AdmissionError("nonregular-file", location, "only regular files are admitted")
    return st


def _read_stable(path: Path, location: str, before: os.stat_result, cap: int) -> bytes:
    """Bound the read and reject observed changes, without claiming atomic snapshots."""
    try:
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if _stat_signature(before, cross_api=True) != _stat_signature(opened, cross_api=True):
                raise EnvironmentFailure("file-changed", location, "changed before read")
            data = handle.read(cap + 1)
            after_read = os.fstat(handle.fileno())
        after_path = path.lstat()
    except OSError as exc:
        raise EnvironmentFailure("read-failed", location, type(exc).__name__) from exc
    if (len(data) != before.st_size or len(data) > cap
            or _stat_signature(opened) != _stat_signature(after_read)
            or _stat_signature(before) != _stat_signature(after_path)):
        raise EnvironmentFailure("file-changed", location, "changed during read")
    return data


def _directory_entries(directory: Path, root: Path) -> list[Path]:
    try:
        with os.scandir(directory) as entries:
            names = sorted(entry.name for entry in entries)
    except OSError as exc:
        raise EnvironmentFailure("directory-read-failed", directory.relative_to(root).as_posix(),
                                 type(exc).__name__) from exc
    return [directory / name for name in names]


def _inventory(root: Path) -> set[str]:
    """Lexicographic-name depth-first traversal; never follow directory symlinks."""
    found: set[str] = set()
    pending = list(reversed(_directory_entries(root, root)))
    while pending:
        path = pending.pop()
        rel = path.relative_to(root).as_posix()
        try:
            st = path.lstat()
        except OSError as exc:
            raise EnvironmentFailure("stat-failed", rel, type(exc).__name__) from exc
        if stat.S_ISLNK(st.st_mode):
            raise AdmissionError("symlink", rel, "symlinks are forbidden")
        if stat.S_ISDIR(st.st_mode):
            pending.extend(reversed(_directory_entries(path, root)))
        elif not stat.S_ISREG(st.st_mode):
            raise AdmissionError("nonregular-file", rel, "only regular files and directories are admitted")
        elif rel != "bundle.json":
            found.add(rel)
    return found

def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _is_escaped(text: str, index: int) -> bool:
    """Return whether text[index] is preceded by an odd backslash run."""
    count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        count += 1
        cursor -= 1
    return bool(count % 2)


def _strict_json_loads(raw: bytes, location: str) -> Any:
    """Decode bounded UTF-8 JSON while rejecting duplicate object keys."""
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate JSON key {key!r}")
            out[key] = value
        return out

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AdmissionError("bad-json", location, str(exc)) from exc


def _safe_manifest_path(value: str, location: str) -> str:
    if not isinstance(value, str) or not value or len(value) > limits.MAX_PATH_LENGTH:
        raise AdmissionError("bad-path", location, "path must be a nonempty bounded string")
    if "\\" in value or "\x00" in value:
        raise AdmissionError("bad-path", location, "backslashes and NUL are forbidden")
    # Validate raw components before PurePosixPath can erase '.' or empty parts.
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise AdmissionError("bad-path", location, "path must be normalized and relative")
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise AdmissionError("bad-path", location, "surrogate code points are forbidden")
    return str(PurePosixPath(value))


def _valid_name(value: str, location: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise AdmissionError("bad-name", location, f"unsupported identifier {value!r}")
    return value


def _resolve_ref(base_path: str, raw: str, location: str) -> tuple[str | None, str | None]:
    raw = _nfc(raw.strip())
    if not raw:
        raise AdmissionError("bad-reference", location, "empty reference")
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise AdmissionError("bad-reference", location, "malformed URL syntax") from exc
    if parts.scheme or parts.netloc or "?" in raw.partition("#")[0]:
        raise AdmissionError("external-reference", location, "schemes, authorities, and queries are outside the model")
    if parts.path.startswith("/") or "\\" in parts.path:
        raise AdmissionError("external-reference", location, "absolute or backslash paths are outside the model")
    fragment = parts.fragment if "#" in raw else None
    if fragment is not None:
        _valid_name(fragment, location + "#fragment")
    if not parts.path:
        return None, fragment
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base_path), parts.path))
    if joined.startswith("../") or joined == ".." or joined.startswith("/"):
        raise AdmissionError("escaping-reference", location, raw)
    return _safe_manifest_path(joined, location), fragment


@dataclass(frozen=True)
class HtmlEvent:
    kind: str
    data: Any
    line: int
    column: int


class _HTMLCollector(HTMLParser):
    def __init__(self, path: str):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.events: list[HtmlEvent] = []
        self.stack: list[str] = []
        self.seen_doctype = False
        self._text_parts: list[str] = []
        self._text_position = (1, 1)

    def _flush_text(self) -> None:
        # A maximal data run may cross comments or parser callback boundaries.
        # Normalize only after concatenation; never erase a space within a run.
        if not self._text_parts:
            return
        data = _nfc("".join(self._text_parts))
        self._text_parts.clear()
        if data and not data.isspace():
            line, col = self._text_position
            self.events.append(HtmlEvent("text", data, line, col))

    def _loc(self) -> str:
        line, col = self.getpos()
        return f"{self.path}:{line}:{col + 1}"

    def _record_start(self, tag: str, attrs: list[tuple[str, str | None]], self_closing: bool) -> None:
        self._flush_text()
        tag = tag.lower()
        if tag in limits.FORBIDDEN_TAGS or tag not in limits.ALLOWED_TAGS:
            raise AdmissionError("forbidden-tag", self._loc(), tag)
        if not TAG_RE.fullmatch(tag):
            raise AdmissionError("bad-tag", self._loc(), tag)
        if self_closing and tag not in limits.VOID_TAGS:
            raise AdmissionError("self-closing-nonvoid", self._loc(), tag)
        seen: set[str] = set()
        normalized: list[tuple[str, str]] = []
        for key, value in attrs:
            key = key.lower()
            if key in seen:
                raise AdmissionError("duplicate-attribute", self._loc(), key)
            seen.add(key)
            allowed_here = key in limits.GLOBAL_ATTRS or key in limits.TAG_ATTRS.get(tag, set())
            if key.startswith("on") or key == "style" or key not in limits.ALLOWED_ATTRS or not allowed_here:
                raise AdmissionError("forbidden-attribute", self._loc(), f"{tag}@{key}")
            if value is None:
                raise AdmissionError("valueless-attribute", self._loc(), key)
            value = _nfc(value)
            if key == "id":
                _valid_name(value, self._loc() + "@id")
            if key == "class":
                names = value.split()
                if not names or len(names) != len(set(names)):
                    raise AdmissionError("bad-class-list", self._loc(), value)
                for name in names:
                    _valid_name(name, self._loc() + "@class")
            normalized.append((key, value))
        line, col = self.getpos()
        self.events.append(HtmlEvent("start", (tag, tuple(normalized), self_closing or tag in limits.VOID_TAGS), line, col + 1))
        if not (self_closing or tag in limits.VOID_TAGS):
            self.stack.append(tag)

    def handle_decl(self, decl: str) -> None:
        self._flush_text()
        if decl.strip().lower() != "doctype html" or self.seen_doctype or self.events:
            raise AdmissionError("bad-doctype", self._loc(), decl)
        self.seen_doctype = True
        line, col = self.getpos()
        self.events.append(HtmlEvent("doctype", "html", line, col + 1))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_start(tag, attrs, False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_start(tag, attrs, True)

    def handle_endtag(self, tag: str) -> None:
        self._flush_text()
        tag = tag.lower()
        if tag in limits.VOID_TAGS:
            raise AdmissionError("void-end-tag", self._loc(), tag)
        if not self.stack or self.stack[-1] != tag:
            raise AdmissionError("unbalanced-html", self._loc(), tag)
        self.stack.pop()
        line, col = self.getpos()
        self.events.append(HtmlEvent("end", tag, line, col + 1))

    def handle_data(self, data: str) -> None:
        if not self._text_parts:
            line, col = self.getpos()
            self._text_position = (line, col + 1)
        self._text_parts.append(data)

    def handle_comment(self, data: str) -> None:
        # A comment emits no event and does not end a maximal text run.
        return

    def handle_pi(self, data: str) -> None:
        raise AdmissionError("processing-instruction", self._loc(), data[:80])

    def unknown_decl(self, data: str) -> None:
        raise AdmissionError("unknown-declaration", self._loc(), data[:80])

    def close_checked(self) -> None:
        if self.rawdata.startswith("<!--"):
            raise AdmissionError("bad-html-comment", self._loc(), "unterminated comment")
        super().close()
        self._flush_text()
        if self.stack:
            raise AdmissionError("unbalanced-html", self.path, f"unclosed tag {self.stack[-1]}")
        if not self.seen_doctype:
            raise AdmissionError("missing-doctype", self.path, "<!doctype html> is required")
        starts = [event.data[0] for event in self.events if event.kind == "start"]
        if starts.count("html") != 1 or starts.count("head") != 1 or starts.count("body") != 1:
            raise AdmissionError("bad-document-shape", self.path, "exactly one html, head, and body element is required")
        if len(self.events) < 3 or self.events[0].kind != "doctype" or self.events[1].kind != "start" or self.events[1].data[0] != "html" or self.events[-1].kind != "end" or self.events[-1].data != "html":
            raise AdmissionError("bad-document-shape", self.path, "document must be rooted by html after the doctype")
        # Require the conventional document skeleton rather than merely counting
        # tag names.  The direct children of html are exactly head then body.
        stack: list[str] = []
        html_children: list[str] = []
        for event in self.events[1:]:
            if event.kind == "start":
                tag, _attrs, self_closing = event.data
                if stack == ["html"]:
                    html_children.append(tag)
                if not self_closing:
                    stack.append(tag)
            elif event.kind == "text":
                if stack == ["html"]:
                    raise AdmissionError("bad-document-shape", self.path, "text may not be a direct child of html")
            elif event.kind == "end":
                if not stack or stack[-1] != event.data:
                    raise AdmissionError("bad-document-shape", self.path, "invalid structural stack")
                stack.pop()
        if html_children != ["head", "body"] or stack:
            raise AdmissionError("bad-document-shape", self.path, "html children must be exactly head then body")
        if len(self.events) > limits.MAX_EVENTS:
            raise AdmissionError("too-many-events", self.path, str(len(self.events)))


@dataclass(frozen=True)
class CssRule:
    selectors: tuple[tuple[str, ...], ...]
    declarations: tuple[tuple[str, str], ...]
    ordinal: int


def _split_outside(text: str, delimiter: str, location: str) -> list[str]:
    out: list[str] = []
    start = 0
    quote: str | None = None
    paren = 0
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and not _is_escaped(text, i):
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
        elif ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
            if paren < 0:
                raise AdmissionError("bad-css", location, "unbalanced parentheses")
        elif ch == delimiter and paren == 0:
            out.append(text[start:i])
            start = i + 1
    if quote or paren:
        raise AdmissionError("bad-css", location, "unterminated string or parentheses")
    out.append(text[start:])
    return out


def _selector_tokens(selector: str, location: str) -> tuple[str, ...]:
    if any(ch in selector for ch in "[]():"):
        raise AdmissionError("unsupported-selector", location, selector.strip())
    pos = 0
    raw: list[str] = []
    while pos < len(selector):
        match = SELECTOR_TOKEN_RE.match(selector, pos)
        if not match:
            raise AdmissionError("unsupported-selector", location, selector.strip())
        token = match.group(0)
        pos = match.end()
        if token.isspace():
            token = " "
            if raw and raw[-1] not in {" ", ">", "+", "~"}:
                raw.append(token)
        else:
            if raw and raw[-1] == " " and token in {">", "+", "~"}:
                raw.pop()
            raw.append(token.lower() if token[0].isalpha() else token)
    while raw and raw[-1] == " ":
        raw.pop()
    if not raw:
        raise AdmissionError("unsupported-selector", location, "empty selector")
    combinators = {" ", ">", "+", "~"}
    in_compound = False
    for token in raw:
        if token in combinators:
            if not in_compound:
                raise AdmissionError("unsupported-selector", location, selector.strip())
            in_compound = False
            continue
        if token.startswith((".", "#")):
            _valid_name(token[1:], location)
        elif in_compound:
            # A compound may contain one type/universal selector followed by
            # class/id qualifiers, but not a second adjacent type selector.
            raise AdmissionError("unsupported-selector", location, selector.strip())
        in_compound = True
    if not in_compound:
        raise AdmissionError("unsupported-selector", location, selector.strip())
    return tuple(raw)


def _strip_css_comments(text: str, location: str) -> str:
    """Single-pass zero-width prelexical erasure outside strings, not CSS semantics."""
    out: list[str] = []
    i = 0
    quote: str | None = None
    while i < len(text):
        ch = text[i]
        if quote is not None:
            out.append(ch)
            if ch == quote and not _is_escaped(text, i):
                quote = None
            i += 1
            continue
        if ch in {"'", '"'}:
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise AdmissionError("bad-css", location, "unterminated comment")
            # IWB explicitly uses zero-width prelexical erasure, not a claim
            # of equivalence between browser CSS token streams.
            i = end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _normalize_css_value(value: str, location: str) -> str:
    """Collapse CSS whitespace outside strings while preserving string bytes."""
    value = _nfc(value.strip())
    out: list[str] = []
    i = 0
    quote: str | None = None
    pending_space = False
    while i < len(value):
        ch = value[i]
        if quote is not None:
            out.append(ch)
            if ch == quote and not _is_escaped(value, i):
                quote = None
            i += 1
            continue
        if ch in {"'", '"'}:
            if pending_space and out:
                out.append(" ")
            pending_space = False
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch in "\t\n\r\f ":
            pending_space = True
            i += 1
            continue
        if pending_space and out:
            out.append(" ")
        pending_space = False
        out.append(ch)
        i += 1
    if quote is not None:
        raise AdmissionError("bad-css", location, "unterminated string")
    return "".join(out)


def _css_url_occurrences(value: str, location: str) -> list[tuple[int, int, str]]:
    """Scan CSS url() functions outside quoted strings.

    The admitted language deliberately recognizes only an unescaped ASCII
    ``url(`` function token.  Text that merely spells ``url(...)`` inside a
    quoted CSS string is literal data, not a resource edge.  Malformed genuine
    url() functions are rejected deterministically.
    """
    found: list[tuple[int, int, str]] = []
    quote: str | None = None
    i = 0
    n = len(value)
    while i < n:
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
        is_boundary = i == 0 or not (value[i - 1].isalnum() or value[i - 1] in {"_", "-"})
        if is_boundary and value[i:i + 4].lower() == "url(":
            start = i
            j = i + 4
            while j < n and value[j].isspace():
                j += 1
            if j >= n:
                raise AdmissionError("bad-css-reference", location, value[start:])
            if value[j] in {"'", '"'}:
                delimiter = value[j]
                j += 1
                target_start = j
                while j < n and not (value[j] == delimiter and not _is_escaped(value, j)):
                    j += 1
                if j >= n:
                    raise AdmissionError("bad-css-reference", location, value[start:])
                target = value[target_start:j]
                j += 1
                while j < n and value[j].isspace():
                    j += 1
                if j >= n or value[j] != ")":
                    raise AdmissionError("bad-css-reference", location, value[start:j + 1])
                end = j + 1
            else:
                target_start = j
                while j < n and value[j] != ")":
                    if value[j] in {"'", '"', "("}:
                        raise AdmissionError("bad-css-reference", location, value[start:j + 1])
                    j += 1
                if j >= n:
                    raise AdmissionError("bad-css-reference", location, value[start:])
                target = value[target_start:j].strip()
                end = j + 1
            if not target:
                raise AdmissionError("bad-css-reference", location, value[start:end])
            found.append((start, end, target))
            i = end
            continue
        i += 1
    if quote is not None:
        raise AdmissionError("bad-css", location, "unterminated string")
    return found


def _rewrite_css_urls(value: str, location: str, mapper: Callable[[str], str]) -> str:
    occurrences = _css_url_occurrences(value, location)
    if not occurrences:
        return value
    out: list[str] = []
    cursor = 0
    for start, end, target in occurrences:
        out.append(value[cursor:start])
        out.append(mapper(target))
        cursor = end
    out.append(value[cursor:])
    return "".join(out)


def _parse_css(text: str, path: str) -> tuple[CssRule, ...]:
    text = _strip_css_comments(_nfc(text), path)
    if "@" in text:
        raise AdmissionError("at-rule", path, "at-rules are outside the model")
    rules: list[CssRule] = []
    declaration_count = 0
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i == n:
            break
        open_brace = text.find("{", i)
        if open_brace < 0:
            raise AdmissionError("bad-css", path, "missing opening brace")
        selector_text = text[i:open_brace].strip()
        quote: str | None = None
        paren = 0
        close_brace = -1
        j = open_brace + 1
        while j < n:
            ch = text[j]
            if quote:
                if ch == quote and not _is_escaped(text, j):
                    quote = None
            elif ch in {"'", '"'}:
                quote = ch
            elif ch == "(":
                paren += 1
            elif ch == ")":
                paren -= 1
                if paren < 0:
                    raise AdmissionError("bad-css", f"{path}:rule{len(rules)}", "unbalanced parentheses")
            elif ch == "{" and paren == 0:
                raise AdmissionError("nested-css", f"{path}:rule{len(rules)}", "nested blocks are outside the model")
            elif ch == "}" and paren == 0:
                close_brace = j
                break
            j += 1
        if close_brace < 0 or quote or paren:
            raise AdmissionError("bad-css", path, "unterminated rule")
        rule_loc = f"{path}:rule{len(rules)}"
        selectors = tuple(_selector_tokens(part.strip(), rule_loc) for part in _split_outside(selector_text, ",", rule_loc))
        body = text[open_brace + 1:close_brace]
        declarations: list[tuple[str, str]] = []
        seen_props: set[str] = set()
        for part in _split_outside(body, ";", rule_loc):
            if not part.strip():
                continue
            if ":" not in part:
                raise AdmissionError("bad-declaration", rule_loc, part.strip())
            prop, value = part.split(":", 1)
            prop = prop.strip().lower()
            value = _normalize_css_value(value, rule_loc)
            if not PROP_RE.fullmatch(prop) or prop not in limits.ALLOWED_PROPERTIES:
                raise AdmissionError("unsupported-property", rule_loc, prop)
            if prop in seen_props:
                raise AdmissionError("duplicate-property", rule_loc, prop)
            if not value or "!important" in value.lower() or "var(" in value.lower():
                raise AdmissionError("unsupported-value", rule_loc, value)
            seen_props.add(prop)
            declarations.append((prop, value))
            declaration_count += 1
            if declaration_count > limits.MAX_DECLARATIONS:
                raise AdmissionError("too-much-css", path, "rule/declaration bound exceeded")
        if not declarations:
            raise AdmissionError("empty-rule", rule_loc, selector_text)
        rules.append(CssRule(selectors, tuple(declarations), len(rules)))
        if len(rules) > limits.MAX_RULES:
            raise AdmissionError("too-much-css", path, "rule/declaration bound exceeded")
        i = close_brace + 1
    return tuple(rules)


@dataclass
class ParsedBundle:
    root_dir: Path
    root: str
    resources: dict[str, dict[str, Any]]
    resource_order: list[str]
    resource_ids: dict[str, str]
    id_order: list[str]
    id_ids: dict[str, str]
    class_order: list[str]
    class_ids: dict[str, str]
    canonical_obj: dict[str, Any]
    canonical_bytes: bytes


def _attr_references(path: str, tag: str, attrs: Iterable[tuple[str, str]], loc: str) -> list[tuple[str, str | None, str]]:
    refs: list[tuple[str, str | None, str]] = []
    attr_map = dict(attrs)
    for key, value in sorted(attrs):
        if key not in limits.REFERENCE_ATTRS:
            continue
        # Fragment-only anchors are namespace references, not resource edges.
        target, fragment = _resolve_ref(path, value, f"{loc}@{key}")
        if target is not None:
            refs.append((target, fragment, f"{tag}:{key}"))
        elif fragment is not None:
            refs.append((path, fragment, f"{tag}:{key}"))
        else:
            raise AdmissionError("bad-reference", f"{loc}@{key}", value)
    if tag == "link":
        rel = attr_map.get("rel", "").lower().split()
        if "stylesheet" not in rel:
            raise AdmissionError("unsupported-link", loc, "only rel=stylesheet links are admitted")
        if "href" not in attr_map:
            raise AdmissionError("missing-reference", loc, "stylesheet link requires href")
    if tag == "img" and "src" not in attr_map:
        raise AdmissionError("missing-reference", loc, "img requires src")
    return refs


def _css_refs(path: str, rules: tuple[CssRule, ...]) -> list[tuple[str, None, str]]:
    refs: list[tuple[str, None, str]] = []
    for rule in rules:
        # Declaration order is admitted as irrelevant, so edge discovery must
        # not depend on the source ordering of declarations.
        for prop, value in sorted(rule.declarations):
            location = f"{path}:rule{rule.ordinal}:{prop}"
            for _start, _end, raw_target in _css_url_occurrences(value, location):
                target, fragment = _resolve_ref(path, raw_target, location)
                if fragment is not None or target is None:
                    raise AdmissionError("bad-css-reference", location, raw_target)
                refs.append((target, None, "css:url"))
    return refs


def _discover(root: str, resources: dict[str, dict[str, Any]]) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()

    def visit(path: str) -> None:
        if path in seen:
            return
        if path not in resources:
            raise AdmissionError("missing-resource", path, "referenced path not listed")
        seen.add(path)
        order.append(path)
        for target, _fragment, _slot in resources[path]["refs"]:
            visit(target)

    visit(root)
    if seen != set(resources):
        extras = sorted(set(resources) - seen)
        raise AdmissionError("unreachable-resource", "bundle.json", extras[0])
    return order


def _collect_names(resource_order: list[str], resources: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    id_seen: set[str] = set()
    classes: list[str] = []
    class_seen: set[str] = set()
    html_classes: set[str] = set()
    css_ids: set[str] = set()
    css_classes: set[str] = set()

    for path in resource_order:
        resource = resources[path]
        if resource["kind"] != "html":
            continue
        for event in resource["events"]:
            if event.kind != "start":
                continue
            _tag, attrs, _self_closing = event.data
            amap = dict(attrs)
            if "id" in amap:
                name = amap["id"]
                if name in id_seen:
                    raise AdmissionError("duplicate-id", f"{path}:{event.line}:{event.column}", name)
                id_seen.add(name)
                ids.append(name)
            if "class" in amap:
                names = amap["class"].split()
                unseen = [name for name in names if name not in class_seen]
                if len(unseen) > 1:
                    raise AdmissionError(
                        "unanchored-class-set",
                        f"{path}:{event.line}:{event.column}",
                        "at most one previously unseen class may appear at an ordered element anchor",
                    )
                for name in names:
                    html_classes.add(name)
                    if name not in class_seen:
                        class_seen.add(name)
                        classes.append(name)

    for path in resource_order:
        resource = resources[path]
        if resource["kind"] != "css":
            continue
        for rule in resource["rules"]:
            for selector in rule.selectors:
                for token in selector:
                    if token.startswith("#"):
                        css_ids.add(token[1:])
                    elif token.startswith("."):
                        css_classes.add(token[1:])
    if not css_ids.issubset(id_seen):
        missing = sorted(css_ids - id_seen)[0]
        raise AdmissionError("undeclared-id-selector", "css", missing)
    if not css_classes.issubset(html_classes):
        missing = sorted(css_classes - html_classes)[0]
        raise AdmissionError("undeclared-class-selector", "css", missing)
    return ids, classes


def _canon_ref(current_path: str, raw: str, resource_ids: dict[str, str], id_ids: dict[str, str], location: str) -> dict[str, Any]:
    target, fragment = _resolve_ref(current_path, raw, location)
    out: dict[str, Any] = {}
    if target is not None:
        out["resource"] = resource_ids[target]
    else:
        out["resource"] = resource_ids[current_path]
    if fragment is not None:
        if fragment not in id_ids:
            raise AdmissionError("unknown-fragment", location, fragment)
        out["fragment"] = id_ids[fragment]
    return out


def _canon_html(path: str, events: list[HtmlEvent], resource_ids: dict[str, str], id_ids: dict[str, str], class_ids: dict[str, str]) -> list[Any]:
    result: list[Any] = []
    for event in events:
        if event.kind == "doctype":
            result.append(["doctype", "html"])
        elif event.kind == "start":
            tag, attrs, self_closing = event.data
            normalized_attrs: list[Any] = []
            for key, value in sorted(attrs):
                loc = f"{path}:{event.line}:{event.column}@{key}"
                if key == "id":
                    normalized_attrs.append([key, ["id", id_ids[value]]])
                elif key == "class":
                    normalized_attrs.append([key, ["classes", sorted(class_ids[n] for n in value.split())]])
                elif key in limits.REFERENCE_ATTRS:
                    normalized_attrs.append([key, ["ref", _canon_ref(path, value, resource_ids, id_ids, loc)]])
                else:
                    normalized_attrs.append([key, ["literal", value]])
            result.append(["start", tag, normalized_attrs, bool(self_closing)])
        elif event.kind == "end":
            result.append(["end", event.data])
        elif event.kind == "text":
            result.append(["text", event.data])
        else:
            raise AssertionError(event.kind)
    return result


def _canon_selector(selector: tuple[str, ...], id_ids: dict[str, str], class_ids: dict[str, str]) -> list[str]:
    out: list[str] = []
    for token in selector:
        if token.startswith("#"):
            out.append("#" + id_ids[token[1:]])
        elif token.startswith("."):
            out.append("." + class_ids[token[1:]])
        else:
            out.append(token)
    return out


def _canon_css(path: str, rules: tuple[CssRule, ...], resource_ids: dict[str, str], id_ids: dict[str, str], class_ids: dict[str, str]) -> list[Any]:
    result: list[Any] = []
    for rule in rules:
        selectors = sorted((_canon_selector(s, id_ids, class_ids) for s in rule.selectors), key=lambda x: json.dumps(x, ensure_ascii=False))
        declarations: list[Any] = []
        for prop, value in sorted(rule.declarations):
            location = f"{path}:rule{rule.ordinal}:{prop}"

            def replace(raw_target: str) -> str:
                target, fragment = _resolve_ref(path, raw_target, location)
                if target is None or fragment is not None:
                    raise AdmissionError("bad-css-reference", location, raw_target)
                return f"url(@{resource_ids[target]})"

            declarations.append([prop, _rewrite_css_urls(value, location, replace)])
        result.append(["rule", selectors, declarations])
    return result


def parse_bundle(root_dir: str | Path) -> ParsedBundle:
    supplied_root = Path(root_dir)
    try:
        root_stat = supplied_root.lstat()
    except OSError as exc:
        raise EnvironmentFailure("root-unavailable", ".", type(exc).__name__) from exc
    if stat.S_ISLNK(root_stat.st_mode):
        raise AdmissionError("symlink", ".", "bundle root may not be a symlink")
    if not stat.S_ISDIR(root_stat.st_mode):
        raise AdmissionError("not-directory", ".", "bundle root is not a directory")
    try:
        root_path = supplied_root.resolve()
    except (OSError, RuntimeError) as exc:
        raise EnvironmentFailure("root-unavailable", ".", type(exc).__name__) from exc
    # Absence observed by a successful inventory is structural. A later failed
    # stat/read is an environmental failure, not proof of language exclusion.
    if "bundle.json" not in {p.name for p in _directory_entries(root_path, root_path)}:
        raise AdmissionError("missing-manifest", "bundle.json", "absent from directory inventory")
    manifest_path = root_path / "bundle.json"
    manifest_stat = _regular_stat(manifest_path, "bundle.json")
    if manifest_stat.st_size > limits.MAX_TEXT_BYTES:
        raise AdmissionError("manifest-too-large", "bundle.json", str(manifest_stat.st_size))
    raw_manifest = _read_stable(manifest_path, "bundle.json", manifest_stat, limits.MAX_TEXT_BYTES)
    try:
        manifest = _strict_json_loads(raw_manifest, "bundle.json")
    except AdmissionError as exc:
        raise AdmissionError("bad-manifest", "bundle.json", exc.detail) from exc
    if not isinstance(manifest, dict) or set(manifest) != {"format", "root", "resources"}:
        raise AdmissionError("bad-manifest", "bundle.json", "expected exactly format, root, resources")
    if manifest["format"] != limits.FORMAT:
        raise AdmissionError("bad-format", "bundle.json", repr(manifest["format"]))
    root = _safe_manifest_path(manifest["root"], "bundle.json:root")
    raw_resources = manifest["resources"]
    if not isinstance(raw_resources, list) or not raw_resources or len(raw_resources) > limits.MAX_FILES:
        raise AdmissionError("bad-resource-list", "bundle.json", "resources must be a bounded nonempty list")
    listed = [_safe_manifest_path(v, f"bundle.json:resources[{i}]") for i, v in enumerate(raw_resources)]
    if len(listed) != len(set(listed)) or root not in listed:
        raise AdmissionError("bad-resource-list", "bundle.json", "duplicates or missing root")
    actual_files = _inventory(root_path)
    if actual_files != set(listed):
        missing = sorted(set(listed) - actual_files)
        extra = sorted(actual_files - set(listed))
        raise AdmissionError("manifest-file-mismatch", "bundle.json", f"missing={missing[:1]} extra={extra[:1]}")
    total = len(raw_manifest)
    resources: dict[str, dict[str, Any]] = {}
    html_events = css_rules = css_declarations = 0
    for rel in sorted(listed):
        file_path = root_path / rel
        file_stat = _regular_stat(file_path, rel)
        projected_total = total + file_stat.st_size
        if projected_total > limits.MAX_TOTAL_BYTES:
            raise AdmissionError("bundle-too-large", "bundle.json", str(projected_total))
        suffix = PurePosixPath(rel).suffix.lower()
        if suffix not in {".html", ".css", ".png", ".jpg", ".jpeg", ".gif"}:
            raise AdmissionError("unsupported-resource", rel, suffix)
        if suffix in {".html", ".css"} and file_stat.st_size > limits.MAX_TEXT_BYTES:
            raise AdmissionError("text-too-large", rel, str(file_stat.st_size))
        cap = limits.MAX_TOTAL_BYTES - total
        if suffix in {".html", ".css"}:
            cap = min(cap, limits.MAX_TEXT_BYTES)
        data = _read_stable(file_path, rel, file_stat, cap)
        total += len(data)
        if suffix in {".html", ".css"}:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AdmissionError("non-utf8", rel, str(exc)) from exc
            if suffix == ".html":
                parser = _HTMLCollector(rel)
                # Unexpected parser/program failures propagate; they must not
                # become certified structural admission failures.
                parser.feed(text)
                parser.close_checked()
                html_events += len(parser.events)
                if html_events > limits.MAX_EVENTS:
                    raise AdmissionError("too-many-events", "bundle.json", str(html_events))
                refs: list[tuple[str, str | None, str]] = []
                for event in parser.events:
                    if event.kind == "start":
                        tag, attrs, _self_closing = event.data
                        refs.extend(_attr_references(rel, tag, attrs, f"{rel}:{event.line}:{event.column}"))
                resources[rel] = {"kind": "html", "events": parser.events, "refs": refs, "bytes": data}
            else:
                rules = _parse_css(text, rel)
                css_rules += len(rules)
                css_declarations += sum(len(rule.declarations) for rule in rules)
                if css_rules > limits.MAX_RULES or css_declarations > limits.MAX_DECLARATIONS:
                    raise AdmissionError("too-much-css", "bundle.json", "bundle rule/declaration bound exceeded")
                refs = _css_refs(rel, rules)
                resources[rel] = {"kind": "css", "rules": rules, "refs": refs, "bytes": data}
        else:
            resources[rel] = {"kind": "asset", "refs": [], "bytes": data}
    if not root.endswith(".html"):
        raise AdmissionError("bad-root-type", "bundle.json:root", root)
    # IDs are intentionally bundle-global in this restricted model.  Record
    # their owning document so fragment references cannot silently point into a
    # different page.
    id_owner: dict[str, str] = {}
    for source, resource in resources.items():
        if resource["kind"] != "html":
            continue
        for event in resource["events"]:
            if event.kind != "start":
                continue
            _tag, attrs, _self_closing = event.data
            name = dict(attrs).get("id")
            if name is None:
                continue
            if name in id_owner:
                raise AdmissionError("duplicate-id", f"{source}:{event.line}:{event.column}", name)
            id_owner[name] = source
    # Type-check all resource edges after the complete inventory is available.
    for source, resource in resources.items():
        for target, fragment, edge_kind in resource["refs"]:
            if target not in resources:
                raise AdmissionError("missing-resource", source, target)
            target_kind = resources[target]["kind"]
            if edge_kind == "link:href":
                if target_kind != "css" or fragment is not None:
                    raise AdmissionError("reference-type", source, f"stylesheet->{target}")
            elif edge_kind == "a:href":
                if target_kind != "html":
                    raise AdmissionError("reference-type", source, f"anchor->{target}")
            elif edge_kind == "img:src":
                if target_kind != "asset" or fragment is not None:
                    raise AdmissionError("reference-type", source, f"image->{target}")
            elif edge_kind == "css:url":
                if target_kind != "asset" or fragment is not None:
                    raise AdmissionError("reference-type", source, f"css-url->{target}")
            else:
                raise AdmissionError("reference-type", source, f"unsupported edge {edge_kind}")
            if fragment is not None and id_owner.get(fragment) != target:
                raise AdmissionError("fragment-target", source, f"{target}#{fragment}")
    resource_order = _discover(root, resources)
    resource_ids = {path: f"r{i}" for i, path in enumerate(resource_order)}
    id_order, class_order = _collect_names(resource_order, resources)
    id_ids = {name: f"i{i}" for i, name in enumerate(id_order)}
    class_ids = {name: f"c{i}" for i, name in enumerate(class_order)}
    canonical_resources: list[Any] = []
    for path in resource_order:
        resource = resources[path]
        if resource["kind"] == "html":
            body = _canon_html(path, resource["events"], resource_ids, id_ids, class_ids)
        elif resource["kind"] == "css":
            body = _canon_css(path, resource["rules"], resource_ids, id_ids, class_ids)
        else:
            # Exact bytes, not only a digest, keep the canonical-form theorem
            # information-theoretic.  Endpoint digests remain a compact binding
            # convenience for certificates, while positive replay compares bytes.
            body = {"encoding": "base64", "data": base64.b64encode(resource["bytes"]).decode("ascii")}
        canonical_resources.append({"id": resource_ids[path], "kind": resource["kind"], "body": body})
    canonical_obj = {"format": limits.FORMAT, "root": resource_ids[root], "resources": canonical_resources}
    canonical_bytes = json.dumps(canonical_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return ParsedBundle(root_path, root, resources, resource_order, resource_ids, id_order, id_ids, class_order, class_ids, canonical_obj, canonical_bytes)


def canonical_digest(bundle: ParsedBundle) -> str:
    return sha256(bundle.canonical_bytes).hexdigest()


def first_mismatch(left: ParsedBundle, right: ParsedBundle) -> dict[str, Any] | None:
    """Bounded, injective UTF-8 byte comparison; no Unicode line splitting.

    Exact asset bytes remain in canonical records, reversibly base64 encoded.
    The witness carries only the first byte difference (or EOF) and lengths;
    the checker reconstructs the full records instead of trusting digests.
    """
    a, b = left.canonical_bytes, right.canonical_bytes
    if a == b:
        return None
    end = min(len(a), len(b))
    offset = 0
    while offset < end and a[offset] == b[offset]:
        offset += 1
    return {"offset": offset, "left": a[offset] if offset < len(a) else None,
            "right": b[offset] if offset < len(b) else None,
            "left_length": len(a), "right_length": len(b)}


def make_certificate(left_dir: str | Path, right_dir: str | Path) -> dict[str, Any]:
    try:
        left = parse_bundle(left_dir)
    except AdmissionError as exc:
        return {"format": "iwb-cert-1", "decision": "out-of-language", "side": "left", "witness": exc.as_dict()}
    try:
        right = parse_bundle(right_dir)
    except AdmissionError as exc:
        return {"format": "iwb-cert-1", "decision": "out-of-language", "side": "right", "witness": exc.as_dict()}
    if left.canonical_obj == right.canonical_obj:
        resource_map = {lp: rp for lp, rp in zip(left.resource_order, right.resource_order)}
        id_map = {ln: rn for ln, rn in zip(left.id_order, right.id_order)}
        class_map = {ln: rn for ln, rn in zip(left.class_order, right.class_order)}
        return {
            "format": "iwb-cert-1",
            "decision": "equivalent",
            "resource_map": resource_map,
            "id_map": id_map,
            "class_map": class_map,
            "left_digest": canonical_digest(left),
            "right_digest": canonical_digest(right),
        }
    return {
        "format": "iwb-cert-1",
        "decision": "different",
        "witness": first_mismatch(left, right),
        "left_digest": canonical_digest(left),
        "right_digest": canonical_digest(right),
    }
