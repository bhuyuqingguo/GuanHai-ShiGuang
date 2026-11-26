from __future__ import annotations

import datetime as dt
import re
import secrets
import string
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

from dialogs import Dialogs
from secure_transfer import PackageResult, SecureTransferService

BG = "#0B1220"
PANEL = "#121E2F"
PANEL_2 = "#1A2A3F"
TEXT = "#EDF4FF"
MUTED = "#8FA3BA"
ACCENT = "#5EEAD4"
ACCENT_DARK = "#0F766E"
BORDER = "#23344A"
FONT = "Microsoft YaHei UI"


class SecureTransferPage:
    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.dialogs = Dialogs()
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        self.service = SecureTransferService(str(base / "receiver_stub.exe"))
        self.last_package: PackageResult | None = None
        self.date_var = tk.StringVar(value=dt.date.today().isoformat())
        self.content_var = tk.StringVar()
        self.person_var = tk.StringVar()
        self.destination_var = tk.StringVar(value=str(Path.home() / "Documents" / "GuanHaiPackages"))
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()
        self.filename_var = tk.StringVar()
        self.show_password = False
        for variable in (self.date_var, self.content_var, self.person_var):
            variable.trace_add("write", self._update_filename)
        self._build()
        self._update_filename()

    def _button(self, parent, text, command, primary=False, compact=False):
        return tk.Button(parent, text=text, command=command,
                         bg=ACCENT_DARK if primary else PANEL_2, fg="#FFFFFF",
                         activebackground="#0D9488", activeforeground="#FFFFFF",
                         relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                         padx=9, pady=4 if compact else 7, font=(FONT, 8 if compact else 9))

    def _card(self, number, title, hint=""):
        card = tk.Frame(self.parent, bg=PANEL, padx=11, pady=8,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 7))
        heading = tk.Frame(card, bg=PANEL)
        heading.pack(fill="x", pady=(0, 5))
        tk.Label(heading, text=number, bg=ACCENT_DARK, fg="#FFFFFF",
                 font=("Segoe UI", 8, "bold"), width=2).pack(side="left")
        tk.Label(heading, text=title, bg=PANEL, fg=TEXT,
                 font=(FONT, 9, "bold")).pack(side="left", padx=7)
        if hint:
            tk.Label(heading, text=hint, bg=PANEL, fg=MUTED, font=(FONT, 7)).pack(side="right")
        return card

    @staticmethod
    def _entry(parent, variable, secret=False):
        return tk.Entry(parent, textvariable=variable, bg=PANEL_2, fg=TEXT,
                        insertbackground=TEXT, relief="flat", bd=0,
                        highlightthickness=0, font=(FONT, 9), show="●" if secret else "")

    @staticmethod
    def _field_label(parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED, font=(FONT, 8), anchor="w").pack(fill="x", pady=(0, 3))

    def _build(self):
        header = tk.Frame(self.parent, bg=BG)
        header.pack(fill="x", pady=(0, 7))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        tk.Label(brand, text="加密交接", bg=BG, fg=TEXT, font=(FONT, 13, "bold")).pack(anchor="w")
        tk.Label(brand, text="观海·八分 BFQ · Windows / 麒麟通用格式", bg=BG, fg=MUTED,
                 font=(FONT, 8)).pack(anchor="w", pady=(3, 0))
        self._button(header, "密码归档 Ctrl+K", self.show_archive, compact=True).pack(side="right", pady=6)

        info = self._card("1", "交接信息", "自动生成文件名")
        first = tk.Frame(info, bg=PANEL)
        first.pack(fill="x")
        date_box = tk.Frame(first, bg=PANEL)
        date_box.pack(side="left", fill="x", expand=True)
        self._field_label(date_box, "日期")
        self._entry(date_box, self.date_var).pack(fill="x", ipady=4)
        person_box = tk.Frame(first, bg=PANEL)
        person_box.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._field_label(person_box, "交接人")
        self._entry(person_box, self.person_var).pack(fill="x", ipady=4)
        self._field_label(info, "交接内容（例如：项目资料）")
        self._entry(info, self.content_var).pack(fill="x", ipady=4)
        tk.Label(info, textvariable=self.filename_var, bg=PANEL, fg=ACCENT,
                 font=(FONT, 8), anchor="w").pack(fill="x", pady=(6, 0))

        files = self._card("2", "交接文件", "树形编辑 · 与刻录队列同步")
        self.tree_hint = tk.Label(files, text="单击选中 · Ctrl+单击多选 · 点 ▸ 折叠", bg=PANEL, fg=MUTED,
                                  anchor="w", font=(FONT, 9))
        self.tree_hint.pack(fill="x", pady=(0, 4))
        tree_area = tk.Frame(files, bg=PANEL_2)
        tree_area.pack(fill="both", expand=True)
        self.file_tree = ttk.Treeview(tree_area, show="tree headings", columns=("mapping",),
                                      selectmode="extended", height=5)
        self.file_tree.heading("#0", text="交接结构")
        self.file_tree.heading("mapping", text="目录对应")
        self.file_tree.column("mapping", width=130, anchor="w", stretch=False)
        tree_scroll = ttk.Scrollbar(tree_area, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=tree_scroll.set)
        self.file_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.file_tree.tag_configure("folder", foreground=ACCENT)
        self.file_tree.tag_configure("file", foreground=TEXT)
        self.file_tree.tag_configure("drop_target", background=ACCENT_DARK, foreground="#FFFFFF")
        self.file_tree.bind("<Delete>", lambda _e: self.app.remove_sources(self.file_tree))
        self.file_tree.bind("<F2>", lambda _e: self.app.rename_source_entry(self.file_tree))
        self.file_tree.bind("<<TreeviewClose>>", self.app._on_tree_collapsed)
        self.file_tree.bind("<<TreeviewOpen>>", self.app._on_tree_expanded)
        self.file_tree.bind("<ButtonPress-1>", lambda e: self.app._tree_drag_start(e, self.file_tree))
        self.file_tree.bind("<B1-Motion>", lambda e: self.app._tree_drag_over(e, self.file_tree))
        self.file_tree.bind("<ButtonRelease-1>", lambda e: self.app._tree_drag_drop(e, self.file_tree))
        if DND_FILES:
            self.file_tree.drop_target_register(DND_FILES)
            self.file_tree.dnd_bind("<<DragPosition>>", lambda e: self.app._on_tree_drag_position(e, self.file_tree))
            self.file_tree.dnd_bind("<<Drop>>", lambda e: self.app._on_tree_drop(e, self.file_tree))
        file_actions = tk.Frame(files, bg=PANEL)
        file_actions.pack(fill="x", pady=(5, 3))
        self._button(file_actions, "+ 文件 Ctrl+O", self.add_files, compact=True).pack(side="left", fill="x", expand=True)
        self._button(file_actions, "+ 文件夹 Ctrl+Shift+O", self.add_folder, compact=True).pack(side="left", fill="x", expand=True, padx=5)
        self._button(file_actions, "删除 Del", lambda: self.app.remove_sources(self.file_tree), compact=True).pack(side="left")
        self._button(file_actions, "清空", self.clear, compact=True).pack(side="left", padx=(5, 0))
        edit_actions = tk.Frame(files, bg=PANEL)
        edit_actions.pack(fill="x")
        self._button(edit_actions, "新建文件夹", lambda: self.app.create_source_folder(self.file_tree), compact=True).pack(side="left", fill="x", expand=True)
        self._button(edit_actions, "重命名 F2", lambda: self.app.rename_source_entry(self.file_tree), compact=True).pack(side="left", fill="x", expand=True, padx=5)
        self._button(edit_actions, "一键整理", self.app.organize_sources, True, compact=True).pack(side="left", fill="x", expand=True)

        security = self._card("3", "密码保护", "内容和文件名都会受到保护")
        passwords = tk.Frame(security, bg=PANEL)
        passwords.pack(fill="x")
        password_box = tk.Frame(passwords, bg=PANEL)
        password_box.pack(side="left", fill="x", expand=True)
        self._field_label(password_box, "交接密码")
        self.password_entry = self._entry(password_box, self.password_var, True)
        self.password_entry.pack(fill="x", ipady=4)
        confirm_box = tk.Frame(passwords, bg=PANEL)
        confirm_box.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._field_label(confirm_box, "再次输入")
        self.confirm_entry = self._entry(confirm_box, self.confirm_var, True)
        self.confirm_entry.pack(fill="x", ipady=4)
        tools = tk.Frame(security, bg=PANEL)
        tools.pack(fill="x", pady=(5, 0))
        self._button(tools, "随机密码 Ctrl+G", self.random_password, compact=True).pack(side="left")
        self._button(tools, "显隐 Ctrl+H", self.toggle_password, compact=True).pack(side="left", padx=5)
        self._button(tools, "复制 Ctrl+Shift+C", self.copy_password, compact=True).pack(side="left")

        output = self._card("4", "保存与输出", "BFQ 通用格式 · 需观海八分核心恢复")
        self._field_label(output, "本机保存位置")
        destination = tk.Frame(output, bg=PANEL)
        destination.pack(fill="x")
        self._entry(destination, self.destination_var).pack(side="left", fill="x", expand=True, ipady=4)
        self._button(destination, "选择 Ctrl+L", self.choose_destination, compact=True).pack(side="right", padx=(6, 0))
        self._button(output, "恢复已有 BFQ 交接包", self.recover_package, compact=True).pack(fill="x", pady=(6, 0))

        actions = tk.Frame(self.parent, bg=BG)
        actions.pack(fill="x", pady=(1, 0))
        self._button(actions, "仅生成 Ctrl+Alt+G", lambda: self.start(False)).pack(side="left", fill="x", expand=True)
        self._button(actions, "生成并刻录 Ctrl+Shift+B", lambda: self.start(True), True).pack(side="left", fill="x", expand=True, padx=(7, 0))
        self.reload_files()

    @staticmethod
    def _safe_part(value: str, fallback: str, limit: int) -> str:
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip()).strip(" .")
        return (text or fallback)[:limit]

    def package_name(self) -> str:
        date = self._safe_part(self.date_var.get(), dt.date.today().isoformat(), 10)
        content = self._safe_part(self.content_var.get(), "未填写内容", 50)
        person = self._safe_part(self.person_var.get(), "未填写交接人", 24)
        return f"{date}-{content}-{person}"

    def _update_filename(self, *_args):
        self.filename_var.set("文件名  " + self.package_name() + ".bfq")

    def reload_files(self):
        if hasattr(self, "file_tree"):
            self.app._reload_sources()

    def add_files(self):
        self.app.add_files()
        self.app.show_tab("secure")
        self.reload_files()

    def add_folder(self):
        self.app.add_folder()
        self.app.show_tab("secure")
        self.reload_files()

    def clear(self):
        self.app.clear_sources()
        self.reload_files()

    def choose_destination(self):
        path = filedialog.askdirectory(title="选择交接包保存位置", parent=self.app.root)
        if path:
            self.destination_var.set(path)

    def recover_package(self):
        package = filedialog.askopenfilename(title="选择观海·八分 BFQ 交接包", parent=self.app.root,
                                             filetypes=[("观海·八分交接包", "*.bfq")])
        if not package:
            return
        password = self.password_var.get()
        if not password:
            self.dialogs.showinfo("观海·拾光", "请先在交接密码栏输入恢复密码。")
            return
        destination = filedialog.askdirectory(title="选择恢复资料的保存目录", parent=self.app.root)
        if destination:
            self.app.run_task("恢复观海·八分交接包",
                              lambda: self.service.recover_package(package, password, destination,
                                                                  self.app._progress_callback, self.app.transfer_cancel))

    def random_password(self):
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(20))
        self.password_var.set(password)
        self.confirm_var.set(password)

    def toggle_password(self):
        self.show_password = not self.show_password
        self.password_entry.config(show="" if self.show_password else "●")
        self.confirm_entry.config(show="" if self.show_password else "●")

    def copy_password(self):
        if self.password_var.get():
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(self.password_var.get())
            self.app.progress_label.config(text="密码已复制，请通过其他渠道交接")

    def validate(self, burn):
        if not self.content_var.get().strip() or not self.person_var.get().strip():
            self.dialogs.showinfo("观海·拾光", "请先填写交接内容和交接人，便于识别与归档。")
            return False
        try:
            dt.date.fromisoformat(self.date_var.get().strip())
        except ValueError:
            self.dialogs.showinfo("观海·拾光", "日期请按 YYYY-MM-DD 填写，例如 2026-11-23。")
            return False
        if not self.app.sources:
            self.dialogs.showinfo("观海·拾光", "请先添加要交接的文件或文件夹。")
            return False
        if not self.password_var.get() or self.password_var.get() != self.confirm_var.get():
            self.dialogs.showinfo("观海·拾光", "密码为空或两次输入不一致。")
            return False
        if burn and not self.app.require_drive(writable=True):
            return False
        return True

    def start(self, burn):
        if not self.validate(burn):
            return
        drive = self.app.selected_drive
        mode = self.app.burn_mode
        package_name = self.package_name()
        destination = self.destination_var.get()
        password = self.password_var.get()

        def task():
            with tempfile.TemporaryDirectory(prefix="GuanHaiTransferTree_") as temporary:
                staged = Path(temporary) / "content"
                self.app.burn_queue.materialize(staged)
                sources = list(staged.iterdir())
                result = self.service.create_package(sources, destination, package_name, password,
                                                     self.app._progress_callback, self.app.transfer_cancel)
            if not result.ok or not burn:
                return result
            return self.service.burn_package(result.package_path, result.sha256, self.app.service, drive, mode,
                                             self.app._progress_callback)

        self.app.run_task("生成并刻录加密交接包" if burn else "生成加密交接包", task)

    def show_archive(self):
        window = tk.Toplevel(self.app.root)
        window.title("观海·拾光 · 本机密码归档")
        window.configure(bg=BG)
        scale = self.app.ui_scale
        width, height = int(600 * scale), int(470 * scale)
        x = max(0, self.app.root.winfo_x() - width - int(14 * scale))
        y = max(0, self.app.root.winfo_y())
        window.geometry(f"{width}x{height}+{x}+{y}")
        tk.Label(window, text="本机密码归档", bg=BG, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
        tk.Label(window, text="仅当前 Windows 账户可解密查看，选中一条记录后复制密码。",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=18, pady=(0, 12))
        records = self.service.passwords.load()
        listing = tk.Listbox(window, bg=PANEL, fg=TEXT, selectbackground=ACCENT_DARK,
                             relief="flat", highlightthickness=0, font=(FONT, 9))
        listing.pack(fill="both", expand=True, padx=18)
        for record in records:
            listing.insert("end", f"{record['time']}  {record['package']}")

        def copy(_event=None):
            selected = listing.curselection()
            if selected:
                password = self.service.passwords.reveal(records[selected[0]])
                window.clipboard_clear()
                window.clipboard_append(password)
                self.app.progress_label.config(text="归档密码已复制")

        self._button(window, "复制选中密码", copy, True).pack(fill="x", padx=18, pady=18)
