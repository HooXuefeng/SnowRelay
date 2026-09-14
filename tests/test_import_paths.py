import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.import_paths import classify_input_paths


class TestImportPaths(unittest.TestCase):
    def test_accepts_supported_files_with_spaces_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "客户 风险结果.XLSX"
            source.touch()
            accepted, rejected = classify_input_paths([source, str(source)])
            self.assertEqual(accepted, [str(source.resolve())])
            self.assertEqual(rejected, [])

    def test_rejects_unsupported_files_and_directories(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "results"
            folder.mkdir()
            unsupported = Path(td) / "notes.txt"
            unsupported.touch()
            accepted, rejected = classify_input_paths([folder, unsupported])
            self.assertEqual(accepted, [])
            self.assertEqual(len(rejected), 2)


if __name__ == "__main__":
    unittest.main()
