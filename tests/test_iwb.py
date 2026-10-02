from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src import limits
from src.baselines import local_alpha_equal
from src.checker_core import verify_certificate
from src.exact_oracle import exact_equivalent
from src.fixture_factory import emit_bundle, emit_global_coupling_pair
from src.producer_core import AdmissionError, make_certificate, parse_bundle
from src.stress_factory import emit_stress_bundle
from src.tiny_fixtures import emit_tiny_bundle, emit_tiny_css_bundle


ARTIFACT = Path(__file__).resolve().parents[1]


class CertificateTests(unittest.TestCase):
    def test_all_declared_variant_kinds(self):
        base = ARTIFACT / "fixtures/owned/fixture-00"
        expected = {
            "all-orderings": "equivalent", "attribute-order": "equivalent",
            "class-alpha": "equivalent", "class-token-order": "equivalent",
            "combined-all": "equivalent", "declaration-order": "equivalent",
            "format-and-comments": "equivalent", "id-alpha": "equivalent",
            "path-move": "equivalent", "path-rename": "equivalent",
            "paths-and-names": "equivalent", "selector-list-order": "equivalent",
            "changed-asset": "different", "changed-css-value": "different",
            "changed-selector": "different", "changed-text": "different",
            "ordered-sibling-swap": "different", "broken-reference": "out-of-language",
            "duplicate-id": "out-of-language", "forbidden-form": "out-of-language",
        }
        for name, decision in expected.items():
            with self.subTest(name=name):
                target = ARTIFACT / "fixtures/variants/fixture-00" / name
                cert = make_certificate(base, target)
                self.assertEqual(cert["decision"], decision)
                self.assertTrue(verify_certificate(base, target, cert)["accepted"])

    def test_certificates_are_deterministic(self):
        left = ARTIFACT / "fixtures/owned/fixture-01"
        right = ARTIFACT / "fixtures/variants/fixture-01/combined-all"
        self.assertEqual(make_certificate(left, right), make_certificate(left, right))

    def test_unknown_field_rejected(self):
        left = ARTIFACT / "fixtures/owned/fixture-00"
        right = ARTIFACT / "fixtures/variants/fixture-00/combined-all"
        cert = make_certificate(left, right); cert["extra"] = 1
        self.assertFalse(verify_certificate(left, right, cert)["accepted"])

    def test_wrong_digest_rejected(self):
        left = ARTIFACT / "fixtures/owned/fixture-00"
        right = ARTIFACT / "fixtures/variants/fixture-00/combined-all"
        cert = make_certificate(left, right); cert["left_digest"] = "0" * 64
        self.assertEqual(verify_certificate(left, right, cert)["reason"], "wrong-canonical-digest")

    def test_partial_map_rejected(self):
        left = ARTIFACT / "fixtures/owned/fixture-00"
        right = ARTIFACT / "fixtures/variants/fixture-00/combined-all"
        cert = make_certificate(left, right)
        del cert["class_map"][next(iter(cert["class_map"]))]
        self.assertFalse(verify_certificate(left, right, cert)["accepted"])

    def test_mismatch_witness_rejected_when_mutated(self):
        left = ARTIFACT / "fixtures/owned/fixture-00"
        right = ARTIFACT / "fixtures/variants/fixture-00/changed-text"
        cert = make_certificate(left, right); cert["witness"]["offset"] += 1
        self.assertFalse(verify_certificate(left, right, cert)["accepted"])

    def test_rejection_witness_exact(self):
        left = ARTIFACT / "fixtures/owned/fixture-00"
        right = ARTIFACT / "fixtures/variants/fixture-00/forbidden-form"
        cert = make_certificate(left, right); del cert["witness"]["detail"]
        self.assertFalse(verify_certificate(left, right, cert)["accepted"])


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="iwb-test-"))
        emit_bundle(self.temp / "base", 0)

    def tearDown(self):
        shutil.rmtree(self.temp)

    def _modify(self, relative: str, old: str, new: str) -> Path:
        target = self.temp / "case"
        shutil.copytree(self.temp / "base", target)
        p = target / relative
        p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
        return target

    def assertRejected(self, target: Path, code: str):
        with self.assertRaises(AdmissionError) as ctx:
            parse_bundle(target)
        self.assertEqual(ctx.exception.code, code)

    def test_external_reference(self):
        target = self._modify("index.html", "assets/dot.png", "https://example.invalid/x.png")
        self.assertRejected(target, "external-reference")

    def test_event_attribute(self):
        target = self._modify("index.html", '<main id="card" class="card">', '<main id="card" class="card" onclick="x()">')
        self.assertRejected(target, "forbidden-attribute")

    def test_style_attribute(self):
        target = self._modify("index.html", '<main id="card" class="card">', '<main id="card" class="card" style="color:red">')
        self.assertRejected(target, "forbidden-attribute")

    def test_script_tag(self):
        target = self._modify("index.html", "</main>", "<script>bad()</script></main>")
        self.assertRejected(target, "forbidden-tag")

    def test_missing_doctype(self):
        target = self._modify("index.html", "<!doctype html>\n", "")
        self.assertRejected(target, "missing-doctype")

    def test_reference_attribute_on_wrong_tag(self):
        target = self._modify(
            "index.html", '<main id="card" class="card">',
            '<main id="card" class="card" href="pages/details.html">'
        )
        self.assertRejected(target, "forbidden-attribute")

    def test_stylesheet_reference_type(self):
        target = self._modify("index.html", "styles/base.css", "pages/details.html")
        self.assertRejected(target, "reference-type")

    def test_image_reference_type(self):
        target = self._modify("index.html", "assets/dot.png", "pages/details.html")
        self.assertRejected(target, "reference-type")

    def test_anchor_reference_type(self):
        target = self._modify("index.html", "pages/details.html#details", "assets/dot.png")
        self.assertRejected(target, "reference-type")


    def test_fragment_must_belong_to_target_document(self):
        target = self._modify("index.html", "pages/details.html#details", "pages/details.html#title")
        self.assertRejected(target, "fragment-target")

    def test_css_at_rule(self):
        target = self._modify("styles/base.css", ".heading", "@media all {}\n.heading")
        self.assertRejected(target, "at-rule")

    def test_css_duplicate_property(self):
        target = self._modify("styles/base.css", "color: #234;", "color: #234;\n  color: #234;")
        self.assertRejected(target, "duplicate-property")

    def test_unanchored_class_set(self):
        target = self._modify("index.html", 'class="page"', 'class="new-a new-b"')
        self.assertRejected(target, "unanchored-class-set")

    def test_undeclared_css_class(self):
        target = self._modify("styles/base.css", ".card", ".not-declared")
        self.assertRejected(target, "undeclared-class-selector")

    def test_duplicate_manifest_key(self):
        target = self.temp / "case"; shutil.copytree(self.temp / "base", target)
        manifest = (target / "bundle.json").read_text()
        manifest = manifest.replace('{\n  "format"', '{\n  "format": "iwb-1",\n  "format"', 1)
        (target / "bundle.json").write_text(manifest)
        self.assertRejected(target, "bad-manifest")

    def test_extra_unlisted_file(self):
        target = self.temp / "case"; shutil.copytree(self.temp / "base", target)
        (target / "extra.txt").write_text("x")
        self.assertRejected(target, "manifest-file-mismatch")


    def test_self_closing_nonvoid_rejected(self):
        target = self._modify("index.html", '<main id="card" class="card">', '<main id="card" class="card"/>')
        self.assertRejected(target, "self-closing-nonvoid")

    def test_head_and_body_must_be_direct_ordered_children(self):
        target = self._modify("index.html", "<head>", "<div><head>")
        # The first modification alone leaves the document balanced only after
        # adding the matching close tag before body.
        p = target / "index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("</head>", "</head></div>", 1), encoding="utf-8")
        self.assertRejected(target, "bad-document-shape")

    def test_malformed_adjacent_type_selector_rejected(self):
        target = self._modify("styles/base.css", ".detail > .note", "div*")
        self.assertRejected(target, "unsupported-selector")

    def test_css_quoted_whitespace_is_not_collapsed(self):
        left = self.temp / "left"; right = self.temp / "right"
        shutil.copytree(self.temp / "base", left); shutil.copytree(self.temp / "base", right)
        for root, family in [(left, '"A  B"'), (right, '"A B"')]:
            css = root / "styles/base.css"
            css.write_text(css.read_text(encoding="utf-8") + f"\nbody {{ font-family: {family}; }}\n", encoding="utf-8")
        self.assertNotEqual(parse_bundle(left).canonical_bytes, parse_bundle(right).canonical_bytes)

    def test_css_url_text_inside_string_is_literal(self):
        left = self.temp / "left"; right = self.temp / "right"
        shutil.copytree(self.temp / "base", left); shutil.copytree(self.temp / "base", right)
        for root, literal in [(left, "ghost-a.png"), (right, "ghost-b.png")]:
            css = root / "styles/base.css"
            css.write_text(
                css.read_text(encoding="utf-8")
                + f'\nbody {{ font-family: "url({literal})"; }}\n',
                encoding="utf-8",
            )
        left_parsed = parse_bundle(left)
        right_parsed = parse_bundle(right)
        self.assertNotEqual(left_parsed.canonical_bytes, right_parsed.canonical_bytes)
        self.assertEqual(set(left_parsed.resources), {
            "index.html", "pages/details.html", "styles/base.css", "assets/dot.png"
        })

    def test_css_malformed_real_url_rejected(self):
        target = self._modify(
            "styles/base.css",
            'url("../assets/dot.png")',
            'url("../assets/dot.png" trailing)',
        )
        self.assertRejected(target, "bad-css-reference")

    def test_css_even_backslash_run_closes_quote(self):
        target = self.temp / "case"
        shutil.copytree(self.temp / "base", target)
        css = target / "styles/base.css"
        # The first closing quote is preceded by two backslashes.  It therefore
        # closes the string; the semicolon in the second string remains literal.
        css.write_text(
            css.read_text(encoding="utf-8")
            + '\nbody { font-family: "A\\\\", "B;C"; }\n',
            encoding="utf-8",
        )
        parsed = parse_bundle(target)
        self.assertIn(b'B;C', parsed.canonical_bytes)

    def test_css_odd_backslash_run_escapes_quote(self):
        target = self.temp / "case"
        shutil.copytree(self.temp / "base", target)
        css = target / "styles/base.css"
        css.write_text(
            css.read_text(encoding="utf-8")
            + '\nbody { font-family: "A\\\";B"; }\n',
            encoding="utf-8",
        )
        parsed = parse_bundle(target)
        self.assertIn(b';B', parsed.canonical_bytes)

    def test_root_symlink_rejected(self):
        link = self.temp / "root-link"
        link.symlink_to(self.temp / "base", target_is_directory=True)
        self.assertRejected(link, "symlink")

    def test_oversized_resource_rejected_from_metadata(self):
        target = self.temp / "case"
        shutil.copytree(self.temp / "base", target)
        huge = target / "assets/huge.png"
        with huge.open("wb") as handle:
            handle.truncate(limits.MAX_TOTAL_BYTES + 1)
        manifest_path = target / "bundle.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["resources"].append("assets/huge.png")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertRejected(target, "bundle-too-large")

    def test_literal_url_string_survives_positive_replay(self):
        left = self.temp / "left"; right = self.temp / "right"
        shutil.copytree(self.temp / "base", left); shutil.copytree(self.temp / "base", right)
        for root in (left, right):
            css = root / "styles/base.css"
            css.write_text(
                css.read_text(encoding="utf-8")
                + '\nbody { font-family: "url(not-a-resource.png)"; }\n',
                encoding="utf-8",
            )
        cert = make_certificate(left, right)
        self.assertEqual(cert["decision"], "equivalent")
        self.assertTrue(verify_certificate(left, right, cert)["accepted"])

    def test_asset_canonical_form_contains_exact_bytes(self):
        parsed = parse_bundle(self.temp / "base")
        assets = [r for r in parsed.canonical_obj["resources"] if r["kind"] == "asset"]
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["body"]["encoding"], "base64")
        self.assertIn("data", assets[0]["body"])
        self.assertNotIn("sha256", assets[0]["body"])

    def test_symlink_rejected(self):
        target = self.temp / "case"; shutil.copytree(self.temp / "base", target)
        (target / "extra-link").symlink_to(target / "index.html")
        self.assertRejected(target, "symlink")


class OracleAndAblationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="iwb-oracle-"))

    def tearDown(self):
        shutil.rmtree(self.temp)

    def test_tiny_exact_positive(self):
        emit_tiny_bundle(self.temp / "a", 2, 0); emit_tiny_bundle(self.temp / "b", 2, 7)
        self.assertTrue(exact_equivalent(self.temp / "a", self.temp / "b")[0])

    def test_tiny_exact_negative(self):
        emit_tiny_bundle(self.temp / "a", 2, 0); emit_tiny_bundle(self.temp / "b", 3, 7)
        self.assertFalse(exact_equivalent(self.temp / "a", self.temp / "b")[0])

    def test_tiny_css_exact_positive(self):
        emit_tiny_css_bundle(self.temp / "a", 1, 0); emit_tiny_css_bundle(self.temp / "b", 1, 7)
        self.assertTrue(exact_equivalent(self.temp / "a", self.temp / "b")[0])

    def test_tiny_css_exact_negative(self):
        emit_tiny_css_bundle(self.temp / "a", 1, 0); emit_tiny_css_bundle(self.temp / "b", 2, 7)
        self.assertFalse(exact_equivalent(self.temp / "a", self.temp / "b")[0])

    def test_canonical_agrees_with_oracle(self):
        for fa, fb in [(0, 0), (0, 1), (4, 4), (5, 7)]:
            emit_tiny_bundle(self.temp / "a", fa, 1); emit_tiny_bundle(self.temp / "b", fb, 6)
            exact = exact_equivalent(self.temp / "a", self.temp / "b")[0]
            canonical = parse_bundle(self.temp / "a").canonical_bytes == parse_bundle(self.temp / "b").canonical_bytes
            self.assertEqual(canonical, exact)

    def test_local_alpha_false_positive(self):
        left, right = emit_global_coupling_pair(self.temp / "coupling")
        self.assertTrue(local_alpha_equal(left, right))
        self.assertEqual(make_certificate(left, right)["decision"], "different")

    def test_small_stress_transform(self):
        emit_stress_bundle(self.temp / "a", pages=2, blocks_per_page=4, transformed=False)
        emit_stress_bundle(self.temp / "b", pages=2, blocks_per_page=4, transformed=True)
        cert = make_certificate(self.temp / "a", self.temp / "b")
        self.assertEqual(cert["decision"], "equivalent")
        self.assertTrue(verify_certificate(self.temp / "a", self.temp / "b", cert)["accepted"])

    def test_checker_has_no_producer_import(self):
        import ast
        source = (ARTIFACT / "src/checker_core.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any("producer_core" in name for name in imported))

    def test_oracle_has_no_checker_import(self):
        import ast
        source = (ARTIFACT / "src/exact_oracle.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any("checker_core" in name for name in imported))

    def test_css_reference_discovery_ignores_declaration_order(self):
        left = self.temp / "left"; right = self.temp / "right"
        emit_bundle(left, 0); shutil.copytree(left, right)
        for root in (left, right):
            (root / "assets/dot2.png").write_bytes(b"opaque-second-asset")
            manifest_path = root / "bundle.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["resources"].append("assets/dot2.png")
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        left_css = (left / "styles/base.css").read_text(encoding="utf-8")
        left_css = left_css.replace(
            '  background-image: url("../assets/dot.png");\n  background-color: #eef;',
            '  background-image: url("../assets/dot.png");\n  cursor: url("../assets/dot2.png");\n  background-color: #eef;'
        )
        (left / "styles/base.css").write_text(left_css, encoding="utf-8")
        right_css = (right / "styles/base.css").read_text(encoding="utf-8")
        right_css = right_css.replace(
            '  background-image: url("../assets/dot.png");\n  background-color: #eef;',
            '  cursor: url("../assets/dot2.png");\n  background-color: #eef;\n  background-image: url("../assets/dot.png");'
        )
        (right / "styles/base.css").write_text(right_css, encoding="utf-8")
        self.assertEqual(parse_bundle(left).canonical_bytes, parse_bundle(right).canonical_bytes)
        cert = make_certificate(left, right)
        self.assertEqual(cert["decision"], "equivalent")
        self.assertTrue(verify_certificate(left, right, cert)["accepted"])


class FixtureSafetyTests(unittest.TestCase):
    def test_owned_and_variants_parse_only(self):
        # Parsing itself enforces no scripts, forms, event handlers, external
        # URLs, active CSS, unknown files, or unreachable resources.
        for root in [ARTIFACT / "fixtures/owned", ARTIFACT / "fixtures/variants"]:
            for manifest in root.rglob("bundle.json"):
                bundle = manifest.parent
                try:
                    parse_bundle(bundle)
                except AdmissionError:
                    # Exactly the three intentionally rejected variants may fail.
                    self.assertIn(bundle.name, {"duplicate-id", "forbidden-form", "broken-reference"})


if __name__ == "__main__":
    unittest.main()
