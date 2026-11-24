from __future__ import annotations

import datetime as dt
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from export_organizer import RULES, export_organized
from optical.models import FileEntry, OperationResult, format_size

BG = "#0B1220"
PANEL = "#121E2F"
PANEL_2 = "#1A2A3F"
TEXT = "#EDF4FF"
MUTED = "#8FA3BA"
ACCENT = "#5EEAD4"
ACCENT_DARK = "#0F766E"
BORDER = "#23344A"
FONT = "Microsoft YaHei UI"


class DiscBrowser(tk.Frame):
    """嵌入光盘页的浏览、整理和导出面板，不创建独立文件窗口。"""

    def __init__(self, app, recorder_id: str, parent):
        super().__init__(parent, bg=BG)
        self.app = app
        self.service = app.service
        self.recorder_id = recorder_id
        self.relative = ""
        self.all_entries: list[FileEntry] = []
        self.entries: list[FileEntry] = []
        self.last_destination: Path | None = None
        default = Path.home() / "Documents" / "GuanHaiExports" / dt.date.today().isoformat()
        self.destination_var = tk.StringVar(value=str(default))
        self.rule_var = tk.StringVar(value=RULES[0])
        self.search_var = tk.StringVar()
        self._build()
        self.load()

    def _button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT_DARK if primary else PANEL_2,
                         fg="#FFFFFF" if primary else TEXT, activebackground="#0D9488",
                         activeforeground="#FFFFFF", relief="flat", bd=0, highlightthickness=0,
                         cursor="hand2", padx=8, pady=6, font=(FONT, 9))

    def _build(self):
        heading = tk.Frame(self, bg=BG)
        heading.pack(fill="x", pady=(0, 7))
        self._button(heading, "‹ 返回光盘", self.close).pack(side="left")
        tk.Label(heading, text="浏览与导出", bg=BG, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left", padx=10)
        self._button(heading, "打开导出目录", self.open_destination).pack(side="right")

        nav = tk.Frame(self, bg=BG)
        nav.pack(fill="x", pady=(0, 6))
        self._button(nav, "↑ 上级", self.go_up).pack(side="left")
        self.path_label = tk.Label(nav, text="光盘根目录", bg=BG, fg=MUTED, font=(FONT, 9))
        self.path_label.pack(side="left", padx=8)
        self._button(nav, "刷新", self.load).pack(side="right")

        search = tk.Entry(self, textvariable=self.search_var, bg=PANEL_2, fg=TEXT,
                          insertbackground=TEXT, relief="flat", font=(FONT, 10))
        search.pack(fill="x", ipady=6, pady=(0, 6))
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        search.insert(0, "")
        search.bind("<FocusIn>", lambda _e: None)
        tk.Label(self, text="输入名称可筛选当前目录；双击文件夹进入", bg=BG, fg=MUTED,
                 anchor="w", font=(FONT, 8)).pack(fill="x", pady=(0, 5))

        body = tk.Frame(self, bg=PANEL)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("size", "modified"), show="tree headings",
                                 selectmode="extended", height=8)
        self.tree.heading("#0", text="名称")
        self.tree.heading("size", text="大小")
        self.tree.heading("modified", text="修改时间")
        self.tree.column("#0", width=160, minwidth=100)
        self.tree.column("size", width=65, anchor="e", stretch=False)
        self.tree.column("modified", width=120, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.open_selected)
        self.tree.bind("<Control-a>", self.select_all)
        self.tree.bind("<Return>", self.open_selected)
        self.tree.bind("<BackSpace>", lambda _e: self.go_up())
        self.status = tk.Label(self, text="正在读取…", bg=BG, fg=MUTED, anchor="w", font=(FONT, 8))
        self.status.pack(fill="x", pady=5)

        settings = tk.Frame(self, bg=PANEL, padx=9, pady=8, highlightbackground=BORDER, highlightthickness=1)
        settings.pack(fill="x", pady=(0, 7))
        tk.Label(settings, text="导出设置", bg=PANEL, fg=TEXT, font=(FONT, 10, "bold")).pack(anchor="w")
        row = tk.Frame(settings, bg=PANEL)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="整理方式", bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(side="left")
        ttk.Combobox(row, textvariable=self.rule_var, state="readonly", values=RULES,
                     font=(FONT, 9), width=15).pack(side="right")
        tk.Label(settings, text="保存到", bg=PANEL, fg=MUTED, anchor="w", font=(FONT, 9)).pack(fill="x", pady=(6, 3))
        destination = tk.Frame(settings, bg=PANEL)
        destination.pack(fill="x")
        tk.Entry(destination, textvariable=self.destination_var, bg=PANEL_2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=(FONT, 8)).pack(side="left", fill="x", expand=True, ipady=4)
        self._button(destination, "选择", self.choose_destination).pack(side="right", padx=(5, 0))

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x")
        self._button(actions, "全选", self.select_all).pack(side="left", fill="x", expand=True)
        self._button(actions, "导出选中 Ctrl+E", self.export_selected).pack(side="left", fill="x", expand=True, padx=5)
        self._button(actions, "导出整张光盘", self.export_disc, True).pack(side="left", fill="x", expand=True)

    def load(self):
        if getattr(self, "_loading", False):
            return
        self._loading = True
        relative = self.relative
        self.status.config(text="正在后台读取光盘目录…")

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
            messagebox.showerror("观海·拾光", error, parent=self.app.root)
            return
        self.all_entries = entries
        self.path_label.config(text=self.relative or "光盘根目录")
        self.apply_filter()

    def apply_filter(self):
        keyword = self.search_var.get().strip().casefold()
        self.entries = [e for e in self.all_entries if keyword in e.name.casefold()] if keyword else list(self.all_entries)
        self.tree.delete(*self.tree.get_children())
        for index, entry in enumerate(self.entries):
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.modified)) if entry.modified else "—"
            self.tree.insert("", "end", iid=str(index), text=("📁 " if entry.is_dir else "📄 ") + entry.name,
                             values=("—" if entry.is_dir else format_size(entry.size), modified))
        total = sum(e.size for e in self.entries if not e.is_dir)
        self.status.config(text=f"{len(self.entries)} 个项目 · 当前目录文件 {format_size(total)}")

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
                messagebox.showerror("观海·拾光", str(exc), parent=self.app.root)

    def select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def choose_destination(self):
        destination = filedialog.askdirectory(title="选择导出位置", parent=self.app.root,
                                              initialdir=self.destination_var.get())
        if destination:
            self.destination_var.set(destination)

    def _export(self, sources):
        destination = self.destination_var.get().strip()
        if not destination:
            messagebox.showinfo("观海·拾光", "请先填写或选择导出目录。", parent=self.app.root)
            return
        self.last_destination = Path(destination)
        rule = self.rule_var.get()
        self.app.run_task("整理并导出" if rule != RULES[0] else "导出文件",
                          lambda: export_organized(sources, destination, rule),
                          on_complete=self._export_done, show_message=False)

    def export_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("观海·拾光", "请先选择要导出的文件或文件夹。", parent=self.app.root)
            return
        self._export([self.entries[int(i)].path for i in selection])

    def export_disc(self):
        if not self.all_entries:
            self.select_all()
        self._export([entry.path for entry in self.all_entries])

    def _export_done(self, result: OperationResult):
        self.status.config(text=result.message)
        if result.ok:
            self.app.progress_label.config(text=result.message + "；可点击“打开导出目录”")

    def open_destination(self):
        destination = Path(self.destination_var.get().strip())
        try:
            destination.mkdir(parents=True, exist_ok=True)
            os.startfile(str(destination))
        except OSError as exc:
            messagebox.showerror("观海·拾光", f"无法打开导出目录：{exc}", parent=self.app.root)

    def close(self):
        self.app.close_disc_browser()
