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
    def test_html_package_decrypts_to_standard_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "资料.txt"
            source.write_text("Windows 与麒麟交接测试", encoding="utf-8")
            service = SecureTransferService()
            with patch.object(service.passwords, "save"):
                result = service.create_package([source], root, "测试交接", "正确密码")
            self.assertTrue(result.ok, result.message)
            target = Path(result.package_path)
            self.assertEqual(target.suffix, ".html")
            html = target.read_text(encoding="utf-8")
            self.assertIn("Windows / 银河麒麟通用", html)
            self.assertNotIn("https://", html)
            config = json.loads(re.search(r"const C=(\{.*?\});", html, re.S).group(1))
            salt = base64.b64decode(config["salt"])
            iv = base64.b64decode(config["iv"])
            raw = base64.b64decode(config["payload"])
            key = hashlib.pbkdf2_hmac("sha256", "正确密码".encode(), salt, 200000, 32)
            clear = AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(raw[:-16], raw[-16:])
            with zipfile.ZipFile(__import__("io").BytesIO(clear)) as archive:
                self.assertEqual(archive.read("资料.txt").decode("utf-8"), "Windows 与麒麟交接测试")

    def test_name_controls_update_date(self):
        with tempfile.TemporaryDirectory() as temp:
            service = SecureTransferService()
            with patch.object(service.passwords, "save"):
                source = Path(temp) / "a.txt"
                source.write_text("a")
                result = service.create_package([source], temp, "工作资料-2026-11-24", "p")
            self.assertTrue(result.package_path.endswith("工作资料-2026-11-24.html"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
