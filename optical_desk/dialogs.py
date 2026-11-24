from __future__ import annotations

import tkinter as tk

BG = "#0B1220"
PANEL = "#121E2F"
PANEL_2 = "#1A2A3F"
TEXT = "#EDF4FF"
MUTED = "#8FA3BA"
ACCENT_DARK = "#0F766E"
DANGER = "#FB7185"
FONT = "Microsoft YaHei UI"


class Dialogs:
    """软件自有提示统一贴近右侧悬浮面板，而不是跳到屏幕中央。"""

    def _show(self, title, message, parent=None, buttons=(("确定", True),), danger=False):
        parent = parent.winfo_toplevel() if parent is not None else None
        window = tk.Toplevel(parent)
        window.title(title)
        window.configure(bg=BG)
        window.resizable(False, False)
        if parent is not None:
            window.transient(parent)
        scale = max(1.0, window.winfo_fpixels("1i") / 96.0)
        width = int(430 * scale)
        body = tk.Frame(window, bg=PANEL, padx=22, pady=20,
                        highlightbackground="#23344A", highlightthickness=1)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title, bg=PANEL, fg=DANGER if danger else TEXT,
                 font=(FONT, 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text=message, bg=PANEL, fg=MUTED, justify="left",
                 wraplength=width - int(44 * scale), anchor="w",
                 font=(FONT, 9)).pack(fill="x", pady=(14, 22))
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x")
        result = False

        def choose(value):
            nonlocal result
            result = value
            window.destroy()

        for text, value in reversed(buttons):
            tk.Button(row, text=text, command=lambda v=value: choose(v),
                      bg=ACCENT_DARK if value else PANEL_2, fg="#FFFFFF",
                      activebackground="#0D9488", activeforeground="#FFFFFF",
                      relief="flat", bd=0, padx=18, pady=8,
                      font=(FONT, 9)).pack(side="right", padx=(8, 0))
        window.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        window.bind("<Escape>", lambda _e: choose(False))
        window.update_idletasks()
        if parent is not None:
            x = parent.winfo_x() - window.winfo_width() - int(14 * scale)
            if x < 0:
                x = parent.winfo_x() + (parent.winfo_width() - window.winfo_width()) // 2
            y = parent.winfo_y() + min(int(120 * scale), max(0, parent.winfo_height() // 4))
        else:
            x = window.winfo_screenwidth() - window.winfo_width() - int(30 * scale)
            y = int(100 * scale)
        x = max(0, min(x, window.winfo_screenwidth() - window.winfo_width()))
        y = max(0, min(y, window.winfo_screenheight() - window.winfo_height()))
        window.geometry(f"+{x}+{y}")
        window.grab_set()
        window.wait_window()
        return result

    def showinfo(self, title, message, parent=None, **kwargs):
        self._show(title, message, parent)

    def showwarning(self, title, message, parent=None, **kwargs):
        self._show(title, message, parent)

    def showerror(self, title, message, parent=None, **kwargs):
        self._show(title, message, parent, danger=True)

    def askyesno(self, title, message, parent=None, **kwargs):
        return bool(self._show(title, message, parent, (("否", False), ("是", True))))

    def askokcancel(self, title, message, parent=None, **kwargs):
        return bool(self._show(title, message, parent, (("取消", False), ("确定", True))))

    def choose(self, title, message, choices, parent=None):
        """返回用户点选的选项值；关闭窗口返回 False。"""
        return self._show(title, message, parent, choices)
