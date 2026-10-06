"""Supplemental regressions, separate from the frozen 84-test measurement."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src import producer_core, checker_core
from src.fixture_factory import emit_bundle, emit_owned_suite, emit_variant_suite, emit_global_coupling_pair
from src.tiny_fixtures import emit_tiny_bundle, emit_tiny_suite, emit_tiny_css_bundle, emit_tiny_css_suite
from src.stress_factory import emit_stress_bundle
from src.output_paths import fresh_directory, write_text_exclusive


class ScientificRepairs(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="iwb-supplemental-"))
        # Preserve these tiny cases for inspection; no deletion is necessary.

    def test_generators_refuse_nonempty_destinations(self):
        functions = [
            lambda p: emit_bundle(p, 0), lambda p: emit_owned_suite(p, 1),
            lambda p: emit_variant_suite(self.root / "unused", p, 1),
            emit_global_coupling_pair,
            lambda p: emit_tiny_bundle(p, 0, 0), lambda p: emit_tiny_suite(p, 1, 1),
            lambda p: emit_tiny_css_bundle(p, 0, 0), lambda p: emit_tiny_css_suite(p, 1, 1),
            lambda p: emit_stress_bundle(p, pages=2, blocks_per_page=2),
        ]
        for index, emit in enumerate(functions):
            with self.subTest(generator=index):
                destination = self.root / str(index)
                destination.mkdir()
                sentinel = destination / "existing-evidence.txt"
                sentinel.write_bytes(b"preserve exactly")
                with self.assertRaises(FileExistsError):
                    emit(destination)
                self.assertEqual(sentinel.read_bytes(), b"preserve exactly")
                self.assertEqual(list(destination.iterdir()), [sentinel])

    def test_empty_directory_is_usable_but_not_reusable(self):
        dest = self.root / "empty"
        dest.mkdir()
        emit_bundle(dest, 0)
        original = {p.relative_to(dest): p.read_bytes() for p in dest.rglob("*") if p.is_file()}
        with self.assertRaises(FileExistsError):
            emit_bundle(dest, 1)
        self.assertEqual(original, {p.relative_to(dest): p.read_bytes() for p in dest.rglob("*") if p.is_file()})

    def test_result_file_is_exclusive(self):
        path = self.root / "measurement.json"
        write_text_exclusive(path, '{"count": 7}\n')
        with self.assertRaises(FileExistsError):
            write_text_exclusive(path, '{"count": 8}\n')
        self.assertEqual(path.read_bytes(), b'{"count": 7}\n')

    def test_output_directory_refuses_file_and_nonempty_directory(self):
        path = self.root / "evidence"
        path.write_bytes(b"initial")
        with self.assertRaises(FileExistsError):
            fresh_directory(path)
        with self.assertRaises(FileExistsError):
            fresh_directory(self.root)
        self.assertEqual(path.read_bytes(), b"initial")

    def test_path_sorted_counterexample_is_admitted(self):
        def document(body):
            return '<!doctype html><html><head><title>Fixture</title></head><body>' + body + '</body></html>'
        endpoints = []
        for side, first, second in [("left", "a.html", "b.html"), ("right", "b.html", "a.html")]:
            path = self.root / side
            path.mkdir()
            files = {"index.html": document(f'<a href="{first}">first</a><a href="{second}">second</a>'),
                     first: document("alpha"), second: document("beta")}
            for name, content in files.items():
                write_text_exclusive(path / name, content)
            write_text_exclusive(path / "bundle.json", json.dumps({"format": "iwb-1", "root": "index.html", "resources": list(files)}))
            endpoints.append(path)
        left, right = map(producer_core.parse_bundle, endpoints)
        self.assertEqual(left.resource_order, ["index.html", "a.html", "b.html"])
        self.assertEqual(right.resource_order, ["index.html", "b.html", "a.html"])
        self.assertEqual(left.canonical_bytes, right.canonical_bytes)
        cert = producer_core.make_certificate(*endpoints)
        self.assertEqual(cert["decision"], "equivalent")
        self.assertTrue(checker_core.verify_certificate(*endpoints, cert)["accepted"])
        def path_sorted_records(parsed):
            order = [parsed.root] + sorted(set(parsed.resources) - {parsed.root})
            labels = {name: f"r{i}" for i, name in enumerate(order)}
            return [producer_core._canon_html(name, parsed.resources[name]["events"], labels, {}, {}) for name in order]
        self.assertNotEqual(path_sorted_records(left), path_sorted_records(right))

    def test_metadata_timestamps_are_compared_within_each_api(self):
        path = self.root / "static.bin"
        path.write_bytes(b"owned")
        fields = dict(st_dev=1, st_ino=2, st_mode=0o100644, st_size=5,
                      st_mtime_ns=7, st_ctime_ns=11, st_birthtime_ns=13)
        before = SimpleNamespace(**fields)
        opened = SimpleNamespace(**dict(fields, st_ctime_ns=17))
        for core in (producer_core, checker_core):
            with self.subTest(core=core.__name__):
                with patch.object(core.os, "name", "nt"), \
                     patch.object(core.os, "fstat", side_effect=[opened, opened]), \
                     patch.object(Path, "lstat", return_value=before):
                    self.assertEqual(core._read_stable(path, "static.bin", before, 5), b"owned")
                # A real change in either metadata API still fails closed.
                for api in ("path", "handle"):
                    changed = SimpleNamespace(**dict(fields, st_ctime_ns=19))
                    with patch.object(core.os, "name", "nt"), \
                         patch.object(core.os, "fstat", side_effect=[opened, changed if api == "handle" else opened]), \
                         patch.object(Path, "lstat", return_value=changed if api == "path" else before):
                        with self.assertRaises(core.EnvironmentFailure):
                            core._read_stable(path, "static.bin", before, 5)


if __name__ == "__main__":
    unittest.main()
