from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import win32crypt
from Cryptodome.Cipher import AES

from optical.models import DriveInfo, OperationResult, format_size

Progress = Callable[[str, int | None], None]


@dataclass
class PackageResult(OperationResult):
    package_path: str = ""
    sha256: str = ""


class PasswordArchive:
    """使用当前 Windows 账户保护密码，其他 Windows 账户无法直接读取。"""

    def __init__(self):
        self.path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GuanHaiShiGuang" / "password_archive.json"

    def save(self, package_name: str, password: str, sha256: str):
        protected = win32crypt.CryptProtectData(password.encode("utf-8"), "观海·拾光密码归档", None, None, None, 0)
        records = self.load()
        records.insert(0, {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "package": package_name,
                           "sha256": sha256, "password": base64.b64encode(protected).decode("ascii")})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(records[:100], ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def reveal(self, record: dict) -> str:
        raw = base64.b64decode(record["password"])
        return win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1].decode("utf-8")


def sha256_file(path: str | Path, callback: Progress | None = None) -> str:
    digest = hashlib.sha256()
    source = Path(path)
    total = source.stat().st_size
    done = 0
    with source.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
            done += len(block)
            if callback and total:
                callback(f"正在核对文件是否完整 · {format_size(done)} / {format_size(total)}", min(99, done * 100 // total))
    return digest.hexdigest()


def _receiver_html(title: str, zip_name: str, salt: bytes, iv: bytes, payload: bytes) -> str:
    config = json.dumps({"salt": base64.b64encode(salt).decode(), "iv": base64.b64encode(iv).decode(),
                         "payload": base64.b64encode(payload).decode(), "name": zip_name}, ensure_ascii=False)
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>观海·拾光 · 加密交接</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#101515;color:#f2e8d5;font-family:"Microsoft YaHei UI","Noto Sans CJK SC",sans-serif}.card{width:min(90vw,460px);padding:36px;border:1px solid #3b4438;border-radius:18px;background:#19211f;box-shadow:0 20px 60px #0006}h1{font-size:24px;margin:0 0 8px;color:#d6b56c}h2{font-size:18px;overflow-wrap:anywhere;margin:22px 0 8px}p{color:#b0a58f;line-height:1.8;font-size:14px}input,button{width:100%;padding:14px;border-radius:9px;border:1px solid #3b4438;font-size:16px}input{background:#26332d;color:#fff;margin:12px 0}button{background:#79613a;color:#fff;cursor:pointer;font-weight:bold}button:hover{background:#95794a}#msg{min-height:28px;color:#d6b56c}.foot{margin-top:22px;font-size:12px;color:#887f6c}</style></head><body><main class="card">
<h1>观海·拾光</h1><p>Windows / 银河麒麟通用 · 离线加密交接</p><h2>""" + safe_title + """</h2>
<form id="form"><label for="password">请输入交接密码</label><input id="password" type="password" autocomplete="current-password" autofocus required><button id="open" type="submit">解密并保存资料</button></form>
<p id="msg" role="status"></p><p class="foot">资料只在当前电脑浏览器中解密，不会上传。解密后会得到一个 ZIP 压缩包，用系统自带工具打开即可。</p></main>
<script>const C=""" + config + """;
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));const msg=document.getElementById('msg');
document.getElementById('form').onsubmit=async e=>{e.preventDefault();const btn=document.getElementById('open');btn.disabled=true;msg.textContent='正在本机解密，请稍候…';try{
const keyMaterial=await crypto.subtle.importKey('raw',new TextEncoder().encode(document.getElementById('password').value),'PBKDF2',false,['deriveKey']);
const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:b64(C.salt),iterations:200000,hash:'SHA-256'},keyMaterial,{name:'AES-GCM',length:256},false,['decrypt']);
const clear=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64(C.iv)},key,b64(C.payload));const blob=new Blob([clear],{type:'application/zip'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=C.name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);msg.textContent='解密成功，资料压缩包已开始保存。';}catch(err){msg.textContent='无法解密：请检查密码是否正确，并使用新版 Edge、Chrome、Firefox 或麒麟自带浏览器打开。';}finally{btn.disabled=false;}};
</script></body></html>"""


class SecureTransferService:
    def __init__(self, stub_path: str = ""):
        # 旧版需要 Windows 自解压程序；新版保留参数仅用于兼容调用，不再依赖它。
        self.stub_path = Path(stub_path) if stub_path else None
        self.passwords = PasswordArchive()

    @staticmethod
    def _files(sources: Iterable[str | Path]):
        files: list[tuple[Path, str, int]] = []
        for value in sources:
            source = Path(value).resolve()
            if source.is_file():
                files.append((source, source.name, source.stat().st_size))
            elif source.is_dir():
                for item in sorted(source.rglob("*")):
                    if item.is_file():
                        files.append((item, str(Path(source.name) / item.relative_to(source)), item.stat().st_size))
        if not files:
            raise ValueError("没有可交接的文件。")
        return files

    def create_package(self, sources: Iterable[str | Path], destination: str | Path,
                       package_name: str, password: str, callback: Progress | None = None) -> PackageResult:
        callback = callback or (lambda _t, _v: None)
        files = self._files(sources)
        total = sum(item[2] for item in files)
        safe_name = Path(package_name.strip() or "加密交接").name
        if safe_name.lower().endswith((".exe", ".html")):
            safe_name = safe_name.rsplit(".", 1)[0]
        target_dir = Path(destination)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (safe_name + ".html")
        temp_dir = Path(tempfile.mkdtemp(prefix="GuanHaiSecure_"))
        archive = temp_dir / "payload.zip"
        try:
            done = 0
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as pack:
                for source, arcname, size in files:
                    callback(f"正在整理交接资料：{arcname} · {format_size(done)} / {format_size(total)}", int(done * 65 / max(1, total)))
                    pack.write(source, arcname)
                    done += size
                    callback(f"已整理：{arcname}", int(done * 65 / max(1, total)))
            callback("正在加密并生成双系统交接页…", 72)
            salt, iv = os.urandom(16), os.urandom(12)
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000, 32)
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            plain = archive.read_bytes()
            encrypted, tag = cipher.encrypt_and_digest(plain)
            # 本地解密复核后才交付，避免把密码错误或数据损坏带出去。
            check = AES.new(key, AES.MODE_GCM, nonce=iv)
            if check.decrypt_and_verify(encrypted, tag) != plain:
                raise ValueError("本地加密复核未通过。")
            target.write_text(_receiver_html(safe_name, safe_name + ".zip", salt, iv, encrypted + tag), encoding="utf-8")
            digest = sha256_file(target)
            self.passwords.save(target.name, password, digest)
            callback("双系统交接文件已生成并完成本地校验", 100)
            return PackageResult(True, f"交接文件已生成 · Windows 和麒麟均可打开 · {format_size(target.stat().st_size)}",
                                 ["离线网页", "内容和文件名均加密", "密码已在本机归档"], str(target), digest)
        except Exception as exc:
            return PackageResult(False, f"交接文件生成失败：{exc}")
        finally:
            try:
                temp_dir.unlink()
            except OSError:
                pass
            archive.unlink(missing_ok=True)
            try:
                temp_dir.rmdir()
            except OSError:
                pass

    def burn_package(self, package_path: str, expected_hash: str, disc_service, drive: DriveInfo,
                     mode: str, callback: Progress) -> OperationResult:
        package = Path(package_path)
        try:
            if drive.file_system == "UDF" and not drive.blank:
                result = disc_service.copy_to_disc(drive.recorder_id, [package], callback=callback)
            else:
                result = disc_service.burn(drive.recorder_id, [package], "观海交接", True, callback, mode)
            if not result.ok:
                return result
            callback("正在从光盘读回并检查文件是否完整…", 96)
            disc_service._initialize()
            letters = disc_service._letters(disc_service._recorder(drive.recorder_id))
            if not letters:
                return OperationResult(False, "刻录完成，但无法取得光盘位置进行复核。")
            burned = Path(letters[0] + "\\") / package.name
            actual = sha256_file(burned)
            if actual.lower() != expected_hash.lower():
                return OperationResult(False, "光盘复核失败：读回文件与本地交接文件不一致。")
            callback("光盘复核通过", 100)
            return OperationResult(True, "双系统交接文件刻录完成，光盘复核通过", [expected_hash])
        except Exception as exc:
            return OperationResult(False, f"刻录或光盘复核失败：{exc}")
        finally:
            disc_service._finish()
