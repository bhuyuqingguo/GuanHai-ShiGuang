import base64
import hashlib
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "build_deps"))
sys.path.insert(0, str(ROOT / "optical_desk"))
from Cryptodome.Cipher import AES
from secure_transfer import SecureTransferService


class CrossPlatformPackageTests(unittest.TestCase):
    def test_bfq_package_recovers_standard_directory_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "资料.txt"
            source.write_text("Windows 与麒麟交接测试", encoding="utf-8")
            service = SecureTransferService()
            with patch.object(service.passwords, "save"):
                result = service.create_package([source], root, "测试交接", "正确密码")
            self.assertTrue(result.ok, result.message)
            target = Path(result.package_path)
            self.assertEqual(target.suffix, ".bfq")
            restored = root / "restored"
            recovered = service.recover_package(target, "正确密码", restored)
            self.assertTrue(recovered.ok, recovered.message)
            self.assertEqual((restored / "资料.txt").read_text(encoding="utf-8"), "Windows 与麒麟交接测试")

    def test_name_controls_update_date(self):
        with tempfile.TemporaryDirectory() as temp:
            service = SecureTransferService()
            with patch.object(service.passwords, "save"):
                source = Path(temp) / "a.txt"
                source.write_text("a")
                result = service.create_package([source], temp, "工作资料-2026-11-24", "p")
            self.assertTrue(result.package_path.endswith("工作资料-2026-11-24.bfq"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
