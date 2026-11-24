import tempfile
import unittest
from pathlib import Path

from optical_desk.burn_queue import BurnQueue


class BurnQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / "工作资料"
        self.folder.mkdir()
        (self.folder / "保留.txt").write_text("keep", encoding="utf-8")
        (self.folder / "删除.txt").write_text("remove", encoding="utf-8")
        self.loose = self.root / "说明.txt"
        self.loose.write_text("readme", encoding="utf-8")
        self.queue = BurnQueue()
        self.queue.add_paths([self.folder, self.loose])

    def tearDown(self):
        self.temp.cleanup()

    def test_nested_delete_does_not_touch_original(self):
        folder = self.queue.roots[0]
        target = next(entry for entry in folder.children if entry.name == "删除.txt")
        self.assertEqual(self.queue.remove([target]), 1)
        self.assertTrue(target.source.exists())
        stage = self.root / "stage"
        self.queue.materialize(stage)
        self.assertTrue((stage / "工作资料" / "保留.txt").exists())
        self.assertFalse((stage / "工作资料" / "删除.txt").exists())

    def test_move_into_folder_is_real_staging_structure(self):
        folder, loose = self.queue.roots
        self.assertEqual(self.queue.move([loose], folder), 1)
        stage = self.root / "stage"
        self.assertEqual(self.queue.materialize(stage), 3)
        self.assertEqual((stage / "工作资料" / "说明.txt").read_text(encoding="utf-8"), "readme")
        self.assertFalse((stage / "说明.txt").exists())
        self.assertTrue(self.loose.exists())

    def test_reject_cycles_and_duplicate_target_names(self):
        folder, loose = self.queue.roots
        self.assertEqual(self.queue.move([folder], folder), 0)
        self.assertEqual(self.queue.move([loose], folder), 1)
        other = self.root / "other"
        other.mkdir()
        self.queue.add_paths([other])
        other_entry = self.queue.roots[-1]
        self.assertEqual(self.queue.move([other_entry], folder), 1)
        self.assertEqual(self.queue.move([folder], other_entry), 0)

    def test_create_rename_and_reject_duplicate(self):
        folder = self.queue.create_folder("交接资料")
        self.assertTrue(folder.is_dir)
        self.queue.rename(folder, "正式交接")
        self.assertEqual(folder.name, "正式交接")
        with self.assertRaises(ValueError):
            self.queue.create_folder("正式交接")

    def test_organize_only_loose_files_and_materialize(self):
        for name in ("照片.jpg", "视频.mp4", "资料.zip", "脚本.py", "未知.bin"):
            (self.root / name).write_text(name, encoding="utf-8")
        self.queue.add_paths([self.root / name for name in ("照片.jpg", "视频.mp4", "资料.zip", "脚本.py", "未知.bin")])
        original_folder = self.queue.roots[0]
        self.queue.organize()
        self.assertEqual(original_folder.parent, None)
        self.assertEqual([child.name for child in original_folder.children], ["保留.txt", "删除.txt"])
        self.assertFalse(any(entry.name == "说明.txt" and entry.parent is None for entry in self.queue.roots))
        stage = self.root / "organized-stage"
        self.queue.materialize(stage)
        for relative in ("文档资料/说明.txt", "图片照片/照片.jpg", "音视频/视频.mp4",
                         "压缩包/资料.zip", "程序与代码/脚本.py", "其他文件/未知.bin"):
            self.assertTrue((stage / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
