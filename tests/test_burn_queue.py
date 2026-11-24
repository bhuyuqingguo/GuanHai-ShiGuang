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


if __name__ == "__main__":
    unittest.main()
