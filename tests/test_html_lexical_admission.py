"""Ordinary closing-token admission and the declared nominal restrictions.

Inputs are small owned publication examples, not browser or security tests.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest

from src import checker_core as checker, producer_core as producer, limits
from src.output_paths import write_text_exclusive


CORES = (producer, checker)


def document(body: str = "<p>Reading notes</p>") -> str:
    return ("<!doctype html><html><head><title>Library</title></head><body>"
            + body + "</body></html>")


class HtmlLexicalAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="iwb-lexical-"))
        self.serial = 0

    def bundle(self, text: str, child: str | None = None) -> Path:
        self.serial += 1
        path = self.root / str(self.serial)
        path.mkdir()
        files = {"index.html": text}
        if child is not None:
            files["child.html"] = child
        for name, source in files.items():
            write_text_exclusive(path / name, source)
        write_text_exclusive(path / "bundle.json", json.dumps({
            "format": "iwb-1", "root": "index.html", "resources": list(files),
        }))
        return path

    def rejected(self, path: Path, code: str):
        errors = []
        for core in CORES:
            with self.assertRaises(core.AdmissionError, msg=core.__name__) as raised:
                core.parse_bundle(path)
            self.assertEqual(raised.exception.code, code, core.__name__)
            errors.append(raised.exception.as_dict())
        self.assertEqual(errors[0], errors[1])
        return errors[0]

    def test_canonical_closing_tags_for_every_nonvoid_tag(self):
        tags = sorted(limits.ALLOWED_TAGS - limits.VOID_TAGS
                      - {"html", "head", "body", "title"})
        path = self.bundle(document("".join(f"<{tag}>Notes</{tag}>" for tag in tags)))
        for core in CORES:
            parsed = core.parse_bundle(path)
            ends = {event.data for event in parsed.resources["index.html"]["events"]
                    if event.kind == "end"}
            self.assertEqual(ends, limits.ALLOWED_TAGS - limits.VOID_TAGS)

    def test_ascii_whitespace_and_case_fold_preserve_records(self):
        left = self.bundle(document())
        canonical = producer.parse_bundle(left).canonical_bytes
        for whitespace in ("", " ", "\t", "\n", "\r\n", "\f", " \t\r\n\f"):
            with self.subTest(whitespace=repr(whitespace)):
                text = re.sub(r"</([a-z]+)>",
                              lambda m: "</" + m[1].upper() + whitespace + ">",
                              document())
                right = self.bundle(text)
                for core in CORES:
                    self.assertEqual(core.parse_bundle(right).canonical_bytes, canonical)
                cert = producer.make_certificate(left, right)
                self.assertEqual(cert["decision"], "equivalent")
                self.assertTrue(checker.verify_certificate(left, right, cert)["accepted"])

    def test_end_tag_metadata_is_rejected_not_discarded(self):
        # Even an attribute admitted on a start tag has no end-tag meaning.
        for tail in (' title="Notes"', " title=Notes", ' id="note"',
                     ' class="entry"', ' data-note="draft"', " title",
                     ' title="draft > final"', ' title="unfinished'):
            with self.subTest(tail=tail):
                self.rejected(self.bundle(document().replace("</p>", "</p" + tail + ">")),
                              "bad-end-tag")

    def test_malformed_delimiters_and_incomplete_closures_are_rejected(self):
        for closing in ("</p/>", "</p />", "</ p>", "</>", "</p!>",
                        "</p\u00a0>", "</p\v>", "</p\x00>"):
            with self.subTest(closing=repr(closing)):
                self.rejected(self.bundle(document().replace("</p>", closing)), "bad-end-tag")
        for suffix in ("</", "</p", "</p ", '</p title="Notes"'):
            with self.subTest(suffix=suffix):
                self.rejected(self.bundle(document().split("</p>", 1)[0] + suffix),
                              "bad-end-tag")
        self.rejected(self.bundle(document().replace("</p>", "</span>")), "unbalanced-html")
        self.rejected(self.bundle(document("<br></br>")), "void-end-tag")

    def test_token_like_literal_text_and_comments_are_not_scanned_as_tags(self):
        text = document('<p title="</p title=Notes>">Reading &lt;/p&gt;'
                        '<!-- </p title="Notes"> --></p>')
        path = self.bundle(text)
        for core in CORES:
            events = core.parse_bundle(path).resources["index.html"]["events"]
            self.assertIn("Reading </p>", [e.data for e in events if e.kind == "text"])
            attrs = [dict(e.data[1]) for e in events if e.kind == "start" and e.data[0] == "p"]
            self.assertEqual(attrs, [{"title": "</p title=Notes>"}])

    def test_chunk_boundaries_do_not_change_closing_token_admission(self):
        valid = document().replace("</p>", "</P \t>")
        invalid = document().replace("</p>", '</p title="Notes">')
        for core in CORES:
            expected = core._HTMLCollector("index.html")
            expected.feed(valid)
            expected.close_checked()
            start = valid.index("</P")
            for split in range(start + 1, valid.index(">", start) + 1):
                parser = core._HTMLCollector("index.html")
                parser.feed(valid[:split])
                parser.feed(valid[split:])
                parser.close_checked()
                self.assertEqual(parser.events, expected.events)
            start = invalid.index("</p")
            for split in range(start + 1, invalid.index(">", start) + 1):
                parser = core._HTMLCollector("index.html")
                with self.assertRaises(core.AdmissionError) as raised:
                    parser.feed(invalid[:split])
                    parser.feed(invalid[split:])
                    parser.close_checked()
                self.assertEqual(raised.exception.code, "bad-end-tag")

    def test_lexical_exclusion_has_a_stable_location_and_admission_witness(self):
        left = self.bundle(document())
        text = '<!doctype html>\n<html><head><title>Library</title></head><body>\n<p>Notes</p title="draft">\n</body></html>'
        right = self.bundle(text)
        error = self.rejected(right, "bad-end-tag")
        self.assertEqual(error["location"], "index.html:3:9")
        self.assertEqual(error["detail"], "expected </name> with optional trailing ASCII whitespace")
        for first, second, side in ((left, right, "right"), (right, left, "left")):
            cert = producer.make_certificate(first, second)
            self.assertEqual((cert["decision"], cert["side"], cert["witness"]),
                             ("out-of-language", side, error))
            self.assertTrue(checker.verify_certificate(first, second, cert)["accepted"])
        positive = producer.make_certificate(left, left)
        verdict = checker.verify_certificate(left, right, positive)
        self.assertFalse(verdict["accepted"])
        self.assertEqual(verdict["reason"], "endpoint-out-of-language:bad-end-tag")

    def test_multiclass_sets_are_admitted_when_introductions_are_anchored(self):
        left = self.bundle(document('<div class="a">A</div><div class="a b">B</div>'))
        right = self.bundle(document('<div class="x">A</div><div class="y x">B</div>'))
        cert = producer.make_certificate(left, right)
        self.assertEqual(cert["decision"], "equivalent")
        self.assertTrue(checker.verify_certificate(left, right, cert)["accepted"])
        self.rejected(self.bundle(document('<div class="a b">A</div>')), "unanchored-class-set")

    def test_id_uniqueness_is_bundle_global_and_fragments_remain_document_typed(self):
        root = document('<p id="root">Root</p><a href="child.html#note">Child</a>')
        valid = self.bundle(root, document('<p id="note">Child</p>'))
        self.assertTrue(checker.verify_certificate(valid, valid,
                                                  producer.make_certificate(valid, valid))["accepted"])
        self.rejected(self.bundle(root, document('<p id="root">Child</p>')), "duplicate-id")
        self.rejected(self.bundle(root.replace("child.html#note", "child.html#root"),
                                  document('<p id="note">Child</p>')), "fragment-target")


if __name__ == "__main__":
    unittest.main()
