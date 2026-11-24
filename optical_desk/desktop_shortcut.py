import ctypes
import sys
from pathlib import Path
from ctypes import wintypes


def desktop_directory() -> Path:
    directory = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    csidl_desktopdirectory = 0x0010
    csidl_flag_create = 0x8000
    result = ctypes.windll.shell32.SHGetFolderPathW(
        None, csidl_desktopdirectory | csidl_flag_create, None, 0, directory
    )
    if result != 0 or not directory.value:
        raise OSError("无法获取当前用户的桌面目录")
    return Path(directory.value)


def ensure_desktop_shortcut(name: str) -> None:
    if not getattr(sys, "frozen", False):
        return
    try:
        from pywintypes import com_error
        from win32com.client import Dispatch
    except ImportError:
        return
    executable = Path(sys.executable).resolve()
    try:
        shortcut_path = desktop_directory() / f"{name}.lnk"
        shortcut = Dispatch("WScript.Shell").CreateShortcut(str(shortcut_path))
        if (shortcut_path.is_file() and shortcut.TargetPath == str(executable)
                and shortcut.WorkingDirectory == str(executable.parent)):
            return
        shortcut.TargetPath = str(executable)
        shortcut.WorkingDirectory = str(executable.parent)
        shortcut.IconLocation = f"{executable},0"
        shortcut.Description = name
        shortcut.Save()
    except (OSError, com_error):
        # A redirected or managed desktop can be unavailable while the app still runs.
        return
