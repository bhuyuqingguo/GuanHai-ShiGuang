import sys
from pathlib import Path

def ensure_desktop_shortcut(name: str) -> None:
    if not getattr(sys, "frozen", False):
        return
    try:
        from pywintypes import com_error
        from win32com.client import Dispatch
        from win32com.shell import shell, shellcon
    except ImportError:
        return
    executable = Path(sys.executable).resolve()
    try:
        desktop = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOPDIRECTORY, None, 0))
        shortcut = Dispatch("WScript.Shell").CreateShortcut(str(desktop / f"{name}.lnk"))
        if (shortcut.TargetPath, shortcut.WorkingDirectory) == (str(executable), str(executable.parent)):
            return
        shortcut.TargetPath = str(executable)
        shortcut.WorkingDirectory = str(executable.parent)
        shortcut.IconLocation = f"{executable},0"
        shortcut.Description = name
        shortcut.Save()
    except (OSError, com_error):
        # A redirected or managed desktop can be unavailable while the app still runs.
        return
