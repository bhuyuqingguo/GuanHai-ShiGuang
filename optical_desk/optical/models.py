from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class DriveInfo:
    recorder_id: str
    name: str
    drive_letters: tuple[str, ...] = ()
    vendor: str = ""
    product: str = ""
    profile: int = 0
    profile_name: str = "未检测到光盘"
    blank: bool = False
    present: bool = False
    writable: bool = False
    erasable: bool = False
    file_system: str = ""
    capacity_bytes: int = 0
    free_bytes: int = 0
    status: str = "请放入光盘"

    @property
    def drive_text(self) -> str:
        return " / ".join(self.drive_letters) if self.drive_letters else "无盘符"

    @property
    def detail(self) -> str:
        return f"{self.drive_text} · {self.profile_name}"


@dataclass(slots=True)
class FileEntry:
    name: str
    path: Path
    is_dir: bool
    size: int = 0
    modified: float = 0.0


@dataclass(slots=True)
class OperationResult:
    ok: bool
    message: str
    details: list[str] = field(default_factory=list)


def format_size(size: int | float) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
