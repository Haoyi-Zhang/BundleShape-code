"""URI component presence at the declared admission boundary."""
import unittest

from src import checker_core, producer_core


class ReferenceComponentTests(unittest.TestCase):
    def test_present_empty_query_is_rejected(self):
        for core in (producer_core, checker_core):
            with self.subTest(core=core.__name__):
                with self.assertRaises(core.AdmissionError):
                    core._resolve_ref('index.html', 'child.html?', 'reference')

    def test_present_empty_fragment_is_rejected(self):
        for core in (producer_core, checker_core):
            with self.subTest(core=core.__name__):
                with self.assertRaises(core.AdmissionError):
                    core._resolve_ref('index.html', 'child.html#', 'reference')

    def test_ordinary_path_and_named_fragment_are_preserved(self):
        for core in (producer_core, checker_core):
            with self.subTest(core=core.__name__):
                self.assertEqual(core._resolve_ref('index.html', 'child.html', 'reference'), ('child.html', None))
                self.assertEqual(core._resolve_ref('index.html', 'child.html#anchor', 'reference'), ('child.html', 'anchor'))


if __name__ == '__main__':
    unittest.main()
