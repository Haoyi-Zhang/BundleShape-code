"""Owned publication entry names use the same kind rules as other resources."""
import json
from pathlib import Path
import tempfile
import unittest

from src import checker_core as checker,producer_core as producer
from src.output_paths import write_text_exclusive

class RootKindTests(unittest.TestCase):
    def setUp(self):
        self.workspace=tempfile.TemporaryDirectory(prefix='iwb-root-kind-')
        self.addCleanup(self.workspace.cleanup)
        self.root=Path(self.workspace.name).resolve()
        if not self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError('owned temporary directory containment')

    def emit(self,folder,entry):
        root=self.root/folder
        document='<!doctype html><html><head><title>Notes</title></head><body><p>Notes</p></body></html>'
        write_text_exclusive(root/entry,document if entry.lower().endswith('.html') else '')
        write_text_exclusive(root/'bundle.json',json.dumps({'format':'iwb-1','root':entry,'resources':[entry]}))
        return root

    def test_uppercase_html_entry_preserves_canonical_form(self):
        lower=self.emit('lower','index.html')
        upper=self.emit('upper','Index.HTML')
        for core in (producer,checker):
            self.assertEqual(core.parse_bundle(lower).canonical_bytes,core.parse_bundle(upper).canonical_bytes)
        certificate=producer.make_certificate(lower,upper)
        self.assertEqual(certificate['decision'],'equivalent')
        self.assertEqual(certificate['resource_map'],{'index.html':'Index.HTML'})
        self.assertTrue(checker.verify_certificate(lower,upper,certificate)['accepted'])

    def test_mixed_case_html_entry_has_the_existing_html_kind(self):
        root=self.emit('mixed','Notes.HtMl')
        for core in (producer,checker):
            parsed=core.parse_bundle(root)
            self.assertEqual(parsed.resources[parsed.root]['kind'],'html')

    def test_css_entry_is_still_excluded_by_kind(self):
        root=self.emit('css','Notes.CSS')
        for core in (producer,checker):
            with self.assertRaises(core.AdmissionError) as raised:
                core.parse_bundle(root)
            self.assertEqual(raised.exception.code,'bad-root-type')

if __name__=='__main__':
    unittest.main(verbosity=2)
