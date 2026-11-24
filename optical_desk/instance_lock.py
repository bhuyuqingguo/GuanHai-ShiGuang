from __future__ import annotations

import ctypes
import hashlib
import os

ERROR_ALREADY_EXISTS = 183


class InstanceLock:
    """Windows 命名互斥体：默认实例和每个指定光驱实例各自只能运行一个。"""

    def __init__(self, drive_id: str | None = None):
        identity = (drive_id or "default").strip().casefold()
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        self.name = f"Local\\GuanHaiShiGuang_{digest}"
        self.handle = None
        self.acquired = False

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "无法创建软件实例锁")
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None
            return False
        self.acquired = True
        return True

    def release(self):
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.handle))
        self.handle = None
        self.acquired = False
