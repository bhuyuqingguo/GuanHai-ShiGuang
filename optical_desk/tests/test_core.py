import tempfile
import unittest
from pathlib import Path

from optical.models import format_size
from optical.windows_imapi import DiscService, OpticalError


class CoreTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(700 * 1024 * 1024), "700.0 MB")

    def test_validate_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "hello.txt"
            file_path.write_text("hello", encoding="utf-8")
            folder = root / "folder"
            folder.mkdir()
            (folder / "nested.bin").write_bytes(b"1234")
            paths, size = DiscService.validate_sources([file_path, folder])
            self.assertEqual(paths, [file_path, folder])
            self.assertEqual(size, 9)

    def test_validate_empty_and_duplicate(self):
        with self.assertRaises(OpticalError):
            DiscService.validate_sources([])
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = Path(a) / "same.txt"
            second = Path(b) / "SAME.txt"
            first.write_text("a")
            second.write_text("b")
            with self.assertRaises(OpticalError):
                DiscService.validate_sources([first, second])


if __name__ == "__main__":
    unittest.main()
