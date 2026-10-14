"""Owned publication tokens; no browser, network, or active payloads."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src import checker_core as checker, producer_core as producer
from src.output_paths import write_text_exclusive

CORES = (producer, checker)


def document(body: str) -> str:
    return ('<!doctype html><html><head><title>Notes</title></head><body>'
            + body + '</body></html>')


class HtmlStartTokenTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="iwb-start-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name).resolve()
        if not self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("owned temporary directory containment")
        self.serial = 0

    def bundle(self, body: str) -> Path:
        self.serial += 1
        root = self.root / str(self.serial)
        write_text_exclusive(root / "index.html", document(body))
        write_text_exclusive(root / "bundle.json", json.dumps({
            "format": "iwb-1", "root": "index.html", "resources": ["index.html"]}))
        return root

    def rejected(self, body: str, code="bad-start-tag"):
        root = self.bundle(body)
        records = []
        for core in CORES:
            with self.assertRaises(core.AdmissionError) as raised:
                core.parse_bundle(root)
            self.assertEqual(raised.exception.code, code)
            records.append(raised.exception.as_dict())
        self.assertEqual(records[0], records[1])
        return root, records[0]

    def test_stray_slashes_are_not_erased(self):
        for opening in ('<p / title="Notes">', '<p/title="Notes">',
                        '<p title="Notes"/ lang="en">', '<br //>'):
            self.rejected(opening + ('Notes</p>' if opening.startswith('<p') else ''))

    def test_attribute_separator_is_required(self):
        for opening in ('<p title="Notes"lang="en">',
                        "<p title='Notes'lang='en'>"):
            self.rejected(opening + 'Notes</p>')

    def test_unquoted_values_are_nonempty_and_lexically_bounded(self):
        for value in ('', 'Not`es', 'Not=es', 'Not"es', "Not'es", 'Not<es'):
            self.rejected('<p title=' + value + '>Notes</p>')

    def test_ordinary_value_forms_and_ascii_spaces_agree(self):
        baseline = self.bundle('<p title="Notes" lang="en">Notes</p><br>')
        expected = producer.parse_bundle(baseline).canonical_bytes
        for space in (' ', '\t', '\n', '\r\n', '\f'):
            for value in ('Notes', '"Notes"', "'Notes'"):
                body = ('<P' + space + 'TITLE' + space + '=' + space + value
                        + space + 'LANG=en>Notes</P><BR />')
                root = self.bundle(body)
                for core in CORES:
                    self.assertEqual(core.parse_bundle(root).canonical_bytes, expected)
                certificate = producer.make_certificate(baseline, root)
                self.assertEqual(certificate['decision'], 'equivalent')
                self.assertTrue(checker.verify_certificate(baseline, root, certificate)['accepted'])

    def test_quoted_delimiters_and_unquoted_slash_are_literal(self):
        root = self.bundle('<p title="a > b / c = d ` e">Notes</p><br title=Notes/>')
        for core in CORES:
            parsed = core.parse_bundle(root)
            attrs = {e.data[0]: dict(e.data[1]) for e in parsed.resources['index.html']['events']
                     if e.kind == 'start' and e.data[0] in {'p', 'br'}}
            self.assertEqual(attrs, {'p': {'title': 'a > b / c = d ` e'},
                                     'br': {'title': 'Notes/'}})
        # Quoting changes where '/' belongs; it must not disappear from a value.
        plain = self.bundle('<p title="a > b / c = d ` e">Notes</p><br title="Notes"/>')
        certificate = producer.make_certificate(root, plain)
        self.assertEqual(certificate['decision'], 'different')
        self.assertTrue(checker.verify_certificate(root, plain, certificate)['accepted'])

    def test_existing_attribute_and_selfclosing_guards_remain(self):
        for body, code in (('<p title>Notes</p>', 'valueless-attribute'),
                           ('<p title="A" title="B">Notes</p>', 'duplicate-attribute'),
                           ('<p unknown="Notes">Notes</p>', 'forbidden-attribute'),
                           ('<p/>', 'self-closing-nonvoid')):
            self.rejected(body, code)

    def test_chunked_tokens_and_incomplete_eof_match(self):
        texts = (document('<p title="Notes" lang=en>Notes</p>'),
                 document('<p title="Notes"lang=en>Notes</p>'),
                 document('<p>Notes</p>') + '<p title="Notes"',
                 document('<p>Notes</p>') + '<p')
        for core in CORES:
            for text in texts:
                results = []
                for chunks in ([text], list(text)):
                    parser = core._HTMLCollector('index.html')
                    try:
                        for chunk in chunks:
                            parser.feed(chunk)
                        parser.close_checked()
                        results.append(('admitted', parser.events))
                    except core.AdmissionError as exc:
                        results.append(('excluded', exc.as_dict()))
                self.assertEqual(results[0], results[1])
                if text != texts[0]:
                    self.assertEqual(results[0][1]['code'], 'bad-start-tag')

    def test_public_certificate_boundary_has_exact_lexical_witness(self):
        valid = self.bundle('<p title="Notes">Notes</p>')
        invalid, error = self.rejected('<p / title="Notes">Notes</p>')
        for left, right, side in ((valid, invalid, 'right'), (invalid, valid, 'left')):
            certificate = producer.make_certificate(left, right)
            self.assertEqual((certificate['decision'], certificate['side'], certificate['witness']),
                             ('out-of-language', side, error))
            self.assertTrue(checker.verify_certificate(left, right, certificate)['accepted'])
        positive = producer.make_certificate(valid, valid)
        result = checker.verify_certificate(valid, invalid, positive)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'endpoint-out-of-language:bad-start-tag')


if __name__ == '__main__':
    unittest.main()
