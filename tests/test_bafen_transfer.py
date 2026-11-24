import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from secure_transfer import SecureTransferService


class BafenTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = self.root / "中文目录"
        source.mkdir()
        (source / "中文资料.txt").write_text("八分跨平台测试", encoding="utf-8")
        self.output = self.root / "out"
        self.service = SecureTransferService()

    def tearDown(self):
        self.temp.cleanup()

    def test_real_bfq_pack_and_directory_recovery(self):
        result = self.service.create_package([source := self.root / "中文目录"], self.output,
                                             "2026-11-24-项目资料-测试人", "正确密码")
        self.assertTrue(result.ok, result.message)
        self.assertTrue(result.package_path.endswith(".bfq"))
        restored = self.root / "restored"
        recovered = self.service.recover_package(result.package_path, "正确密码", restored)
        self.assertTrue(recovered.ok, recovered.message)
        self.assertEqual((restored / "中文目录" / "中文资料.txt").read_text(encoding="utf-8"), "八分跨平台测试")
        wrong = self.service.recover_package(result.package_path, "错误密码", self.root / "wrong")
        self.assertFalse(wrong.ok)
        self.assertFalse((self.root / "wrong" / "中文目录" / "中文资料.txt").exists())

    def test_wrong_password_and_existing_target_are_safe(self):
        target = self.output / "资料.bfq"
        target.parent.mkdir()
        target.write_bytes(b"keep")
        result = self.service.create_package([self.root / "中文目录"], self.output, "资料", "密码")
        self.assertFalse(result.ok)
        self.assertEqual(target.read_bytes(), b"keep")

    def test_pre_cancelled_operation_creates_no_package(self):
        cancel = threading.Event()
        cancel.set()
        result = self.service.create_package([self.root / "中文目录"], self.output, "取消测试", "密码", cancel_event=cancel)
        self.assertFalse(result.ok)
        self.assertFalse((self.output / "取消测试.bfq").exists())


if __name__ == "__main__":
    unittest.main()
