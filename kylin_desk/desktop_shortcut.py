import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile


def desktop_directory() -> Path:
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        lines = (config / "user-dirs.dirs").read_text(encoding="utf-8").splitlines()
        for line in lines:
            key, _, value = line.partition("=")
            if key.strip() == "XDG_DESKTOP_DIR":
                path, = shlex.split(value, comments=True)
                path = Path(os.path.expandvars(path))
                if path.is_absolute():
                    return path
    except (OSError, ValueError):
        pass
    return Path.home() / "Desktop"


def desktop_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def exec_argument(path: Path) -> str:
    escaped = str(path).replace("%", "%%")
    for character in ('\\', '"', '`', '$'):
        escaped = escaped.replace(character, "\\" + character)
    return desktop_value(f'"{escaped}"')


def ensure_desktop_shortcut(icon: Path) -> None:
    if not getattr(sys, "frozen", False):
        return
    executable = Path(sys.executable).resolve()
    desktop = desktop_directory()
    shortcut = desktop / "GuanHaiShiGuang.desktop"
    contents = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=观海·拾光\n"
        f"Exec={exec_argument(executable)}\n"
        f"Icon={desktop_value(str(icon))}\n"
        "Terminal=false\n"
        "StartupWMClass=GuanHaiShiGuang\n"
    )
    try:
        if shortcut.read_text(encoding="utf-8") == contents and os.access(shortcut, os.X_OK):
            return
    except (OSError, UnicodeError):
        pass

    desktop.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=desktop, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(contents)
            stream.close()
            temporary.chmod(0o755)
            temporary.replace(shortcut)
        finally:
            temporary.unlink(missing_ok=True)

    gio = shutil.which("gio")
    if gio:
        environment = os.environ.copy()
        original_library_path = environment.pop("LD_LIBRARY_PATH_ORIG", None)
        if original_library_path is None:
            environment.pop("LD_LIBRARY_PATH", None)
        else:
            environment["LD_LIBRARY_PATH"] = original_library_path
        subprocess.run([gio, "set", str(shortcut), "metadata::trusted", "true"],
                       env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False, timeout=2)
