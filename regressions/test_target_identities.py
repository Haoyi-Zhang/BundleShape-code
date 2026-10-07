"""Owned finite specification oracle; no historical code, timing or cleanup."""
from __future__ import annotations

import copy
import itertools
import json
import posixpath
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import producer_core as producer, checker_core as checker


def emit_case(destination, variant=0, mutation="none"):
    """Emit two HTML, two CSS and one opaque asset, with a typed specification.

    The oracle below consumes this specification, not either production parser.
    It concerns these fixed templates only, not arbitrary HTML/CSS admission.
    """
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    paths = (("index.html", "child.html", "a.css", "b.css", "x.png")
             if variant < 2 else
             ("site/home.html", "docs/info.html", "css/two.css", "css/one.css", "media/mark.png"))
    ids = ("one", "two") if variant % 2 == 0 else ("left", "right")
    classes = ("a", "b") if variant % 2 == 0 else ("x", "y")
    p0, p1, c0, c1, asset = paths
    i0, i1 = ids
    a, b = classes
    child_a, child_b = (b, a) if mutation == "coupling" else (a, b)
    text = "alpha\u2028z" + ("!" if mutation == "text" else "")
    raw_asset = b"opaque-owned" + (b"!" if mutation == "asset" else b"")

    def ref(source, target, fragment=None):
        value = posixpath.relpath(target, posixpath.dirname(source) or ".")
        return value + ("#" + fragment if fragment else "")

    def attrs(items):
        ordered = list(reversed(items)) if variant % 2 else items
        return " ".join(f'{key}="{value}"' for key, value in ordered)

    def page(path, body):
        links = "".join('<link ' + attrs([("rel", "stylesheet"), ("href", ref(path, css))]) + '>'
                        for css in (c0, c1))
        return '<!doctype html><html><head><title>owned</title>' + links + '</head>' + body + '</html>'

    files = {
        p0: page(p0, f'<body class="{a}"><p ' + attrs([("id", i0), ("class", b)]) + '>' + text + '</p>'
                 + '<a href="' + ref(p0, p1, i1) + '">child</a><img src="' + ref(p0, asset) + '" alt="owned"></body>'),
        p1: page(p1, f'<body class="{child_a}"><p ' + attrs([("id", i1), ("class", child_b)]) + '>beta</p></body>'),
        c0: (f'.{b},#{i0}' if variant % 2 else f'#{i0},.{b}') + '{color:red}',
        c1: f'.{a}' + '{background-image:url("' + ref(c1, asset) + '");color:blue}',
        asset: raw_asset,
    }
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    (root / "bundle.json").write_text(json.dumps({"format": "iwb-1", "root": p0,
                                                 "resources": list(reversed(paths)) if variant % 2 else list(paths)}),
                                      encoding="utf-8")
    R = lambda path: ("R", path)
    I = lambda name: ("I", name)
    C = lambda name: ("C", name)
    records = {
        p0: ("html", (R(c0), R(c1), C(a), I(i0), C(b), text, (R(p1), I(i1)), R(asset))),
        p1: ("html", (R(c0), R(c1), C(child_a), I(i1), C(child_b), "beta")),
        c0: ("css", (frozenset((I(i0), C(b))), "red")),
        c1: ("css", (C(a), R(asset), "blue")),
        asset: ("asset", raw_asset),
    }
    return {"path": root, "root": p0, "ids": ids, "classes": classes, "records": records}


def reference_matches(left, right, rmap, imap, cmap):
    """Direct typed-occurrence substitution under one global total mapping."""
    def substitute(value):
        if isinstance(value, tuple):
            if len(value) == 2 and value[0] in ("R", "I", "C"):
                return value[0], {"R": rmap, "I": imap, "C": cmap}[value[0]][value[1]]
            return tuple(substitute(part) for part in value)
        if isinstance(value, frozenset):
            return frozenset(substitute(part) for part in value)
        return value
    return (rmap[left["root"]] == right["root"] and
            all(substitute(record) == right["records"][rmap[path]]
                for path, record in left["records"].items()))


def reference_equivalent(left, right):
    """Finite enumeration, without canonical labels, digest or checker helpers."""
    source = tuple(left["records"])
    for targets in itertools.permutations(right["records"]):
        rmap = dict(zip(source, targets))
        if rmap[left["root"]] != right["root"]:
            continue
        if any(left["records"][s][0] != right["records"][t][0] for s, t in rmap.items()):
            continue
        for ids in itertools.permutations(right["ids"]):
            for classes in itertools.permutations(right["classes"]):
                if reference_matches(left, right, rmap, dict(zip(left["ids"], ids)),
                                     dict(zip(left["classes"], classes))):
                    return True
    return False


class TargetIdentityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="iwb-identities-"))

    def pair(self):
        return emit_case(self.root / "left"), emit_case(self.root / "right", 3)

    def test_specification_cartesian_oracle(self):
        cases = [emit_case(self.root / str(v) / m, v, m)
                 for v in range(4) for m in ("none", "text", "coupling", "asset")]
        for left, right in itertools.product(cases, repeat=2):
            cert = producer.make_certificate(left["path"], right["path"])
            exact = reference_equivalent(left, right)
            self.assertEqual(cert["decision"], "equivalent" if exact else "different")
            self.assertTrue(checker.verify_certificate(left["path"], right["path"], cert)["accepted"])

    def test_reuses_read_only_identities_only_within_one_replay(self):
        left, right = self.pair()
        cert = producer.make_certificate(left["path"], right["path"])
        original_cert = copy.deepcopy(cert)
        seen = []
        def probe(original):
            def wrapped(*args):
                identities = args[-1]
                snapshot = copy.deepcopy(identities)
                seen.append(identities)
                result = original(*args)
                self.assertEqual(identities, snapshot)
                return result
            return wrapped
        with patch.object(checker, "_match_html", probe(checker._match_html)), \
             patch.object(checker, "_match_css", probe(checker._match_css)):
            for _ in range(2):
                self.assertTrue(checker.verify_certificate(left["path"], right["path"], cert)["accepted"])
        self.assertEqual(len(seen), 8)  # two HTML + two CSS, per invocation
        self.assertTrue(all(item is seen[0] for item in seen[:4]))
        self.assertTrue(all(item is seen[4] for item in seen[4:]))
        self.assertIsNot(seen[0], seen[4])
        self.assertEqual(seen[0], tuple({v: v for v in cert[key].values()}
                                      for key in ("resource_map", "id_map", "class_map")))
        self.assertEqual(cert, original_cert)

    def test_validation_order_before_any_matcher(self):
        left, right = self.pair()
        cert = producer.make_certificate(left["path"], right["path"])
        cases = []
        bad = copy.deepcopy(cert); bad["left_digest"] = "0" * 64; bad["resource_map"] = None
        cases.append((bad, "wrong-canonical-digest"))
        for label in ("resource_map", "id_map", "class_map"):
            bad = copy.deepcopy(cert); bad[label] = {}
            cases.append((bad, "bad-certificate-map:" + label))
        bad = copy.deepcopy(cert)
        rm = bad["resource_map"]; keys = list(left["records"])[:2]
        rm[keys[0]], rm[keys[1]] = rm[keys[1]], rm[keys[0]]
        cases.append((bad, "bad-certificate-map:resource_map"))
        with patch.object(checker, "_match_html", side_effect=AssertionError("premature HTML replay")), \
             patch.object(checker, "_match_css", side_effect=AssertionError("premature CSS replay")):
            for bad, reason in cases:
                self.assertEqual(checker.verify_certificate(left["path"], right["path"], bad),
                                 {"accepted": False, "decision": "equivalent", "reason": reason})

    def test_all_total_maps_against_specification(self):
        left, right = self.pair()
        cert = producer.make_certificate(left["path"], right["path"])
        for paths in itertools.permutations(right["records"]):
            for ids in itertools.permutations(right["ids"]):
                for classes in itertools.permutations(right["classes"]):
                    bad = copy.deepcopy(cert)
                    bad["resource_map"] = dict(zip(left["records"], paths))
                    bad["id_map"] = dict(zip(left["ids"], ids))
                    bad["class_map"] = dict(zip(left["classes"], classes))
                    expected = reference_matches(left, right, bad["resource_map"], bad["id_map"], bad["class_map"])
                    self.assertEqual(checker.verify_certificate(left["path"], right["path"], bad)["accepted"], expected)

    def test_negative_byte_witness_and_strict_types(self):
        left = emit_case(self.root / "left")
        right = emit_case(self.root / "right", 3, "text")
        cert = producer.make_certificate(left["path"], right["path"])
        a = producer.parse_bundle(left["path"]).canonical_bytes
        b = producer.parse_bundle(right["path"]).canonical_bytes
        offset = next(i for i in range(min(len(a), len(b))) if a[i] != b[i])
        self.assertEqual(cert["witness"], {"offset": offset, "left": a[offset], "right": b[offset],
                                          "left_length": len(a), "right_length": len(b)})
        for value in (True, float(offset), offset + 1):
            bad = copy.deepcopy(cert); bad["witness"]["offset"] = value
            self.assertFalse(checker.verify_certificate(left["path"], right["path"], bad)["accepted"])

    def test_empty_symbol_maps(self):
        paths = []
        for name in ("left", "right"):
            path = self.root / name; path.mkdir(); paths.append(path)
            (path / "bundle.json").write_text(json.dumps({"format": "iwb-1", "root": "index.html",
                                                          "resources": ["index.html"]}), encoding="utf-8")
            (path / "index.html").write_text('<!doctype html><html><head><title>t</title></head><body><p>t</p></body></html>',
                                             encoding="utf-8")
        cert = producer.make_certificate(*paths)
        self.assertEqual((cert["id_map"], cert["class_map"]), ({}, {}))
        self.assertTrue(checker.verify_certificate(*paths, cert)["accepted"])


if __name__ == "__main__":
    unittest.main()
