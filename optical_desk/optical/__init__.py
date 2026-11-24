"""光盘后端包。Windows 实现使用 IMAPI2，界面不直接依赖 COM。"""

from .models import DriveInfo, FileEntry, OperationResult

__all__ = ["DriveInfo", "FileEntry", "OperationResult"]
