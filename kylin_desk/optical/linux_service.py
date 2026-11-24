"""Linux optical-media service. No Windows APIs and no drive access at import time."""
from __future__ import annotations

try:
    import fcntl
except ImportError:  # permits pure mocked tests on non-Linux build hosts
    fcntl = None
import glob
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Iterable

from .models import DriveInfo, FileEntry, OperationResult

Progress = Callable[[str, int | None], None]
CDROM_GET_CAPABILITY = 0x5331
CDS_NO_DISK = 1
CDS_DRIVE_NOT_READY = 2
CDROM_DRIVE_STATUS = 0x5326
# Linux include/uapi/linux/cdrom.h: CAN_WRITE_* and CAN_BURN flags.
WRITE_FLAGS = 0x00000200 | 0x00000400 | 0x00001000 | 0x00002000 | 0x00020000 | 0x00040000 | 0x00200000 | 0x00400000
ERASABLE_FLAGS = 0x00000400 | 0x00002000 | 0x00020000 | 0x00040000 | 0x00400000


class OpticalError(RuntimeError):
    pass


def safe_volume_label(value: str) -> str:
    """ISO/UDF-friendly d-characters; keep result portable across readers."""
    result = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")
    return (result or "GUANHAI_DISC")[:32].upper()


def split_dnd_paths(data: str, splitlist) -> list[Path]:
    """Use Tcl's parser: handles spaces and {braced paths} correctly."""
    return [Path(p) for p in splitlist(data) if p]


def dependency_message(tools: dict[str, str | None], on_linux: bool = True) -> str:
    if not on_linux:
        return "此版本仅支持银河麒麟 V10 / Linux。"
    missing = [name for name, path in tools.items() if not path]
    if not missing:
        return ""
    return ("未找到系统工具：" + "、".join(missing) +
            "。\n请将构建机随附的 tools/<架构>/ 目录置于程序旁，或从银河麒麟安装镜像离线安装 xorriso。"
            "\n读取、文件选择与皮肤仍可使用；刻录、擦除和 UDF 初始化暂不可用。")


class CommandRunner:
    """Small injectable runner. Commands always use argv, never a shell."""
    def run(self, argv: list[str], **kwargs):
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, **kwargs)

    def popen(self, argv: list[str]):
        return subprocess.Popen(argv, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, bufsize=1)


class DiscService:
    def __init__(self, runner: CommandRunner | None = None,
                 xorriso: str | None = None, device_glob: str = "/dev/sr*"):
        self.runner = runner or CommandRunner()
        self.device_glob = device_glob
        self._xorriso = xorriso
        self._process: subprocess.Popen | None = None
        self._cancelled = threading.Event()
        self._lock = threading.Lock()

    @property
    def xorriso(self) -> str:
        if self._xorriso:
            return self._xorriso
        # PyInstaller onefile extracts embedded binaries into its private _MEIPASS.
        # Current-directory and source-tree paths remain development fallbacks.
        bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        bases = [bundle / "tools", Path.cwd() / "tools", Path(__file__).resolve().parents[1] / "tools"]
        for base in bases:
            for path in base.glob("*/xorriso"):
                if os.access(path, os.X_OK):
                    self._xorriso = str(path)
                    return self._xorriso
        found = shutil.which("xorriso")
        if not found:
            raise OpticalError("未找到 xorriso。请从银河麒麟安装镜像离线安装，或把匹配本机架构的 xorriso 放到程序旁 tools/<架构>/ 下。")
        self._xorriso = found
        return found

    def tools(self) -> dict[str, str | None]:
        try:
            return {"xorriso": self.xorriso}
        except OpticalError:
            return {"xorriso": None}

    @staticmethod
    def _ioctl(fd: int, request: int, default: int = 0) -> int:
        try:
            return fcntl.ioctl(fd, request, default)
        except OSError:
            return default

    def inspect_device(self, device: str) -> DriveInfo:
        """Read-only status/capacity ioctls; no burn/blank/eject operation."""
        if fcntl is None:
            raise OpticalError("当前系统不支持 Linux 光盘 ioctl；请在银河麒麟 V10 / Linux 上运行。")
        info = DriveInfo(device=device)
        sys_name = Path(device).name
        for sys_path, attr in ((f"/sys/block/{sys_name}/device/vendor", "vendor"),
                               (f"/sys/block/{sys_name}/device/model", "model")):
            try:
                value = Path(sys_path).read_text(encoding="utf-8").strip()
                setattr(info, attr, value)
            except OSError:
                pass
        vendor = getattr(info, "vendor", "")
        model = getattr(info, "model", "")
        info.name = " ".join((vendor + " " + model).split()) or "光盘驱动器"
        try:
            fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            info.status = f"设备不可读：{exc.strerror or exc}。请检查当前用户是否在 cdrom 用户组。"
            return info
        try:
            caps = self._ioctl(fd, CDROM_GET_CAPABILITY)
            info.writable = bool(caps & WRITE_FLAGS)
            info.erasable = bool(caps & ERASABLE_FLAGS)
            status = self._ioctl(fd, CDROM_DRIVE_STATUS, CDS_NO_DISK)
            info.present = status not in (0, CDS_NO_DISK, CDS_DRIVE_NOT_READY)
            if not info.present:
                return info
            # blk_ssz is commonly 2048 for optical media. READ_CAPACITY returns
            # last logical block address + block size, unlike Windows disk APIs.
            try:
                raw = bytearray(8)
                fcntl.ioctl(fd, 0x5384, raw, True)  # CDROMREADCAPACITY
                last, block = struct.unpack(">II", raw)
                info.capacity_bytes = (last + 1) * block
            except OSError:
                info.capacity_bytes = 0
            info.profile_name = "可重写光盘" if info.erasable else ("可刻录光盘" if info.writable else "只读光盘")
            info.status = "光盘已就绪"
        finally:
            os.close(fd)
        self._fill_mount_info(info)
        return info

    def _fill_mount_info(self, info: DriveInfo) -> None:
        try:
            lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            parts = line.split()
            if "-" not in parts:
                continue
            sep = parts.index("-")
            if len(parts) > sep + 2 and parts[sep + 1] == info.device:
                info.mountpoint = parts[4].replace("\\040", " ")
                info.file_system = parts[sep + 2].upper()
                try:
                    stat = os.statvfs(info.mountpoint)
                    info.free_bytes = stat.f_bavail * stat.f_frsize
                    info.capacity_bytes = info.capacity_bytes or stat.f_blocks * stat.f_frsize
                except OSError:
                    pass
                break

    def list_drives(self) -> list[DriveInfo]:
        return [self.inspect_device(path) for path in sorted(glob.glob(self.device_glob))]

    def _require_mounted(self, device: str) -> Path:
        info = self.inspect_device(device)
        if not info.present:
            raise OpticalError("未检测到可读光盘，请放入光盘后重试。")
        if not info.mountpoint:
            raise OpticalError("光盘尚未挂载。请在麒麟文件管理器中打开一次光盘，或让系统以只读方式挂载后再读取。")
        return Path(info.mountpoint)

    def list_files(self, device: str, relative: str = "") -> list[FileEntry]:
        root = self._require_mounted(device)
        folder = (root / relative).resolve()
        if root != folder and root not in folder.parents:
            raise OpticalError("目录超出光盘范围。")
        result = []
        try:
            for path in folder.iterdir():
                stat = path.stat()
                result.append(FileEntry(path.name, path, path.is_dir(),
                                        0 if path.is_dir() else stat.st_size, stat.st_mtime))
        except OSError as exc:
            raise OpticalError(f"读取光盘目录失败：{exc}") from exc
        return sorted(result, key=lambda e: (not e.is_dir, e.name.casefold()))

    @staticmethod
    def _copy_with_progress(sources: Iterable[Path], destination: Path,
                            callback: Progress | None) -> OperationResult:
        destination.mkdir(parents=True, exist_ok=True)
        files = [p for source in sources for p in ([source] if source.is_file() else source.rglob("*")) if p.is_file()]
        total = sum(p.stat().st_size for p in files) or 1
        copied = 0
        for source in sources:
            target = destination / source.name
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)
            copied += source.stat().st_size if source.is_file() else sum(p.stat().st_size for p in source.rglob("*") if p.is_file())
            if callback:
                callback(f"正在复制 {source.name}", min(99, int(copied * 100 / total)))
        return OperationResult(True, f"已导出 {len(files)} 个文件")

    def export_files(self, sources: list[Path], destination: str,
                     callback: Progress | None = None) -> OperationResult:
        return self._copy_with_progress(sources, Path(destination), callback)

    def export_disc(self, device: str, destination: str,
                    callback: Progress | None = None) -> OperationResult:
        root = self._require_mounted(device)
        return self._copy_with_progress([root], Path(destination), callback)

    def _validate_device(self, device: str) -> None:
        path = Path(device)
        if path.parent != Path("/dev") or not re.fullmatch(r"sr\d+", path.name):
            raise OpticalError("目标不是有效的 /dev/srN 光盘设备，操作已停止。")

    def _execute(self, argv: list[str], callback: Progress | None, operation: str) -> OperationResult:
        self._cancelled.clear()
        if callback:
            callback(f"{operation}：正在启动 xorriso", None)
        with self._lock:
            try:
                self._process = self.runner.popen(argv)
            except OSError as exc:
                raise OpticalError(f"无法启动 xorriso：{exc}") from exc
        lines: list[str] = []
        assert self._process.stdout is not None
        for line in self._process.stdout:
            lines.append(line.rstrip())
            if len(lines) > 30:
                lines.pop(0)
            match = re.search(r"(\d+(?:\.\d+)?)%\s+(?:done|written)", line, re.I)
            if not match:
                match = re.search(r"(\d+(?:\.\d+)?)%", line)
            if callback:
                value = min(99, int(float(match.group(1)))) if match else None
                callback(line.strip() or f"{operation}中…", value)
        code = self._process.wait()
        self._process = None
        if self._cancelled.is_set():
            return OperationResult(False, "操作已取消；介质状态请在重新检测后确认。")
        if code:
            detail = "\n".join(lines[-8:])
            raise OpticalError(f"xorriso 返回错误（{code}）。请确认光盘可写、未挂载且有操作权限。\n{detail}")
        if callback:
            callback(f"{operation}完成", 100)
        return OperationResult(True, f"{operation}完成")

    def burn(self, device: str, sources: list[Path], volume: str,
             close_disc: bool = True, callback: Progress | None = None,
             burn_mode: str = "CD") -> OperationResult:
        self._validate_device(device)
        if not sources:
            raise OpticalError("刻录队列为空。")
        missing = [str(p) for p in sources if not p.exists()]
        if missing:
            raise OpticalError("源文件不存在：" + "、".join(missing))
        argv = [self.xorriso, "-dev", device, "-volid", safe_volume_label(volume),
                "-joliet", "on", "-rockridge", "on", "-compliance", "no_emul_toc"]
        if burn_mode == "UDF":
            argv += ["-udf", "on"]
        for source in sources:
            argv += ["-map", str(source), "/" + source.name]
        argv += ["-commit"]
        if close_disc:
            argv += ["-close", "on"]
        argv += ["-end"]
        return self._execute(argv, callback, "刻录")

    def erase(self, device: str, full: bool = False,
              callback: Progress | None = None) -> OperationResult:
        self._validate_device(device)
        mode = "all" if full else "fast"
        return self._execute([self.xorriso, "-dev", device, "-blank", mode, "-end"],
                             callback, "完整擦除" if full else "快速擦除")

    def format(self, device: str, volume: str,
               callback: Progress | None = None) -> OperationResult:
        self._validate_device(device)
        # xorriso creates UDF when -udf on precedes an empty commit.
        argv = [self.xorriso, "-dev", device, "-format", "as_needed",
                "-volid", safe_volume_label(volume), "-udf", "on", "-commit", "-end"]
        return self._execute(argv, callback, "建立 UDF 文件系统")

    def copy_to_disc(self, device: str, sources: list[Path],
                     callback: Progress | None = None) -> OperationResult:
        self._validate_device(device)
        argv = [self.xorriso, "-dev", device, "-rockridge", "on", "-joliet", "on", "-udf", "on"]
        for source in sources:
            argv += ["-map", str(source), "/" + source.name]
        argv += ["-commit", "-end"]
        return self._execute(argv, callback, "写入 UDF 光盘")

    def eject(self, device: str) -> OperationResult:
        self._validate_device(device)
        return self._execute([self.xorriso, "-dev", device, "-eject", "all", "-end"],
                             None, "弹出光盘")

    def cancel(self) -> bool:
        with self._lock:
            if self._process and self._process.poll() is None:
                self._cancelled.set()
                self._process.terminate()  # cooperative stop; do not force-reset hardware
                return True
        return False
