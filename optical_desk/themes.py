from __future__ import annotations

import json
import os
import sys
from pathlib import Path

THEMES = {
    "classic": {
        "name": "古典 · 黛金", "description": "黛色为底，鎏金作光，沉静书卷气",
        "BG": "#101515", "PANEL": "#19211F", "PANEL_2": "#26332D", "PANEL_HOVER": "#34453C",
        "TEXT": "#F2E8D5", "MUTED": "#B0A58F", "ACCENT": "#D6B56C", "ACCENT_DARK": "#79613A",
        "DANGER": "#D88A80", "SUCCESS": "#8DB9A2", "BORDER": "#3B4438",
    },
    "modern": {
        "name": "现代 · 沐青", "description": "简洁墨青，清晰克制，适合长时间使用",
        "BG": "#0B1220", "PANEL": "#121E2F", "PANEL_2": "#1A2A3F", "PANEL_HOVER": "#223650",
        "TEXT": "#EDF4FF", "MUTED": "#8FA3BA", "ACCENT": "#5EEAD4", "ACCENT_DARK": "#0F766E",
        "DANGER": "#FB7185", "SUCCESS": "#5EEAD4", "BORDER": "#23344A",
    },
    "tech": {
        "name": "科技 · 深蓝", "description": "深海蓝与澄明蓝光，冷静而精准",
        "BG": "#07101F", "PANEL": "#0D1B30", "PANEL_2": "#142944", "PANEL_HOVER": "#1D3A5C",
        "TEXT": "#E8F2FF", "MUTED": "#83A6CA", "ACCENT": "#60A5FA", "ACCENT_DARK": "#1D4F91",
        "DANGER": "#FB7185", "SUCCESS": "#67E8F9", "BORDER": "#1C3A5B",
    },
    "future": {
        "name": "未来 · 星紫", "description": "夜幕紫与微星光，轻盈但不眩目",
        "BG": "#110D1D", "PANEL": "#1B152B", "PANEL_2": "#29203E", "PANEL_HOVER": "#3A2D55",
        "TEXT": "#F1EBFF", "MUTED": "#AA9CC8", "ACCENT": "#C4B5FD", "ACCENT_DARK": "#6D4BA1",
        "DANGER": "#F38BA8", "SUCCESS": "#A7F3D0", "BORDER": "#3B2C55",
    },
    "cute": {
        "name": "可爱 · 桃夭", "description": "柔和桃粉与奶油白，温暖亲近",
        "BG": "#21151C", "PANEL": "#2E1D27", "PANEL_2": "#442B39", "PANEL_HOVER": "#5B3849",
        "TEXT": "#FFF0F4", "MUTED": "#D2A9B7", "ACCENT": "#F9A8C5", "ACCENT_DARK": "#9E506F",
        "DANGER": "#FB7185", "SUCCESS": "#A7E3CF", "BORDER": "#543342",
    },
    "nature": {
        "name": "自然 · 竹青", "description": "竹叶青与米白，淡雅舒展",
        "BG": "#101B18", "PANEL": "#182A24", "PANEL_2": "#253C32", "PANEL_HOVER": "#345344",
        "TEXT": "#EDF3E7", "MUTED": "#A2B6A4", "ACCENT": "#A7C957", "ACCENT_DARK": "#4F703E",
        "DANGER": "#E5988F", "SUCCESS": "#A7C957", "BORDER": "#334A3C",
    },
}
COLOR_KEYS = ("BG", "PANEL", "PANEL_2", "PANEL_HOVER", "TEXT", "MUTED", "ACCENT", "ACCENT_DARK", "DANGER", "SUCCESS", "BORDER")
SETTINGS = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OpticalDesk" / "settings.json"


def load_theme() -> str:
    try:
        value = json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "classic")
        return value if value in THEMES else "classic"
    except (OSError, ValueError, TypeError):
        return "classic"


def save_theme(key: str) -> None:
    if key not in THEMES:
        return
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data["theme"] = key
    SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_theme(key: str, main_globals=None) -> None:
    palette = THEMES.get(key, THEMES["classic"])
    targets = [main_globals] if main_globals is not None else []
    targets.extend(vars(sys.modules[name]) for name in ("secure_ui", "blank_wizard", "dialogs", "help_window") if name in sys.modules)
    for target in targets:
        for field in COLOR_KEYS:
            if field in palette:
                target[field] = palette[field]
