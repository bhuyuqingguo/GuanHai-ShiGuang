import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from export_organizer import export_organized


class ExportOrganizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "报告.txt").write_text("doc", encoding="utf-8")
        (self.root / "照片.JPG").write_text("image", encoding="utf-8")
        folder = self.root / "原目录"
        folder.mkdir()
        (folder / "同名.txt").write_text("one", encoding="utf-8")
        (folder / "无扩展名").write_text("none", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_original_structure(self):
        output = self.root / "original"
        result = export_organized([self.root / "原目录"], output)
        self.assertTrue(result.ok)
        self.assertTrue((output / "原目录" / "同名.txt").is_file())

    def test_type_and_duplicate_names(self):
        output = self.root / "typed"
        result = export_organized([self.root / "报告.txt", self.root / "原目录"], output, "按资料类型")
        self.assertTrue(result.ok)
        self.assertEqual(len(list((output / "文档资料").glob("*.txt"))), 2)
        self.assertTrue((output / "其他文件" / "无扩展名").is_file())

    def test_all_rules(self):
        for rule in ("按修改月份", "按文件大小", "按扩展名"):
            output = self.root / rule
            result = export_organized([self.root / "照片.JPG"], output, rule)
            self.assertTrue(result.ok, result.message)
            self.assertEqual(len(list(output.rglob("照片.JPG"))), 1)


if __name__ == "__main__":
    unittest.main()
