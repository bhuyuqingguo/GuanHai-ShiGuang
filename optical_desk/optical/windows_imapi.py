from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from .models import DriveInfo, FileEntry, OperationResult, format_size

_IMPORT_ERROR = ""
try:
    import pythoncom
    import win32com.client
except ImportError as exc:  # 让未安装依赖时仍能启动并显示安装提示
    _IMPORT_ERROR = str(exc)
    pythoncom = None
    win32com = None


ProgressCallback = Callable[[str, int | None], None]

# IMAPI2 KnownCdProfiles / IMAPI_PROFILE_TYPE
PROFILE_NAMES = {
    0x0008: "CD-ROM",
    0x0009: "CD-R",
    0x000A: "CD-RW",
    0x0010: "DVD-ROM",
    0x0011: "DVD-R 顺序写入",
    0x0012: "DVD-RAM",
    0x0013: "DVD-RW 受限覆写",
    0x0014: "DVD-RW 顺序写入",
    0x0015: "DVD+R 双层",
    0x0016: "DVD+R 双层跳变",
    0x0017: "DVD-RW 双层",
    0x001A: "DVD+R",
    0x001B: "DVD+RW",
    0x0021: "DVD-R 双层顺序写入",
    0x0022: "DVD-R 双层跳变",
    0x0040: "BD-ROM",
    0x0041: "BD-R",
    0x0042: "BD-RE",
    0x0050: "HD DVD-ROM",
    0x0051: "HD DVD-R",
    0x0052: "HD DVD-RAM",
}
REWRITABLE_PROFILES = {0x000A, 0x0012, 0x0013, 0x0014, 0x0017, 0x001B, 0x0042, 0x0052}
WRITABLE_PROFILES = REWRITABLE_PROFILES | {0x0009, 0x0011, 0x0015, 0x0016, 0x001A, 0x0021, 0x0022, 0x0041, 0x0051}
CD_PROFILES = {0x0008, 0x0009, 0x000A}
PHYSICAL_NAMES = {
    1: "CD-ROM", 2: "CD-R", 3: "CD-RW", 4: "DVD-ROM", 5: "DVD-R",
    6: "DVD+RW", 7: "DVD+R", 8: "DVD-RW", 9: "DVD-RAM", 10: "DVD+R DL",
    11: "DVD-R DL", 12: "BD-ROM", 13: "BD-R", 14: "BD-RE",
}
FS_ISO9660 = 1
FS_JOLIET = 2
FS_UDF = 4


class OpticalError(RuntimeError):
    pass


def dependency_message() -> str | None:
    if os.name != "nt":
        return "当前版本仅支持 Windows。"
    if pythoncom is None:
        return f"刻录组件加载失败：{_IMPORT_ERROR}"
    return None


def _com_error(exc: Exception) -> str:
    text = str(exc).strip()
    lowered = text.lower()
    hresult = _decode_hresult(exc)
    if hresult == 0x80070015:
        return "光驱尚未就绪，请等待光盘装入后点击“重新检测”。"
    if hresult == 0xC0AA0206:
        return "光驱正在准备介质，请等待当前操作结束后重试。"
    hints = (
        ("0xc0aa0301", "光盘正在被其他程序占用，请关闭资源管理器中的刻录任务或其他刻录软件。"),
        ("0xc0aa0007", "设备中没有可写光盘，或光盘与刻录机不兼容。"),
        ("0xc0aa0202", "光盘不可写或已经关闭，无法继续写入。"),
        ("0x80070005", "系统拒绝了访问，请检查驱动器占用和权限。"),
        ("0xc0aa0402", "光盘已关闭，无法添加新的写入会话。"),
    )
    for code, hint in hints:
        if code in lowered:
            return hint
    return f"操作未完成：{text or exc.__class__.__name__}"


def _decode_hresult(exc: Exception) -> int | None:
    try:
        return int(exc.hresult) & 0xFFFFFFFF
    except (AttributeError, TypeError, ValueError):
        return None


class DiscService:
    """每个公共方法都可从工作线程调用；COM 仅在当前线程初始化。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = None
        self._active_kind = ""

    def _initialize(self) -> None:
        message = dependency_message()
        if message:
            raise OpticalError(message)
        pythoncom.CoInitialize()

    @staticmethod
    def _finish() -> None:
        if pythoncom is not None:
            pythoncom.CoUninitialize()

    @staticmethod
    def _recorder(recorder_id: str):
        recorder = win32com.client.Dispatch("IMAPI2.MsftDiscRecorder2")
        recorder.InitializeDiscRecorder(recorder_id)
        return recorder

    @staticmethod
    def _letters(recorder) -> tuple[str, ...]:
        try:
            values = recorder.VolumePathNames
            if isinstance(values, str):
                values = (values,)
            return tuple(str(v).rstrip("\\") for v in values)
        except Exception:
            return ()

    def list_drives(self) -> list[DriveInfo]:
        self._initialize()
        try:
            master = win32com.client.Dispatch("IMAPI2.MsftDiscMaster2")
            drives: list[DriveInfo] = []
            for index in range(master.Count):
                recorder_id = str(master.Item(index))
                try:
                    drives.append(self.inspect_recorder(recorder_id))
                except Exception as exc:
                    drives.append(DriveInfo(recorder_id, f"光驱 {index + 1}", status=_com_error(exc)))
            return drives
        except Exception as exc:
            raise OpticalError(_com_error(exc)) from exc
        finally:
            self._finish()

    def inspect_recorder(self, recorder_id: str) -> DriveInfo:
        recorder = self._recorder(recorder_id)
        letters = self._letters(recorder)
        vendor = str(getattr(recorder, "VendorId", "")).strip()
        product = str(getattr(recorder, "ProductId", "")).strip()
        name = " ".join(part for part in (vendor, product) if part) or "光盘驱动器"
        info = DriveInfo(recorder_id, name, letters, vendor, product)
        file_system = ""
        volume_name = ""
        # IMAPI2 数据接口没有 CurrentProfile。介质是否存在由 MediaLoaded、
        # CurrentMediaStatus 和逻辑光盘卷共同判断，避免把 UDF 盘误报为空驱动器。
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            for drive in wmi.ExecQuery("SELECT Drive, MediaLoaded FROM Win32_CDROMDrive"):
                if str(drive.Drive).upper() in {letter.upper() for letter in letters}:
                    info.present = bool(drive.MediaLoaded)
            for volume in wmi.ExecQuery("SELECT DeviceID, VolumeName, FileSystem, Size, FreeSpace FROM Win32_LogicalDisk WHERE DriveType=5"):
                if str(volume.DeviceID).upper() in {letter.upper() for letter in letters}:
                    info.present = True
                    file_system = str(volume.FileSystem or "")
                    volume_name = str(volume.VolumeName or "")
                    info.capacity_bytes = int(volume.Size or 0)
                    info.free_bytes = int(volume.FreeSpace or 0)
        except Exception:
            pass
        physical_type = 0
        try:
            data = win32com.client.Dispatch("IMAPI2.MsftDiscFormat2Data")
            data.Recorder = recorder
            media_state = int(data.CurrentMediaStatus)
            physical_type = int(data.CurrentPhysicalMediaType)
            info.profile = physical_type
            # 部分从未初始化的 CD-RW 返回 0x4800，而不是 HeuristicallyBlank。
            # 没有文件系统且属于可重写介质时，应进入空白盘准备流程。
            info.blank = bool(data.MediaHeuristicallyBlank) or (media_state == 0x4800 and physical_type in {3, 6, 8, 9, 14} and not file_system)
            info.present = info.present or media_state != 0 or physical_type != 0
            info.writable = media_state in (1, 2) or info.blank
            info.erasable = physical_type in {3, 6, 8, 9, 14} if physical_type else (info.present and not info.blank)
            try:
                info.capacity_bytes = max(info.capacity_bytes, int(data.TotalSectorsOnMedia) * 2048)
                info.free_bytes = max(0, int(data.FreeSectorsOnMedia)) * 2048
            except Exception:
                pass
        except Exception:
            info.writable = False
            info.erasable = info.present and not info.blank
        info.file_system = file_system.upper()
        if info.file_system == "UDF" and not info.blank and info.free_bytes > 0:
            info.writable = True
        media_name = PHYSICAL_NAMES.get(physical_type, "")
        family = "CD" if media_name.startswith("CD") or (not media_name and info.capacity_bytes <= 1024**3) else ("DVD" if media_name.startswith("DVD") or info.capacity_bytes <= 12 * 1024**3 else "BD")
        if not info.present:
            info.status = "请放入光盘"
            info.profile_name = "未检测到光盘"
        elif info.blank:
            info.profile_name = f"空白 {media_name or family} · 可写"
            info.status = f"空白 {media_name or family} · 可以刻录"
        else:
            disc_kind = media_name or family
            use_text = "可继续复制文件" if info.file_system == "UDF" and info.writable and info.free_bytes > 0 else "光盘已有文件"
            info.profile_name = " · ".join(part for part in (disc_kind, use_text, f"光盘名称：{volume_name}" if volume_name else "") if part)
            info.status = ("可以直接复制文件" if info.file_system == "UDF" and info.writable and info.free_bytes > 0 else "光盘已有文件 · 可继续刻录" if info.writable and info.free_bytes > 0 else "光盘已有文件 · 可读取或擦除")
        return info

    def eject(self, recorder_id: str) -> OperationResult:
        self._initialize()
        try:
            recorder = self._recorder(recorder_id)
            recorder.EjectMedia()
            return OperationResult(True, "已弹出光盘")
        except Exception as exc:
            return OperationResult(False, _com_error(exc))
        finally:
            self._finish()

    def _set_active(self, obj, kind: str) -> None:
        with self._lock:
            self._active = obj
            self._active_kind = kind

    def _clear_active(self) -> None:
        with self._lock:
            self._active = None
            self._active_kind = ""

    def cancel(self) -> bool:
        with self._lock:
            active, kind = self._active, self._active_kind
        if active is None:
            return False
        try:
            if kind == "burn":
                active.CancelWrite()
            elif kind == "erase":
                active.CancelEraseMedia()
            elif kind == "format":
                active.terminate()
            return True
        except Exception:
            return False

    @staticmethod
    def _erase_events(callback: ProgressCallback):
        class EraseEvents:
            def Update(self, args):
                try:
                    elapsed = int(args.ElapsedTime)
                    remaining = max(1, int(args.RemainingTime))
                    percent = min(99, int(elapsed * 100 / (elapsed + remaining)))
                    callback(f"正在擦除… 已用 {elapsed} 秒", percent)
                except Exception:
                    callback("正在擦除…", None)
        return EraseEvents

    @staticmethod
    def _shell_media_notification(event: int, letters: tuple[str, ...]) -> None:
        notify = ctypes.windll.shell32.SHChangeNotify
        notify.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p]
        for letter in letters:
            notify(event, 0x0005, letter + "\\", None)  # SHCNF_PATHW

    @classmethod
    def _notify_shell_blank_media(cls, letters: tuple[str, ...]) -> None:
        # SHCNE_MEDIAREMOVED / SHCNE_MEDIAINSERTED，不能误用 RMDIR / MKDIR。
        # 完整路径和盘符都通知一次，使资源管理器及 AutoPlay 放弃旧的 UDF 卷缓存。
        cls._shell_media_notification(0x00000040, letters)
        time.sleep(0.4)
        cls._shell_media_notification(0x00000020, letters)
        cls._shell_media_notification(0x00002000, letters)  # SHCNE_UPDATEITEM
        cls._shell_media_notification(0x00008000, letters)  # SHCNE_UPDATEDIR

    def _reload_and_verify_blank(self, recorder, full: bool, callback: ProgressCallback) -> OperationResult:
        """验证物理空白并重新通知资源管理器；空白盘本身没有可读取的文件系统。"""
        letters = self._letters(recorder)
        if not letters:
            return OperationResult(False, "擦除已执行，但光驱没有盘符，无法确认空白盘状态。")
        callback("正在确认空白状态并刷新 Windows 光盘缓存…", 96)
        for attempt in range(12):
            try:
                data = win32com.client.Dispatch("IMAPI2.MsftDiscFormat2Data")
                data.Recorder = recorder
                if bool(data.MediaHeuristicallyBlank):
                    physical = bool(data.MediaPhysicallyBlank)
                    capacity = int(data.TotalSectorsOnMedia)
                    available = int(data.FreeSectorsOnMedia)
                    if capacity <= 0 or available != capacity:
                        raise OpticalError("空白标志已返回，但可用扇区尚未恢复，请继续等待。")
                    if ctypes.windll.kernel32.GetDriveTypeW(letters[0] + "\\") != 5:
                        raise OpticalError("Windows 尚未返回光盘驱动器状态。")
                    self._notify_shell_blank_media(letters)
                    details = [f"Windows 光盘驱动器已就绪 · {format_size(available * 2048)} 可写", "完整擦除" if full else "快速擦除"]
                    if full:
                        details.append("介质物理空白" if physical else "完整擦除已完成，空白标志已确认")
                    details.append("空白盘没有文件目录，请直接添加文件刻录；不要双击打开空白盘")
                    callback("空白光盘已就绪，可直接刻录", 100)
                    return OperationResult(True, "深度擦除完成，空白光盘已就绪，可直接刻录" if full else "快速擦除完成，空白光盘已就绪，可直接刻录", details)
            except Exception:
                pass
            time.sleep(1)
            callback(f"正在等待光驱确认空白状态… {attempt + 1} / 12 秒", 97)
        return OperationResult(False, "擦除已执行，但光驱尚未确认空白状态。请重新检测；软件不会把未确认状态报告为成功。")

    def erase(self, recorder_id: str, full: bool = False, callback: ProgressCallback | None = None) -> OperationResult:
        callback = callback or (lambda _text, _value: None)
        self._initialize()
        try:
            recorder = self._recorder(recorder_id)
            erase = win32com.client.Dispatch("IMAPI2.MsftDiscFormat2Erase")
            erase.Recorder = recorder
            erase.ClientName = "Optical Desk"
            erase.FullErase = bool(full)
            try:
                events = win32com.client.WithEvents(erase, self._erase_events(callback))
                self._set_active(erase, "erase")
            except Exception:
                self._set_active(erase, "erase")
            callback("正在快速擦除…" if not full else "正在完整擦除，请耐心等待…", None)
            erase.EraseMedia()
            self._clear_active()
            return self._reload_and_verify_blank(recorder, full, callback)
        except Exception as exc:
            return OperationResult(False, _com_error(exc))
        finally:
            self._clear_active()
            self._finish()

    def format(self, recorder_id: str, volume_name: str = "OPTICAL_DISC", callback: ProgressCallback | None = None) -> OperationResult:
        """调用 Windows 自带的 Live File System 格式化，建立真正可写的 UDF 卷。"""
        callback = callback or (lambda _text, _value: None)
        self._initialize()
        try:
            recorder = self._recorder(recorder_id)
            letters = self._letters(recorder)
            if not letters:
                raise OpticalError("该光驱没有可访问的盘符。")
            data = win32com.client.Dispatch("IMAPI2.MsftDiscFormat2Data")
            data.Recorder = recorder
            if int(data.CurrentPhysicalMediaType) not in {3, 6, 8, 9, 14}:
                raise OpticalError("只有可重写光盘支持 UDF 格式化；一次性光盘请直接刻录。")
            current_label = ""
            try:
                wmi = win32com.client.GetObject("winmgmts:")
                for volume in wmi.ExecQuery("SELECT DeviceID, VolumeName FROM Win32_LogicalDisk WHERE DriveType=5"):
                    if str(volume.DeviceID).upper() == letters[0].upper():
                        current_label = str(volume.VolumeName or "")
            except Exception:
                pass
            answers = ((current_label + "\n") if current_label else "") + "Y\n"
            command = ["format.com", letters[0], "/FS:UDF", "/V:" + (volume_name[:32] or "DATA_DISC")]
            callback("正在建立 Windows 文件目录，速度较慢的光盘可能需要几十分钟…", 0)
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="mbcs", errors="replace",
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), bufsize=0)
            self._set_active(process, "format")
            process.stdin.write(answers)
            process.stdin.close()
            chunks: list[str] = []
            last_percent = 0
            while True:
                chunk = process.stdout.read(1)
                if not chunk:
                    break
                chunks.append(chunk)
                if chunk in "%\r\n":
                    text = "".join(chunks[-160:])
                    matches = re.findall(r"(\d{1,3})\s*%", text)
                    if matches:
                        percent = min(99, int(matches[-1]))
                        if percent > last_percent:
                            last_percent = percent
                            callback(f"正在完整格式化… {percent}%", percent)
            process.wait()
            output = "".join(chunks)
            if process.returncode != 0:
                useful = [line.strip() for line in output.splitlines() if line.strip()]
                raise OpticalError("格式化失败：" + "；".join(useful[-4:]))
            return OperationResult(True, "光盘已准备好", ["已建立 Windows 文件目录，可以复制文件"])
        except OpticalError as exc:
            return OperationResult(False, str(exc))
        except Exception as exc:
            return OperationResult(False, _com_error(exc))
        finally:
            self._clear_active()
            self._finish()

    @staticmethod
    def validate_sources(sources: Iterable[str | Path]) -> tuple[list[Path], int]:
        paths = [Path(p).expanduser().resolve() for p in sources]
        if not paths:
            raise OpticalError("请先添加要刻录的文件或文件夹。")
        names: set[str] = set()
        total = 0
        for path in paths:
            if not path.exists():
                raise OpticalError(f"路径不存在：{path}")
            if path.name.casefold() in names:
                raise OpticalError(f"刻录根目录存在同名项目：{path.name}")
            names.add(path.name.casefold())
            if path.is_file():
                total += path.stat().st_size
            else:
                for root, _dirs, files in os.walk(path):
                    for filename in files:
                        try:
                            total += (Path(root) / filename).stat().st_size
                        except OSError:
                            pass
        return paths, total

    @staticmethod
    def _burn_events(callback: ProgressCallback):
        class BurnEvents:
            def Update(self, args):
                try:
                    elapsed = int(args.ElapsedTime)
                    remaining = max(0, int(args.RemainingTime))
                    percent = None
                    if elapsed + remaining > 0:
                        percent = min(99, int(elapsed * 100 / (elapsed + remaining)))
                    action = int(getattr(args, "CurrentAction", 0))
                    action_text = {1: "校验介质", 2: "写入数据", 3: "结束光盘", 4: "完成"}.get(action, "刻录")
                    callback(f"正在{action_text}… 剩余约 {remaining} 秒", percent)
                except Exception:
                    callback("正在刻录…", None)
        return BurnEvents

    def burn(self, recorder_id: str, sources: Iterable[str | Path], volume_name: str = "OPTICAL_DISC", close_disc: bool = True, callback: ProgressCallback | None = None, mode: str = "CD") -> OperationResult:
        callback = callback or (lambda _text, _value: None)
        paths, total = self.validate_sources(sources)
        self._initialize()
        staging_dir: Path | None = None
        try:
            recorder = self._recorder(recorder_id)
            data = win32com.client.Dispatch("IMAPI2.MsftDiscFormat2Data")
            data.Recorder = recorder
            data.ClientName = "GuanHaiShiGuang"
            media_state = int(data.CurrentMediaStatus)
            if media_state not in (1, 2) and not bool(data.MediaHeuristicallyBlank):
                raise OpticalError("当前介质不可直接写入；可重写光盘请先擦除。")
            capacity_bytes = int(data.TotalSectorsOnMedia) * 2048
            free_bytes = int(data.FreeSectorsOnMedia) * 2048
            required = total + 20 * 1024 * 1024
            if free_bytes and required > free_bytes:
                raise OpticalError(f"空间不足：内容约 {format_size(total)}，光盘可用约 {format_size(free_bytes)}。")

            # CD 默认 ISO9660 + Joliet；USB 选择使用 UDF mastered，适配一次性光盘。
            file_systems = FS_UDF if mode == "UDF" else ((FS_ISO9660 | FS_JOLIET) if capacity_bytes <= 1024**3 else (FS_ISO9660 | FS_JOLIET | FS_UDF))
            data.ForceMediaToBeClosed = bool(close_disc)
            image = win32com.client.Dispatch("IMAPI2FS.MsftFileSystemImage")
            image.ChooseImageDefaults(recorder)
            image.FileSystemsToCreate = file_systems
            image.VolumeName = volume_name[:32] or "OPTICAL_DISC"
            root = image.Root
            callback("正在整理刻录内容…", 0)
            staging_dir = Path(tempfile.mkdtemp(prefix="GuanHaiShiGuang_"))
            staged_files = False
            for path in paths:
                if path.is_dir():
                    callback(f"添加文件夹：{path.name}", 0)
                    root.AddTree(str(path), True)
                else:
                    callback(f"准备文件：{path.name}", 0)
                    target = staging_dir / path.name
                    try:
                        os.link(path, target)
                    except OSError:
                        shutil.copy2(path, target)
                    staged_files = True
            if staged_files:
                root.AddTree(str(staging_dir), False)
            if not bool(data.MediaHeuristicallyBlank):
                image.MultisessionInterfaces = (data.MultisessionInterfaces[0],)
            try:
                events = win32com.client.WithEvents(data, self._burn_events(callback))
                self._set_active(data, "burn")
            except Exception:
                self._set_active(data, "burn")
            callback("正在刻录，请勿弹出光盘或关闭程序…", None)
            data.Write(image.CreateResultImage().ImageStream)
            return OperationResult(True, "刻录完成", [f"已写入 {len(paths)} 个根目录项目", f"内容大小约 {format_size(total)}"])
        except OpticalError as exc:
            return OperationResult(False, str(exc))
        except Exception as exc:
            return OperationResult(False, _com_error(exc))
        finally:
            if staging_dir is not None:
                shutil.rmtree(staging_dir, ignore_errors=True)
            self._clear_active()
            self._finish()

    def copy_to_disc(self, recorder_id: str, sources: Iterable[str | Path], destination: str | None = None, callback: ProgressCallback | None = None) -> OperationResult:
        """向已格式化的 UDF 光盘直接复制文件，不经过 mastered 刻录。"""
        callback = callback or (lambda _text, _value: None)
        paths, total = self.validate_sources(sources)
        self._initialize()
        try:
            recorder = self._recorder(recorder_id)
            letters = self._letters(recorder)
            if not letters:
                raise OpticalError("该光驱没有可访问的盘符。")
            base = Path(letters[0] + "\\")
            target_dir = (base / destination).resolve() if destination else base.resolve()
            if base.resolve() not in target_dir.parents and target_dir != base.resolve():
                raise OpticalError("无效的盘内路径。")
            target_dir.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(target_dir)
            if total + 1024 * 1024 > usage.free:
                raise OpticalError(f"空间不足：内容约 {format_size(total)}，光盘可用约 {format_size(usage.free)}。")
            copied: list[str] = []
            written = 0

            def copy_with_progress(source: Path, target: Path):
                nonlocal written
                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    for child in source.iterdir():
                        copy_with_progress(child, target / child.name)
                    return
                with source.open("rb") as reader, target.open("wb") as writer:
                    while True:
                        block = reader.read(1024 * 1024)
                        if not block:
                            break
                        writer.write(block)
                        written += len(block)
                        percent = min(99, int(written * 100 / max(1, total)))
                        callback(f"正在写入 {source.name} · {format_size(written)} / {format_size(total)}", percent)
                shutil.copystat(source, target)

            for source in paths:
                copy_with_progress(source, target_dir / source.name)
                copied.append(source.name)
            callback("正在确认光盘写入结果…", 100)
            return OperationResult(True, f"已写入 {len(copied)} 个项目", copied)
        except OpticalError as exc:
            return OperationResult(False, str(exc))
        except Exception as exc:
            return OperationResult(False, f"写入光盘未完成：{exc}")
        finally:
            self._finish()

    def list_files(self, recorder_id: str, relative_path: str = "") -> list[FileEntry]:
        self._initialize()
        try:
            recorder = self._recorder(recorder_id)
            letters = self._letters(recorder)
            if not letters:
                raise OpticalError("该光驱没有可访问的盘符。")
            base = Path(letters[0] + "\\")
            target = (base / relative_path).resolve()
            if base.resolve() not in target.parents and target != base.resolve():
                raise OpticalError("无效的盘内路径。")
            last_error: Exception | None = None
            for attempt in range(6):
                try:
                    entries: list[FileEntry] = []
                    with os.scandir(target) as iterator:
                        for item in iterator:
                            try:
                                stat = item.stat()
                                entries.append(FileEntry(item.name, Path(item.path), item.is_dir(), 0 if item.is_dir() else stat.st_size, stat.st_mtime))
                            except OSError:
                                entries.append(FileEntry(item.name, Path(item.path), item.is_dir()))
                    return sorted(entries, key=lambda e: (not e.is_dir, e.name.casefold()))
                except (FileNotFoundError, NotADirectoryError, OSError) as exc:
                    last_error = exc
                    if attempt < 5:
                        time.sleep(0.75)
            raise OpticalError(f"无法读取光盘目录：{last_error}")
        except OpticalError:
            raise
        except Exception as exc:
            raise OpticalError(f"无法读取光盘目录：{exc}") from exc
        finally:
            self._finish()

    @staticmethod
    def export_files(sources: Iterable[str | Path], destination: str | Path) -> OperationResult:
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        try:
            for source_value in sources:
                source = Path(source_value)
                target = dest / source.name
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, target)
                copied.append(source.name)
            return OperationResult(True, f"已导出 {len(copied)} 个项目", copied)
        except Exception as exc:
            return OperationResult(False, f"导出未完成：{exc}", copied)

    def export_disc(self, recorder_id: str, destination: str | Path) -> OperationResult:
        """完整复制当前光盘根目录下的全部可见、系统及隐藏项目。"""
        self._initialize()
        try:
            recorder = self._recorder(recorder_id)
            letters = self._letters(recorder)
            if not letters:
                raise OpticalError("该光驱没有可访问的盘符。")
            source = Path(letters[0] + "\\")
            dest = Path(destination)
            dest.mkdir(parents=True, exist_ok=True)
            count = 0
            for item in source.iterdir():
                target = dest / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
                count += 1
            return OperationResult(True, f"整盘导出完成，共处理 {count} 个根目录项目")
        except OpticalError as exc:
            return OperationResult(False, str(exc))
        except Exception as exc:
            return OperationResult(False, f"整盘导出未完成：{exc}")
        finally:
            self._finish()
