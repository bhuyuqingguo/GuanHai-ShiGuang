from __future__ import annotations

import ctypes
import datetime as dt
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from optical.history import HistoryStore
from optical.models import DriveInfo, FileEntry, OperationResult, format_size
from optical.windows_imapi import DiscService, dependency_message
from blank_wizard import BlankDiscWizard
from dialogs import Dialogs
from help_window import HelpWindow
from mini_icon import DesktopMiniIcon
from tray_icon import TrayIcon
from secure_ui import SecureTransferPage
from splash import StartupSplash
from themes import THEMES, apply_theme, load_theme, save_theme

messagebox = Dialogs()

APP_NAME = "观海·拾光"
APP_VERSION = "0.0.5"
APP_SUBTITLE = "GUANHAI · SHIGUANG · 光盘读写中枢"


def resource_path(filename: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / filename)
BG = "#0B1220"
PANEL = "#121E2F"
PANEL_2 = "#1A2A3F"
PANEL_HOVER = "#223650"
TEXT = "#EDF4FF"
MUTED = "#8FA3BA"
ACCENT = "#5EEAD4"
ACCENT_DARK = "#0F766E"
DANGER = "#FB7185"
SUCCESS = "#5EEAD4"
BORDER = "#23344A"
FONT = "Microsoft YaHei UI"


class Button(tk.Button):
    def __init__(self, master, text, command, kind="secondary", **kwargs):
        colors = {
            "primary": (ACCENT_DARK, "#FFFFFF", "#0D9488"),
            "secondary": (PANEL_2, TEXT, PANEL_HOVER),
            "danger": ("#422635", "#FECDD3", "#71324A"),
            "ghost": (BG, MUTED, PANEL_2),
        }
        bg, fg, active = colors[kind]
        options = {"font": (FONT, 9), "padx": 9, "pady": 8}
        options.update(kwargs)
        super().__init__(master, text=text, command=command, bg=bg, fg=fg,
                         activebackground=active, activeforeground="#FFFFFF",
                         relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                         **options)


class DiscBrowser(tk.Toplevel):
    """完整盘内文件管理器：目录导航、搜索、打开和导出均不依赖资源管理器。"""

    def __init__(self, app: "YaoKeApp", recorder_id: str):
        super().__init__(app.root)
        self.app = app
        self.service = app.service
        self.recorder_id = recorder_id
        self.relative = ""
        self.all_entries: list[FileEntry] = []
        self.entries: list[FileEntry] = []
        self.title("观海·拾光 · 光盘文件")
        scale = app.ui_scale
        width, height = int(820 * scale), int(560 * scale)
        x = app.root.winfo_x() - width - int(14 * scale)
        if x < 0:
            x = app.root.winfo_x()
        y = max(0, min(app.root.winfo_y(), app.root.winfo_screenheight() - height))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(int(620 * scale), int(420 * scale))
        self.configure(bg=BG)
        self.transient(app.root)

        header = tk.Frame(self, bg=BG, padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="光盘文件", bg=BG, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(side="left")
        Button(header, "整盘导出 Ctrl+Shift+E", self.export_disc, "primary").pack(side="right")
        Button(header, "导出选中 Ctrl+E", self.export_selected).pack(side="right", padx=8)

        navigation = tk.Frame(self, bg=BG, padx=18)
        navigation.pack(fill="x", pady=(0, 12))
        Button(navigation, "← 上级 Backspace", self.go_up, "ghost").pack(side="left")
        self.path_label = tk.Label(navigation, text="光盘根目录", bg=BG, fg=MUTED,
                                   font=(FONT, 9))
        self.path_label.pack(side="left", padx=10)
        search_box = tk.Frame(navigation, bg=PANEL_2, padx=9, pady=5)
        search_box.pack(side="right")
        tk.Label(search_box, text="搜索", bg=PANEL_2, fg=MUTED, font=(FONT, 8)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        search = tk.Entry(search_box, textvariable=self.search_var, width=22,
                          bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat",
                          font=(FONT, 9))
        search.pack(side="left", padx=(7, 0))

        body = tk.Frame(self, bg=BG, padx=18)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("size", "modified"), show="tree headings",
                                 selectmode="extended")
        self.tree.heading("#0", text="名称")
        self.tree.heading("size", text="大小")
        self.tree.heading("modified", text="修改时间")
        self.tree.column("#0", width=440)
        self.tree.column("size", width=110, anchor="e")
        self.tree.column("modified", width=150, anchor="center")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.open_selected)
        self.tree.bind("<Control-a>", self.select_all)
        self.tree.bind("<F5>", lambda _e: self.load())
        self.bind("<BackSpace>", lambda _e: self.go_up())
        self.bind("<Return>", self.open_selected)
        self.bind("<Control-e>", lambda _e: self.export_selected())
        self.bind("<Control-E>", lambda _e: self.export_disc())

        footer = tk.Frame(self, bg=BG, padx=18, pady=12)
        footer.pack(fill="x")
        self.status = tk.Label(footer, text="正在读取…", bg=BG, fg=MUTED,
                               anchor="w", font=(FONT, 8))
        self.status.pack(side="left", fill="x", expand=True)
        Button(footer, "全选 Ctrl+A", self.select_all, "ghost", pady=4).pack(side="right")
        Button(footer, "刷新 F5", self.load, "ghost", pady=4).pack(side="right", padx=6)
        self.load()

    def load(self):
        if getattr(self, "_loading", False):
            return
        self._loading = True
        relative = self.relative
        self.status.config(text="正在后台读取光盘目录，界面仍可操作…")

        def worker():
            try:
                result = self.service.list_files(self.recorder_id, relative)
                self.after(0, lambda: self._load_done(relative, result, None))
            except Exception as exc:
                self.after(0, lambda: self._load_done(relative, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _load_done(self, relative, entries, error):
        self._loading = False
        if not self.winfo_exists() or relative != self.relative:
            return
        if error:
            self.status.config(text=error)
            messagebox.showerror(APP_NAME, error, parent=self)
            return
        self.all_entries = entries
        self.path_label.config(text=relative or "光盘根目录")
        self.apply_filter()

    def apply_filter(self):
        keyword = self.search_var.get().strip().casefold()
        self.entries = [e for e in self.all_entries if keyword in e.name.casefold()] if keyword else list(self.all_entries)
        self.tree.delete(*self.tree.get_children())
        for index, entry in enumerate(self.entries):
            kind = "[文件夹]" if entry.is_dir else "[文件]"
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.modified)) if entry.modified else "—"
            self.tree.insert("", "end", iid=str(index), text=f"{kind}  {entry.name}",
                             values=("—" if entry.is_dir else format_size(entry.size), modified))
        total = sum(e.size for e in self.entries if not e.is_dir)
        self.status.config(text=f"{len(self.entries)} 个项目 · 当前目录文件 {format_size(total)} · 双击打开")

    def go_up(self):
        if not self.relative:
            return
        self.relative = str(Path(self.relative).parent)
        if self.relative == ".":
            self.relative = ""
        self.search_var.set("")
        self.load()

    def open_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        entry = self.entries[int(selection[0])]
        if entry.is_dir:
            self.relative = str(Path(self.relative) / entry.name) if self.relative else entry.name
            self.search_var.set("")
            self.load()
        else:
            try:
                os.startfile(str(entry.path))
            except OSError as exc:
                messagebox.showerror(APP_NAME, str(exc), parent=self)

    def select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def export_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "请先选择要导出的文件或文件夹。", parent=self)
            return
        destination = filedialog.askdirectory(title="选择导出位置", parent=self)
        if not destination:
            return
        sources = [self.entries[int(i)].path for i in selection]
        self.app.run_task("导出文件", lambda: self.service.export_files(sources, destination))

    def export_disc(self):
        destination = filedialog.askdirectory(title="选择整盘导出位置", parent=self)
        if destination:
            self.app.run_task("整盘导出", lambda: self.service.export_disc(self.recorder_id, destination))


def enable_dpi_awareness():
    """在创建任何窗口前启用 Per-Monitor V2，禁止系统位图拉伸。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


class YaoKeApp:
    def __init__(self):
        enable_dpi_awareness()
        self.theme_key = load_theme()
        apply_theme(self.theme_key, globals())
        root_class = TkinterDnD.Tk if TkinterDnD else tk.Tk
        self.root = root_class()
        self.root.tk.call("tk", "scaling", self.root.winfo_fpixels("1i") / 72.0)
        self.ui_scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BORDER)
        self.service = DiscService()
        self.history = HistoryStore()
        self.tray = TrayIcon(resource_path("discore.ico"), APP_NAME, self.restore, self.force_close)
        self.mini_icon = DesktopMiniIcon(self, resource_path("discore_64.png"))
        self.drives: list[DriveInfo] = []
        self.selected_drive: DriveInfo | None = None
        self.sources: list[Path] = []
        self.busy = False
        self.refreshing = False
        self.events: queue.Queue = queue.Queue()
        self.topmost = True
        self.minimized = False
        self.current_tab = "disc"
        self.burn_mode = "CD"
        self.last_progress = None
        self._drag_origin = (0, 0)
        self._refresh_timer = None
        self._tally_after = None
        self._tally_lit = False
        self._place_right()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda _e: self.close())
        self.root.bind("<Map>", self._restored)
        self.splash = StartupSplash(self.root, resource_path("discore_512.png"), self._complete_startup,
                                    sound_path=resource_path("startup_chime.wav"))

    def _complete_startup(self):
        self._build_style()
        self._build_ui()
        self.root.after(100, self.refresh)
        self.root.after(100, self._poll_events)
        self._bind_shortcuts()
        message = dependency_message()
        if message:
            self.root.after(300, lambda: messagebox.showwarning(APP_NAME, message, parent=self.root))

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2,
                        foreground=TEXT, arrowcolor=ACCENT, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, padding=8)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_2)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", PANEL_2)])
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL_2, background=ACCENT,
                        bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT, thickness=5)
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, rowheight=30, bordercolor=BORDER,
                        font=(FONT, 9))
        style.configure("Treeview.Heading", background=PANEL_2, foreground=TEXT,
                        relief="flat", font=(FONT, 9, "bold"), padding=5)
        style.map("Treeview", background=[("selected", ACCENT_DARK)])

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BG, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        header = tk.Frame(outer, bg=BG, height=76, padx=17)
        header.pack(fill="x")
        header.pack_propagate(False)
        for widget in (header,):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._snap_right)

        self.logo_image = tk.PhotoImage(file=resource_path("discore_64.png"))
        self.tally_image = tk.PhotoImage(file=resource_path("discore_tally.png"))
        self.tally_dim_image = tk.PhotoImage(file=resource_path("discore_tally_dim.png"))
        self.root.iconphoto(True, self.logo_image)
        self.logo_label = tk.Label(header, image=self.logo_image, bg=BG, bd=0)
        self.logo_label.pack(side="left", pady=6)
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", padx=9, pady=15)
        tk.Label(brand, text="观海·拾光", bg=BG, fg=TEXT, font=(FONT, 15, "bold")).pack(anchor="w")
        tk.Label(brand, text=f"GUANHAI · SHIGUANG · v{APP_VERSION}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 7)).pack(anchor="w", pady=(2, 0))
        close = tk.Label(header, text="×", bg=BG, fg=MUTED, font=("Arial", 20), cursor="hand2")
        close.pack(side="right", padx=(10, 0), pady=15)
        close.bind("<Button-1>", lambda _e: self.close())
        close.bind("<Button-3>", lambda _e: self.force_close())
        self.pin_label = tk.Button(header, text="● 已置顶  Ctrl+P", command=self.toggle_topmost,
                                   bg=ACCENT_DARK, fg="#FFFFFF", activebackground="#0D9488",
                                   activeforeground="#FFFFFF", relief="flat", bd=0,
                                   highlightthickness=0, cursor="hand2", padx=8, pady=5,
                                   font=(FONT, 8, "bold"))
        self.pin_label.pack(side="right", pady=20)
        help_button = tk.Button(header, text="?  F1", command=self.show_help,
                                bg=PANEL_2, fg=ACCENT, activebackground=PANEL_HOVER,
                                activeforeground=TEXT, relief="flat", bd=0, highlightthickness=0,
                                cursor="hand2", padx=8, pady=5, font=(FONT, 8, "bold"))
        help_button.pack(side="right", padx=(0, 6), pady=20)

        drive_row = tk.Frame(outer, bg=BG, padx=17)
        drive_row.pack(fill="x", pady=(0, 11))
        self.drive_box = ttk.Combobox(drive_row, state="readonly", font=(FONT, 10))
        self.drive_box.pack(side="left", fill="x", expand=True)
        self.drive_box.bind("<<ComboboxSelected>>", self._select_drive)
        Button(drive_row, "刷新 F5", self.refresh, "ghost", font=(FONT, 9)).pack(side="right", padx=(7, 0))

        tabs = tk.Frame(outer, bg=PANEL, padx=4, pady=4)
        tabs.pack(fill="x", padx=17, pady=(0, 12))
        self.tab_buttons = {}
        for key, label in (("disc", "光盘\nCtrl+1"), ("burn", "刻录\nCtrl+2"),
                           ("secure", "交接\nCtrl+3"), ("history", "历史\nCtrl+4")):
            button = Button(tabs, label, lambda k=key: self.show_tab(k), "ghost", pady=7,
                            font=(FONT, 10, "bold"), justify="center")
            button.pack(side="left", fill="x", expand=True, padx=2)
            self.tab_buttons[key] = button

        self.content = tk.Frame(outer, bg=BG, padx=17)
        self.content.pack(fill="both", expand=True)
        self.pages = {key: tk.Frame(self.content, bg=BG) for key in ("disc", "burn", "secure", "history")}
        self._build_disc_page()
        self._build_burn_page()
        self.secure_page = SecureTransferPage(self, self.pages["secure"])
        self._build_history_page()

        footer = tk.Frame(outer, bg=BG, padx=17, pady=11)
        footer.pack(fill="x", side="bottom")
        progress_text = tk.Frame(footer, bg=BG)
        progress_text.pack(fill="x")
        self.progress_label = tk.Label(progress_text, text="就绪", bg=BG, fg=MUTED,
                                       font=(FONT, 8), anchor="w")
        self.progress_label.pack(side="left", fill="x", expand=True)
        self.progress_percent = tk.Label(progress_text, text="", bg=BG, fg=ACCENT,
                                         font=("Segoe UI", 12, "bold"), width=6, anchor="e")
        self.progress_percent.pack(side="right")
        progress_row = tk.Frame(footer, bg=BG)
        progress_row.pack(fill="x", pady=(6, 0))
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        self.cancel_button = Button(progress_row, "取消  Ctrl+.", self.cancel, "ghost", pady=2)
        self.cancel_button.pack(side="right", padx=(8, 0))
        self.show_tab("disc")
        self._tally_after = self.root.after(500, self._pulse_tally)

    def _section_title(self, page, title, hint=""):
        row = tk.Frame(page, bg=BG)
        row.pack(fill="x", pady=(0, 7))
        tk.Label(row, text=title, bg=BG, fg=TEXT, font=(FONT, 9, "bold")).pack(side="left")
        if hint:
            tk.Label(row, text=hint, bg=BG, fg=MUTED, font=(FONT, 8)).pack(side="right")

    def _build_disc_page(self):
        page = self.pages["disc"]
        self._section_title(page, "当前介质", "自动检测 · F5")
        card = tk.Frame(page, bg=PANEL, padx=15, pady=12,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")
        self.media_label = tk.Label(card, text="正在检测光盘…", bg=PANEL, fg=TEXT,
                                    font=(FONT, 13, "bold"), anchor="w")
        self.media_label.pack(fill="x")
        self.profile_label = tk.Label(card, text="—", bg=PANEL, fg=MUTED,
                                      font=(FONT, 10), anchor="w")
        self.profile_label.pack(fill="x", pady=(6, 10))
        self.space_bar = ttk.Progressbar(card, mode="determinate", maximum=100)
        self.space_bar.pack(fill="x")
        self.space_label = tk.Label(card, text="容量 —", bg=PANEL, fg=MUTED,
                                    font=(FONT, 9), anchor="w")
        self.space_label.pack(fill="x", pady=(7, 0))

        skin_row = tk.Frame(page, bg=BG)
        skin_row.pack(fill="x", pady=9)
        tk.Label(skin_row, text="面板皮肤", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self.theme_names = [palette["name"] for palette in THEMES.values()]
        self.theme_keys = list(THEMES)
        self.theme_box = ttk.Combobox(skin_row, state="readonly", values=self.theme_names,
                                      font=(FONT, 9), width=15)
        self.theme_box.current(self.theme_keys.index(self.theme_key))
        self.theme_box.pack(side="left", fill="x", expand=True, padx=8)
        self.theme_box.bind("<<ComboboxSelected>>", self._select_theme)
        Button(skin_row, "换一套 Ctrl+T", self.next_theme, "ghost", font=(FONT, 8)).pack(side="right")

        self._section_title(page, "读取与管理", "大按钮 · 快捷键直达")
        actions = tk.Frame(page, bg=BG)
        actions.pack(fill="x", pady=(0, 10))
        large = {"font": (FONT, 10, "bold"), "pady": 11}
        Button(actions, "读取光盘  Ctrl+R", self.browse, "primary", **large).grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 7))
        Button(actions, "整盘导出  Ctrl+E", self.export_disc, **large).grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 7))
        Button(actions, "加入刻录  Ctrl+O", self.add_files, **large).grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(0, 7))
        Button(actions, "制作交接包  Ctrl+3", lambda: self.show_tab("secure"), **large).grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(0, 7))
        Button(actions, "弹出光盘  Ctrl+J", self.eject, **large).grid(row=2, column=0, sticky="ew", padx=(0, 5))
        Button(actions, "重新检测  F5", self.refresh, **large).grid(row=2, column=1, sticky="ew", padx=(5, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self._section_title(page, "介质维护", "谨慎操作")
        manage = tk.Frame(page, bg=PANEL, padx=10, pady=9,
                          highlightbackground=BORDER, highlightthickness=1)
        manage.pack(fill="x")
        maintenance = {"font": (FONT, 10), "pady": 9}
        Button(manage, "快速擦除  Ctrl+Shift+X", self.erase, "danger", **maintenance).pack(fill="x")
        Button(manage, "深度擦除  Ctrl+Shift+D", self.deep_format, "danger", **maintenance).pack(fill="x", pady=(7, 0))
        Button(manage, "建立 Windows 文件目录  Ctrl+Shift+F", self.format_disc, "primary", **maintenance).pack(fill="x", pady=(7, 0))

    def _build_burn_page(self):
        page = self.pages["burn"]
        self._section_title(page, "新建刻录", "空白 CD 优先")
        self.drop_zone = tk.Canvas(page, height=int(112 * self.ui_scale), bg=PANEL, highlightthickness=0, cursor="hand2")
        self.drop_zone.pack(fill="x")
        self.drop_border = self.drop_zone.create_rectangle(2, 2, 380, 110, outline=ACCENT_DARK,
                                                           width=2)
        self.drop_title = self.drop_zone.create_text(190, 38, text="把文件或文件夹拖到这里",
                                                      fill=TEXT, font=(FONT, 12, "bold"))
        self.drop_hint = self.drop_zone.create_text(190, 70, text="或点击选择文件 · 可多次拖入",
                                                     fill=MUTED, font=(FONT, 9))
        self.drop_zone.create_text(190, 92, text="默认使用标准光盘模式，其他电脑也能读取",
                                   fill=ACCENT, font=(FONT, 8))
        self.drop_zone.bind("<Button-1>", lambda _e: self.add_files())
        self.drop_zone.bind("<Configure>", self._resize_drop_zone)
        if DND_FILES:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_zone.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.drop_zone.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        name_area = tk.Frame(page, bg=BG)
        name_area.pack(fill="x", pady=9)
        name_header = tk.Frame(name_area, bg=BG)
        name_header.pack(fill="x", pady=(0, 6))
        tk.Label(name_header, text="光盘名称", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self.auto_date_var = tk.BooleanVar(value=getattr(self, "_auto_date", True))
        tk.Checkbutton(name_header, text="自动带当天日期", variable=self.auto_date_var,
                       command=self._update_volume_name, bg=BG, fg=MUTED, selectcolor=PANEL_2,
                       activebackground=BG, activeforeground=TEXT, highlightthickness=0,
                       font=(FONT, 8)).pack(side="right")
        self.volume_base = getattr(self, "volume_base", "观海拾光")
        self.volume_var = tk.StringVar()
        self.volume_presets = ("观海拾光", "工作资料", "文件交接", "重要备份", "项目归档", "照片留念", "音乐精选")
        self.volume_tags = {}
        tags = tk.Frame(name_area, bg=BG)
        tags.pack(fill="x")
        for index, name in enumerate(self.volume_presets):
            tag = Button(tags, name, lambda n=name: self.select_volume_tag(n), "secondary",
                         font=(FONT, 8), padx=4, pady=5)
            tag.grid(row=index // 4, column=index % 4, sticky="ew", padx=2, pady=2)
            self.volume_tags[name] = tag
        for column in range(4):
            tags.columnconfigure(column, weight=1)
        self.volume_entry = tk.Entry(name_area, textvariable=self.volume_var, bg=PANEL_2, fg=TEXT,
                                     insertbackground=TEXT, relief="flat", font=(FONT, 9))
        self.volume_entry.pack(fill="x", pady=(6, 0), ipady=5)
        self._update_volume_name()

        list_card = tk.Frame(page, bg=PANEL, padx=8, pady=8,
                             highlightbackground=BORDER, highlightthickness=1)
        list_card.pack(fill="both", expand=True)
        self.source_list = tk.Listbox(list_card, bg=PANEL, fg=TEXT, selectbackground=ACCENT_DARK,
                                      selectforeground="#FFFFFF", relief="flat", highlightthickness=0,
                                      activestyle="none", font=(FONT, 9), height=7)
        self.source_list.pack(fill="both", expand=True)
        self.source_list.bind("<Delete>", lambda _e: self.remove_sources())
        source_buttons = tk.Frame(page, bg=BG)
        source_buttons.pack(fill="x", pady=8)
        Button(source_buttons, "+ 文件 Ctrl+O", self.add_files, font=(FONT, 9)).pack(side="left", fill="x", expand=True)
        Button(source_buttons, "+ 文件夹 Ctrl+Shift+O", self.add_folder, font=(FONT, 8)).pack(side="left", fill="x", expand=True, padx=6)
        Button(source_buttons, "移除 Del", self.remove_sources, "ghost", font=(FONT, 8)).pack(side="left")
        Button(source_buttons, "清空 Ctrl+Shift+Del", self.clear_sources, "ghost", font=(FONT, 8)).pack(side="left")
        self.source_summary = tk.Label(page, text="刻录队列为空", bg=BG, fg=MUTED,
                                       font=(FONT, 9), anchor="w")
        self.source_summary.pack(fill="x", pady=(0, 8))
        Button(page, "开始刻录  Ctrl+B", self.burn, "primary",
               font=(FONT, 11, "bold"), pady=12).pack(fill="x")

    def select_volume_tag(self, name: str):
        self.volume_base = name
        self._update_volume_name()

    def _update_volume_name(self):
        self._auto_date = self.auto_date_var.get()
        suffix = "-" + dt.date.today().isoformat() if self._auto_date else ""
        self.volume_var.set(self.volume_base + suffix)
        for name, tag in self.volume_tags.items():
            selected = name == self.volume_base
            tag.config(bg=ACCENT_DARK if selected else PANEL_2,
                       fg="#FFFFFF" if selected else TEXT)

    def _build_history_page(self):
        page = self.pages["history"]
        self._section_title(page, "本机操作记录", "最多 100 条")
        self.history_list = tk.Listbox(page, bg=PANEL, fg=TEXT, selectbackground=ACCENT_DARK,
                                       relief="flat", highlightthickness=0, activestyle="none",
                                       font=(FONT, 9))
        self.history_list.pack(fill="both", expand=True)
        self.history_detail = tk.Label(page, text="", bg=BG, fg=MUTED, wraplength=355,
                                       justify="left", anchor="nw", height=5, font=(FONT, 8))
        self.history_detail.pack(fill="x", pady=8)
        self.history_list.bind("<<ListboxSelect>>", self._show_history_detail)
        Button(page, "清空操作记录  Ctrl+Shift+H", self.clear_history).pack(fill="x")
        Button(page, "彻底退出观海·拾光  Ctrl+Shift+Q", self.force_close, "danger").pack(fill="x", pady=(8, 0))
        self.reload_history()

    def _select_theme(self, _event=None):
        index = self.theme_box.current()
        if 0 <= index < len(self.theme_keys):
            self.set_theme(self.theme_keys[index])

    def next_theme(self):
        index = (list(THEMES).index(self.theme_key) + 1) % len(THEMES)
        self.set_theme(list(THEMES)[index])

    def set_theme(self, key: str):
        if self.busy:
            messagebox.showinfo(APP_NAME, "当前光盘操作结束后即可切换皮肤。", parent=self.root)
            return
        previous_tab = self.current_tab
        self.theme_key = key
        save_theme(key)
        apply_theme(key, globals())
        if self._tally_after:
            self.root.after_cancel(self._tally_after)
            self._tally_after = None
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(bg=BORDER)
        self._build_style()
        self._build_ui()
        self._apply_drives(self.drives)
        self._reload_sources()
        self.show_tab(previous_tab)

    def _pulse_tally(self):
        if self.logo_label.winfo_exists():
            if self.busy:
                self._tally_lit = not self._tally_lit
                self.logo_label.config(image=self.tally_image if self._tally_lit else self.tally_dim_image)
            else:
                self._tally_lit = False
                self.logo_label.config(image=self.logo_image)
            self._tally_after = self.root.after(650, self._pulse_tally)

    def _resize_drop_zone(self, event):
        scale = self.ui_scale
        self.drop_zone.coords(self.drop_border, 2, 2, event.width - 3, event.height - 3)
        for item in (self.drop_title, self.drop_hint):
            y_ratio = 0.34 if item == self.drop_title else 0.62
            self.drop_zone.coords(item, event.width / 2, event.height * y_ratio)
        for item in self.drop_zone.find_all():
            if item not in (self.drop_border, self.drop_title, self.drop_hint):
                self.drop_zone.coords(item, event.width / 2, event.height * 0.83)

    def _on_drop(self, event):
        self._on_drag_leave()
        paths = [Path(p) for p in self.root.tk.splitlist(event.data)]
        self._add_sources(paths)
        self.progress_label.config(text=f"已加入 {len(paths)} 个拖放项目，点击开始刻录")
        return event.action

    def _on_drag_enter(self, _event=None):
        self.drop_zone.config(bg=PANEL_2)
        self.drop_zone.itemconfig(self.drop_border, outline=ACCENT)
        self.drop_zone.itemconfig(self.drop_title, text="松开即可加入刻录队列")

    def _on_drag_leave(self, _event=None):
        self.drop_zone.config(bg=PANEL)
        self.drop_zone.itemconfig(self.drop_border, outline=ACCENT_DARK)
        self.drop_zone.itemconfig(self.drop_title, text="把文件或文件夹拖到这里")

    def _place_right(self):
        self.root.update_idletasks()
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        scale = self.ui_scale
        width = int(420 * scale)
        height = min(int(760 * scale), screen_h - int(70 * scale))
        margin = int(22 * scale)
        x = screen_w - width - margin
        y = max(int(24 * scale), (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _start_drag(self, event):
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event):
        self.root.geometry(f"+{event.x_root - self._drag_origin[0]}+{event.y_root - self._drag_origin[1]}")

    def _snap_right(self, _event):
        screen_w = self.root.winfo_screenwidth()
        if self.root.winfo_x() + self.root.winfo_width() > screen_w - 100:
            self.root.geometry(f"+{screen_w - self.root.winfo_width() - 22}+{self.root.winfo_y()}")

    def _bind_shortcuts(self):
        bindings = {
            "<F1>": lambda _e: self.show_help(),
            "<F5>": lambda _e: self.refresh(),
            "<Control-Key-1>": lambda _e: self.show_tab("disc"),
            "<Control-Key-2>": lambda _e: self.show_tab("burn"),
            "<Control-Key-3>": lambda _e: self.show_tab("secure"),
            "<Control-Key-4>": lambda _e: self.show_tab("history"),
            "<Control-r>": lambda _e: self.browse(),
            "<Control-e>": lambda _e: self.export_disc(),
            "<Control-j>": lambda _e: self.eject(),
            "<Control-o>": lambda _e: self.add_files(),
            "<Control-O>": lambda _e: self.add_folder(),
            "<Control-b>": lambda _e: self.burn(),
            "<Control-X>": lambda _e: self.erase(),
            "<Control-D>": lambda _e: self.deep_format(),
            "<Control-F>": lambda _e: self.format_disc(),
            "<Control-Delete>": lambda _e: self.clear_sources(),
            "<Control-t>": lambda _e: self.next_theme(),
            "<Control-p>": lambda _e: self.toggle_topmost(),
            "<Control-period>": lambda _e: self.cancel(),
            "<Control-g>": lambda _e: self.secure_page.random_password(),
            "<Control-C>": lambda _e: self.secure_page.copy_password(),
            "<Control-k>": lambda _e: self.secure_page.show_archive(),
            "<Control-h>": lambda _e: self.secure_page.toggle_password(),
            "<Control-l>": lambda _e: self.secure_page.choose_destination(),
            "<Control-Alt-g>": lambda _e: self.secure_page.start(False),
            "<Control-B>": lambda _e: self.secure_page.start(True),
            "<Control-H>": lambda _e: self.clear_history(),
            "<Control-Q>": lambda _e: self.force_close(),
        }
        for sequence, command in bindings.items():
            self.root.bind(sequence, command)

    def show_help(self):
        HelpWindow(self)

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)
        self.pin_label.config(
            text="● 已置顶  Ctrl+P" if self.topmost else "○ 未置顶  Ctrl+P",
            bg=ACCENT_DARK if self.topmost else PANEL_2,
            fg="#FFFFFF" if self.topmost else MUTED,
        )

    def show_tab(self, key: str):
        self.current_tab = key
        for name, page in self.pages.items():
            page.pack_forget()
            self.tab_buttons[name].config(bg=PANEL_2 if name == key else PANEL,
                                          fg=TEXT if name == key else MUTED)
        self.pages[key].pack(fill="both", expand=True)
        if key == "history":
            self.reload_history()

    def _select_drive(self, _event=None):
        index = self.drive_box.current()
        if 0 <= index < len(self.drives):
            self.selected_drive = self.drives[index]
            self._update_drive_card()

    def _update_drive_card(self):
        drive = self.selected_drive
        if not drive:
            self.media_label.config(text="未检测到光驱", fg=MUTED)
            self.profile_label.config(text="请检查设备连接后点击刷新")
            self.space_label.config(text="容量 —")
            self.space_bar.config(value=0)
            return
        self.media_label.config(text=drive.status, fg=SUCCESS if drive.blank else TEXT)
        self.profile_label.config(text=f"{drive.profile_name}  ·  {drive.drive_text}")
        self.space_label.config(text=f"容量 {format_size(drive.capacity_bytes)}  ·  可用 {format_size(drive.free_bytes)}")
        used = 0
        if drive.capacity_bytes > 0:
            used = max(0, min(100, (drive.capacity_bytes - drive.free_bytes) * 100 / drive.capacity_bytes))
        self.space_bar.config(value=used)

    def refresh(self):
        if self.busy or self.refreshing or self.minimized:
            return
        self.refreshing = True
        self.progress_label.config(text="正在检测光驱与介质…")

        def worker():
            try:
                self.events.put(("refreshed", self.service.list_drives()))
            except Exception as exc:
                self.events.put(("refresh_error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "refreshed":
                    self.refreshing = False
                    self._apply_drives(payload)
                elif kind == "refresh_error":
                    self.refreshing = False
                    self.progress_label.config(text=payload)
                    self._schedule_refresh()
                elif kind == "progress":
                    text, value = payload
                    self.progress_label.config(text=text)
                    self.last_progress = value
                    self.progress_percent.config(text=f"{value}%" if value is not None else "处理中")
                    if value is None:
                        if str(self.progress.cget("mode")) != "indeterminate":
                            self.progress.config(mode="indeterminate")
                            self.progress.start(12)
                    else:
                        self.progress.stop()
                        self.progress.config(mode="determinate", value=value)
                elif kind == "done":
                    operation, result, on_complete, show_message = payload
                    self._task_done(operation, result, on_complete, show_message)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._poll_events)

    def _schedule_refresh(self):
        if self._refresh_timer:
            self.root.after_cancel(self._refresh_timer)
        self._refresh_timer = self.root.after(8000, self.refresh)

    def _apply_drives(self, drives: list[DriveInfo]):
        previous = self.selected_drive.recorder_id if self.selected_drive else None
        self.drives = drives
        self.drive_box.config(values=[f"{d.drive_text}  |  {d.name}" for d in drives])
        index = next((i for i, d in enumerate(drives) if d.recorder_id == previous), 0 if drives else -1)
        self.selected_drive = drives[index] if index >= 0 else None
        if index >= 0:
            self.drive_box.current(index)
        else:
            self.drive_box.set("")
        self._update_drive_card()
        self.progress_label.config(text=f"检测到 {len(drives)} 个光驱" if drives else "未检测到光驱")
        self._schedule_refresh()

    def require_drive(self, writable=False, erasable=False) -> DriveInfo | None:
        drive = self.selected_drive
        if not drive:
            messagebox.showinfo(APP_NAME, "未检测到光驱。", parent=self.root)
            return None
        if not drive.present:
            messagebox.showinfo(APP_NAME, "请先放入光盘。", parent=self.root)
            return None
        if writable and not drive.writable:
            messagebox.showwarning(APP_NAME, "这张光盘当前不能写入文件。请确认它是空白光盘，或还有可写空间。", parent=self.root)
            return None
        if erasable and not drive.erasable:
            messagebox.showwarning(APP_NAME, "这张光盘不支持擦除。只有标有“可重复擦写”的光盘才能清除后重新使用。", parent=self.root)
            return None
        return drive

    def run_task(self, operation: str, function, on_complete=None, show_message=True):
        if self.busy:
            messagebox.showinfo(APP_NAME, "已有操作正在进行，请等待完成或先取消。", parent=self.root)
            return
        self.busy = True
        self.progress.config(mode="indeterminate", value=0)
        self.progress.start(12)
        self.progress_label.config(text=f"{operation}中…")

        def worker():
            try:
                result = function()
                if not isinstance(result, OperationResult):
                    result = OperationResult(True, f"{operation}完成")
            except Exception as exc:
                result = OperationResult(False, str(exc))
            self.events.put(("done", (operation, result, on_complete, show_message)))
        threading.Thread(target=worker, daemon=True).start()

    def _task_done(self, operation: str, result: OperationResult, on_complete=None, show_message=True):
        self.busy = False
        self.progress.stop()
        self.progress.config(mode="determinate", value=100 if result.ok else 0)
        self.last_progress = 100 if result.ok else 0
        self.progress_percent.config(text="100%" if result.ok else "失败")
        self.progress_label.config(text=result.message)
        self.history.add(operation, result.ok, result.message)
        if on_complete:
            on_complete(result)
        elif show_message:
            if result.ok:
                messagebox.showinfo(APP_NAME, result.message, parent=self.root)
            else:
                messagebox.showerror(APP_NAME, result.message, parent=self.root)
        self.refresh()

    def cancel(self):
        if self.busy and self.service.cancel():
            self.progress_label.config(text="正在请求取消，请等待光驱停止…")

    def browse(self):
        drive = self.require_drive()
        if not drive:
            return
        if drive.blank:
            BlankDiscWizard(self, drive)
        else:
            DiscBrowser(self, drive.recorder_id)

    def export_disc(self):
        drive = self.require_drive()
        if not drive:
            return
        destination = filedialog.askdirectory(title="选择整盘导出位置", parent=self.root)
        if destination:
            self.run_task("整盘导出", lambda: self.service.export_disc(drive.recorder_id, destination))

    def eject(self):
        drive = self.require_drive()
        if drive:
            self.run_task("弹出光盘", lambda: self.service.eject(drive.recorder_id))

    def erase(self):
        drive = self.require_drive(erasable=True)
        if not drive:
            return
        if not messagebox.askyesno(APP_NAME, f"擦除会清除 {drive.drive_text} 光盘中的现有数据，且无法撤销。\n\n确定继续吗？", parent=self.root):
            return
        self.run_task("快速擦除",
                      lambda: self.service.erase(drive.recorder_id, False, self._progress_callback),
                      on_complete=self._erase_finished, show_message=False)

    def deep_format(self):
        drive = self.require_drive(erasable=True)
        if not drive:
            return
        text = (f"将对 {drive.drive_text} 光盘执行深度格式化（完整擦除）。\n\n"
                "这会逐块清除整张光盘，不只是删除文件目录，且无法撤销。"
                "根据光盘类型和速度，可能需要几十分钟，期间请勿弹出光盘或让电脑休眠。\n\n确定继续吗？")
        if messagebox.askyesno(APP_NAME, text, parent=self.root):
            self.run_task("深度格式化",
                          lambda: self.service.erase(drive.recorder_id, True, self._progress_callback),
                          on_complete=self._erase_finished, show_message=False)

    def _erase_finished(self, result: OperationResult):
        if not result.ok:
            messagebox.showerror(APP_NAME, result.message, parent=self.root)
            return
        choice = messagebox.choose(
            "擦除完成 · 选择使用方式",
            "光盘已清空。接下来希望怎样使用？\n\n"
            "标准刻录：通过本软件或 Windows 刻录向导写入，完成后各种电脑都能读取。\n\n"
            "可移动磁盘：建立 Windows 原生文件目录，可在资源管理器中直接打开、复制和删除文件。",
            (("暂不操作", False), ("标准刻录", "burn"), ("建立 Windows 文件目录", "udf")),
            parent=self.root,
        )
        if choice == "udf":
            self.format_disc()
        elif choice == "burn":
            self.show_tab("burn")
            messagebox.showinfo(APP_NAME, "空白光盘已就绪，拖入文件即可开始刻录。", parent=self.root)

    def format_disc(self):
        drive = self.require_drive(writable=True)
        if not drive:
            return
        text = (f"将在 {drive.drive_text} 中建立 Windows 文件目录。\n"
                "完成后可直接打开空光盘，像 U 盘一样复制、删除文件。\n\n"
                "此操作会清除原有内容，只适用于可重复擦写的光盘。\n\n确定继续吗？")
        if messagebox.askyesno(APP_NAME, text, parent=self.root):
            self.run_task("建立 Windows 文件目录",
                          lambda: self.service.format(drive.recorder_id, self.volume_var.get(), self._progress_callback),
                          on_complete=self._format_finished, show_message=False)

    def _format_finished(self, result: OperationResult):
        if not result.ok:
            messagebox.showerror(APP_NAME, result.message, parent=self.root)
            return
        drive = self.selected_drive
        if not drive:
            messagebox.showerror(APP_NAME, "目录已建立，但未找到用于读取验证的光驱。", parent=self.root)
            return
        self.run_task("后台检查光盘是否可读",
                      lambda: self.service.list_files(drive.recorder_id),
                      on_complete=self._verify_format_done, show_message=False)

    def _verify_format_done(self, result: OperationResult):
        if not result.ok:
            messagebox.showerror(APP_NAME, f"文件目录已写入，但读取检查失败：{result.message}", parent=self.root)
            return
        self.refresh()
        messagebox.showinfo(APP_NAME, "Windows 文件目录已建立并通过读取检查。\n\n现在既可以在观海·拾光中管理，也可以在资源管理器中打开光盘、复制或删除文件。", parent=self.root)

    def add_files(self):
        paths = filedialog.askopenfilenames(title="选择要刻录的文件", parent=self.root)
        self._add_sources(Path(p) for p in paths)

    def add_folder(self):
        path = filedialog.askdirectory(title="选择要刻录的文件夹", parent=self.root)
        if path:
            self._add_sources([Path(path)])

    def _add_sources(self, paths):
        existing = {p.name.casefold() for p in self.sources}
        added = 0
        for path in paths:
            if path.exists() and path.name.casefold() not in existing:
                self.sources.append(path)
                existing.add(path.name.casefold())
                added += 1
        self._reload_sources()
        if added and self.current_tab != "burn":
            self.show_tab("burn")

    def remove_sources(self):
        selected = set(self.source_list.curselection())
        self.sources = [p for i, p in enumerate(self.sources) if i not in selected]
        self._reload_sources()

    def clear_sources(self):
        self.sources.clear()
        self._reload_sources()

    def _reload_sources(self):
        self.source_list.delete(0, "end")
        total = 0
        for path in self.sources:
            self.source_list.insert("end", f"{'文件夹' if path.is_dir() else '文件'}  {path.name}")
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
        suffix = f" · 文件约 {format_size(total)}" if total else ""
        self.source_summary.config(text=f"队列：{len(self.sources)} 个根目录项目{suffix}" if self.sources else "刻录队列为空")
        if hasattr(self, "secure_page"):
            self.secure_page.reload_files()

    def burn(self):
        drive = self.require_drive(writable=True)
        if not drive:
            return
        if not self.sources:
            messagebox.showinfo(APP_NAME, "请先拖入或添加要刻录的文件。", parent=self.root)
            return
        if drive.file_system == "UDF" and not drive.blank:
            if not messagebox.askokcancel(APP_NAME, f"目标：{drive.drive_text} · 可直接复制文件的光盘\n项目：{len(self.sources)} 个\n\n文件将复制到光盘，同名文件会被替换。开始吗？", parent=self.root):
                return
            sources = list(self.sources)
            self.run_task("复制文件到光盘", lambda: self.service.copy_to_disc(drive.recorder_id, sources, callback=self._progress_callback))
            return
        if not drive.blank and not messagebox.askyesno(APP_NAME, "这张光盘已有文件。程序会尝试保留原文件并加入新文件；如果光盘已经封盘，则无法继续写入。\n\n仍要尝试刻录吗？", parent=self.root):
            return
        mode = "像 U 盘一样使用的光盘" if self.burn_mode == "UDF" else "标准光盘（适合交接和其他电脑读取）"
        if not messagebox.askokcancel(APP_NAME, f"目标：{drive.drive_text}\n使用方式：{mode}\n项目：{len(self.sources)} 个\n光盘名称：{self.volume_var.get()}\n\n刻录完成后将封盘，保护已有内容。开始吗？", parent=self.root):
            return
        sources = list(self.sources)
        self.run_task("刻录光盘", lambda: self.service.burn(drive.recorder_id, sources, self.volume_var.get(), True, self._progress_callback, self.burn_mode))

    def _progress_callback(self, text: str, value: int | None):
        self.events.put(("progress", (text, value)))

    def reload_history(self):
        records = self.history.load()
        self.history_records = records
        self.history_list.delete(0, "end")
        for record in records:
            self.history_list.insert("end", f"{record['time'][5:16]}  {record['operation']}  ·  {record['status']}")
        self.history_detail.config(text="")

    def _show_history_detail(self, _event=None):
        selected = self.history_list.curselection()
        if selected:
            record = self.history_records[selected[0]]
            self.history_detail.config(text=f"{record['time']}\n{record['operation']} · {record['status']}\n{record['message']}")

    def clear_history(self):
        if messagebox.askyesno(APP_NAME, "清空本机的操作记录？", parent=self.root):
            self.history.clear()
            self.reload_history()

    def close(self):
        """点击关闭收缩为桌面浮动图标，后台任务继续运行。"""
        self.minimized = True
        self.root.withdraw()
        self.tray.show()
        self.mini_icon.show()
        self._show_minimize_toast()

    def restore(self):
        self.root.after(0, self._restore_now)

    def _restore_now(self):
        self.tray.hide()
        self.mini_icon.hide()
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.topmost)
        self.minimized = False
        self.refresh()

    def _show_minimize_toast(self):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=BORDER)
        frame = tk.Frame(toast, bg=PANEL, padx=16, pady=12)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(frame, text="观海·拾光已收缩为桌面浮动图标，单击即可召回", 
                 bg=PANEL, fg=TEXT, font=(FONT, 9)).pack()
        toast.update_idletasks()
        width, height = int(360 * self.ui_scale), int(58 * self.ui_scale)
        x = self.root.winfo_screenwidth() - width - int(22 * self.ui_scale)
        y = self.root.winfo_screenheight() - height - int(72 * self.ui_scale)
        toast.geometry(f"{width}x{height}+{x}+{y}")
        toast.after(4000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def _restored(self, _event=None):
        if self.minimized and self.root.state() == "normal":
            self.minimized = False
            self.root.after(20, lambda: self.root.overrideredirect(True))

    def force_close(self):
        if self.busy:
            if not messagebox.askyesno(APP_NAME, "光盘操作尚未结束。强制退出可能导致刻录失败，建议先取消并等待。\n\n仍要退出吗？", parent=self.root):
                return
        self.mini_icon.destroy()
        self.tray.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if os.name != "nt":
        print("当前版本仅支持 Windows。")
        return 1
    try:
        app = YaoKeApp()
        app.run()
        return 0
    except tk.TclError as exc:
        print(f"无法启动图形界面：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
