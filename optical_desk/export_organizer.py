from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Iterable

from optical.models import OperationResult

RULES = ("保留原目录", "按资料类型", "按修改月份", "按文件大小", "按扩展名")
TYPE_NAMES = {
    "文档资料": {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".md", ".csv", ".wps"},
    "图片照片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".svg", ".raw"},
    "音视频": {".mp3", ".wav", ".flac", ".ape", ".wma", ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".m4a"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "程序与代码": {".exe", ".msi", ".bat", ".cmd", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs"},
}


def _category(path: Path, stat, rule: str) -> str:
    if rule == "按资料类型":
        return next((name for name, extensions in TYPE_NAMES.items() if path.suffix.casefold() in extensions), "其他文件")
    if rule == "按修改月份":
        return time.strftime("%Y年%m月", time.localtime(stat.st_mtime))
    if rule == "按文件大小":
        size = stat.st_size
        if size < 1024 * 1024:
            return "小于 1 MB"
        if size < 100 * 1024 * 1024:
            return "1–100 MB"
        if size < 1024 * 1024 * 1024:
            return "100 MB–1 GB"
        return "大于 1 GB"
    if rule == "按扩展名":
        return (path.suffix.lstrip(".").upper() or "无扩展名") + " 文件"
    return ""


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def export_organized(sources: Iterable[str | Path], destination: str | Path, rule: str = RULES[0]) -> OperationResult:
    if rule not in RULES:
        return OperationResult(False, "未知的导出整理方式")
    dest = Path(destination)
    copied = []
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for value in sources:
            source = Path(value)
            if rule == RULES[0]:
                target = _unique(dest / source.name)
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
                copied.append(source.name)
                continue
            files = source.rglob("*") if source.is_dir() else (source,)
            for item in files:
                if not item.is_file():
                    continue
                stat = item.stat()
                category = _category(item, stat, rule)
                target_dir = dest / category
                target_dir.mkdir(parents=True, exist_ok=True)
                target = _unique(target_dir / item.name)
                shutil.copy2(item, target)
                copied.append(str(target.relative_to(dest)))
        return OperationResult(True, f"已导出 {len(copied)} 个项目；整理方式：{rule}", copied)
    except Exception as exc:
        return OperationResult(False, f"导出未完成：{exc}", copied)
