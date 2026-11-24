from __future__ import annotations

import tkinter as tk
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None


class DesktopMiniIcon:
    """主面板收起后的桌面入口；单击恢复，右键彻底退出。"""

    def __init__(self, app, image_path: str):
        self.app = app
        self.window = None
        self.image_path = image_path

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
        x = window.winfo_screenwidth() - size - int(20 * scale)
        y = max(int(90 * scale), min(app.root.winfo_y(), window.winfo_screenheight() - size - int(90 * scale)))
        window.geometry(f"{size}x{size}+{x}+{y}")
        image = tk.PhotoImage(file=self.image_path)
        label = tk.Label(window, image=image, bg="#19211F", cursor="hand2", bd=0)
        label.image = image
        label.pack(fill="both", expand=True, padx=2, pady=2)
        label.bind("<Button-1>", lambda _e: app.restore())
        label.bind("<Button-3>", lambda _e: app.force_close())
        label.bind("<Enter>", lambda _e: window.configure(bg="#F0CD7A"))
        label.bind("<Leave>", lambda _e: window.configure(bg="#D6B56C"))
        window.protocol("WM_DELETE_WINDOW", app.restore)
        if DND_FILES:
            window.drop_target_register(DND_FILES)
            window.dnd_bind("<<DragEnter>>", self._drag_enter)
            window.dnd_bind("<<DragLeave>>", self._drag_leave)
            window.dnd_bind("<<Drop>>", self._drop)

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
