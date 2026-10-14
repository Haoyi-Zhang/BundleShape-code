"""Owned, inert static fixtures exercise the scientific runner's admission gates."""
from pathlib import Path
import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ARTIFACT = Path(__file__).resolve().parents[1]


class ScientificGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="iwb-static-controls-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        (self.root / "src").mkdir()
        shutil.copy2(ARTIFACT / "static_assurance.py", self.root / "static_assurance.py")
        shutil.copy2(ARTIFACT / "src" / "output_paths.py", self.root / "src" / "output_paths.py")
        (self.root / "src" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "src" / "producer_core.py").write_text("marker = 1\n", encoding="utf-8")

    def audit(self, checker, optimized):
        (self.root / "src" / "checker_core.py").write_text(checker, encoding="utf-8")
        out = self.root / ("optimized" if optimized else "normal")
        command = [sys.executable, *(["-O"] if optimized else []), "-B",
                   str(self.root / "static_assurance.py"), "--out", str(out)]
        return subprocess.run(command, cwd=self.root, capture_output=True,
                              text=True, encoding="utf-8", timeout=15,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_imported_producer_is_rejected_in_both_modes(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.audit("import src.producer_core\nmarker = 1\n", optimized)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_import_from_alias_is_not_hidden_from_gate(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.audit("from src import producer_core\nmarker = 1\n", optimized)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_separate_literal_checker_passes_in_both_modes(self):
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                result = self.audit("marker = 2\n", optimized)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reproduction_help_is_available_without_posix_resource(self):
        result = subprocess.run([sys.executable, "-B", str(ARTIFACT / "reproduce.py"), "--help"],
                                cwd=ARTIFACT, capture_output=True, text=True,
                                encoding="utf-8", timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reproduction_comparison_preserves_json_field_types(self):
        actual, expected = self.root / 'actual', self.root / 'expected'
        actual.mkdir()
        expected.mkdir()
        for name in ('variant-results.csv', 'baseline-summary.csv', 'variant-summary.json',
                     'coupling-control.json', 'mutation-summary.json', 'combination-summary.json',
                     'oracle-summary.json', 'stress-summary.json', 'evaluation-summary.json'):
            for directory in (actual, expected):
                (directory / name).write_text('{}\n', encoding='utf-8')
        (expected / 'unit-summary.json').write_text(json.dumps({'successful': True, 'tests_run': 108}), encoding='utf-8')
        (actual / 'unit-summary.json').write_text(json.dumps({'successful': 1, 'tests_run': 108}), encoding='utf-8')
        result = subprocess.run([sys.executable, '-O', '-B', str(ARTIFACT / 'verify_results.py'),
                                 '--actual', str(actual), '--expected', str(expected)],
                                cwd=ARTIFACT, capture_output=True, text=True,
                                encoding='utf-8', timeout=15)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
