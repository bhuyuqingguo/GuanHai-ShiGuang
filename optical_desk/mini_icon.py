from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

from monitor_utils import (monitor_rects, primary_rect, rect_contains,
                           window_has_visible_monitor)

SETTINGS = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OpticalDesk" / "settings.json"


class DesktopMiniIcon:
    """主面板收起后的桌面入口；单击恢复，可拖拽换位，右键彻底退出。"""

    DRAG_THRESHOLD = 6  # 像素，超过才算拖拽，避免误触恢复

    def __init__(self, app, image_path: str):
        self.app = app
        self.window = None
        self.image_path = image_path
        self._press = None
        self._last = None
        self._dragging = False

    # ---------- 位置持久化 ----------

    @staticmethod
    def _load_position():
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8"))
            pos = data.get("mini_icon_pos")
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                return int(pos[0]), int(pos[1])
        except (OSError, ValueError, TypeError):
            pass
        return None

    @staticmethod
    def _save_position(x: int, y: int):
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            except (OSError, ValueError, TypeError):
                data = {}
            data["mini_icon_pos"] = [int(x), int(y)]
            SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _default_position(self):
        """主面板所在屏幕（取不到则用主屏）的右侧边缘。"""
        app = self.app
        scale = app.ui_scale
        size = self.window.winfo_width() or int(72 * scale)
        rects = monitor_rects()
        rect = None
        if rects:
            root = app.root
            rect = next((r for r in rects if rect_contains(r, root.winfo_x() + root.winfo_width() // 2,
                                                          root.winfo_y() + root.winfo_height() // 2)), None)
            if rect is None:
                rect = primary_rect(rects) or rects[0]
        if rect is None:
            rect = (0, 0, self.window.winfo_screenwidth(), self.window.winfo_screenheight())
        x = rect[2] - size - int(20 * scale)
        y = max(rect[1] + int(90 * scale),
                min(app.root.winfo_y(), rect[3] - size - int(90 * scale)))
        return x, y

    def recover(self, rects=None):
        """屏幕变化后：若图标不在任何屏幕内，回到当前屏幕右侧边缘。"""
        if not self.window or not self.window.winfo_exists():
            return
        rects = rects if rects is not None else monitor_rects()
        if rects and window_has_visible_monitor(rects, self.window.winfo_x(), self.window.winfo_y(),
                                                self.window.winfo_width(), self.window.winfo_height()):
            return
        x, y = self._default_position()
        self.window.geometry(f"+{x}+{y}")
        self._save_position(x, y)

    # ---------- 窗口 ----------

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            return
        app = self.app
        window = tk.Toplevel(app.root)
        self.window = window
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg="#D6B56C")
        scale = app.ui_scale
        size = int(72 * scale)
        window.geometry(f"{size}x{size}+0+0")
        window.update_idletasks()
        saved = self._load_position()
        if saved:
            rects = monitor_rects()
            if not rects or window_has_visible_monitor(rects, saved[0], saved[1], size, size):
                x, y = saved
            else:
                x, y = self._default_position()
        else:
            x, y = self._default_position()
        window.geometry(f"{size}x{size}+{x}+{y}")
        image = tk.PhotoImage(file=self.image_path)
        label = tk.Label(window, image=image, bg="#19211F", cursor="fleur", bd=0)
        label.image = image
        label.pack(fill="both", expand=True, padx=2, pady=2)
        label.bind("<Button-1>", self._on_press)
        label.bind("<B1-Motion>", self._on_motion)
        label.bind("<ButtonRelease-1>", self._on_release)
        label.bind("<Button-3>", self._show_menu)
        label.bind("<Enter>", lambda _e: None if self._dragging else window.configure(bg="#F0CD7A"))
        label.bind("<Leave>", lambda _e: None if self._dragging else window.configure(bg="#D6B56C"))
        window.bind("<Button-3>", self._show_menu)
        window.protocol("WM_DELETE_WINDOW", app.restore)
        if DND_FILES:
            window.drop_target_register(DND_FILES)
            window.dnd_bind("<<DragEnter>>", self._drag_enter)
            window.dnd_bind("<<DragLeave>>", self._drag_leave)
            window.dnd_bind("<<Drop>>", self._drop)

    # ---------- 拖拽 ----------

    def _on_press(self, event):
        self._press = (event.x_root, event.y_root)
        self._last = (event.x_root, event.y_root)
        self._dragging = False

    def _on_motion(self, event):
        if not self._press or not self.window or not self.window.winfo_exists():
            return
        last = self._last or self._press
        dx = event.x_root - last[0]
        dy = event.y_root - last[1]
        if not self._dragging:
            total = abs(event.x_root - self._press[0]) + abs(event.y_root - self._press[1])
            if total < self.DRAG_THRESHOLD:
                return
            self._dragging = True
            self.window.configure(bg="#5EEAD4")
        self.window.geometry(f"+{self.window.winfo_x() + dx}+{self.window.winfo_y() + dy}")
        self._last = (event.x_root, event.y_root)

    def _on_release(self, _event):
        if not self._press:
            return
        dragged = self._dragging
        self._press = None
        self._last = None
        self._dragging = False
        if not self.window or not self.window.winfo_exists():
            return
        self.window.configure(bg="#D6B56C")
        if dragged:
            self._save_position(self.window.winfo_x(), self.window.winfo_y())
        else:
            self.app.restore()

    # ---------- 右键菜单 ----------

    def _show_menu(self, event):
        """右键不再直接退出，而是给出选项；彻底退出只是其中一个选项。"""
        if not self.window or not self.window.winfo_exists():
            return
        app = self.app
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="打开观海·拾光", command=app.restore)
        menu.add_command(label="重新检测光驱（F5）", command=lambda: (app.restore(), app.refresh()))
        menu.add_separator()
        menu.add_command(label="彻底退出观海·拾光", command=app.force_close)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ---------- 文件拖入 ----------

    def _drag_enter(self, _event=None):
        if self.window:
            self.window.configure(bg="#5EEAD4")

    def _drag_leave(self, _event=None):
        if self.window:
            self.window.configure(bg="#D6B56C")

    def _drop(self, event):
        paths = [Path(item) for item in self.app.root.tk.splitlist(event.data)]
        self.app._add_sources(paths)
        self.app.current_tab = "burn"
        if self.window:
            self.window.configure(bg="#5EEAD4")
            self.window.after(900, self._drag_leave)
        return event.action

    def hide(self):
        if self.window and self.window.winfo_exists():
            self.window.withdraw()

    def destroy(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
