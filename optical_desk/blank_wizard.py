from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from optical.models import DriveInfo, OperationResult, format_size

BG = "#0B1220"
PANEL = "#121E2F"
PANEL_2 = "#1A2A3F"
TEXT = "#EDF4FF"
MUTED = "#8FA3BA"
ACCENT = "#5EEAD4"
ACCENT_DARK = "#0F766E"
DANGER = "#FB7185"
FONT = "Microsoft YaHei UI"


class BlankDiscWizard(tk.Toplevel):
    """空白盘从识别、格式化到可读验证的分步向导。"""

    def __init__(self, app, drive: DriveInfo):
        super().__init__(app.root)
        self.app = app
        self.drive = drive
        self.step = 1
        self.working = False
        self.volume_var = tk.StringVar(value="观海拾光")
        self.mode_var = tk.StringVar(value="CD")
        self.title("观海·拾光 · 空白光盘向导")
        self.configure(bg=BG)
        self.transient(app.root)
        self.resizable(False, False)
        scale = app.ui_scale
        self.geometry(f"{int(500*scale)}x{int(570*scale)}")
        self.update_idletasks()
        x = app.root.winfo_x() + (app.root.winfo_width() - self.winfo_width()) // 2
        y = app.root.winfo_y() + (app.root.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._build_shell()
        self.show_step(1)

    def _build_shell(self):
        header = tk.Frame(self, bg=BG, padx=24, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="空白光盘向导", bg=BG, fg=TEXT,
                 font=(FONT, 16, "bold")).pack(anchor="w")
        tk.Label(header, text="按步骤准备光盘，完成后即可读取和写入。",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(5, 0))
        self.steps = tk.Label(self, bg=BG, fg=ACCENT, font=(FONT, 9), padx=24)
        self.steps.pack(fill="x")
        self.body = tk.Frame(self, bg=BG, padx=24, pady=18)
        self.body.pack(fill="both", expand=True)
        self.footer = tk.Frame(self, bg=BG, padx=24, pady=18)
        self.footer.pack(fill="x", side="bottom")

    def _button(self, text, command, primary=False):
        return tk.Button(self.footer, text=text, command=command,
                         bg=ACCENT_DARK if primary else PANEL_2,
                         fg="#FFFFFF" if primary else TEXT,
                         activebackground="#0D9488", activeforeground="#FFFFFF",
                         relief="flat", bd=0, cursor="hand2", padx=16, pady=10,
                         font=(FONT, 9, "bold" if primary else "normal"))

    def _clear(self):
        for frame in (self.body, self.footer):
            for child in frame.winfo_children():
                child.destroy()

    def _card(self):
        card = tk.Frame(self.body, bg=PANEL, padx=18, pady=18,
                        highlightbackground="#23344A", highlightthickness=1)
        card.pack(fill="x")
        return card

    def show_step(self, step: int):
        self.step = step
        self._clear()
        labels = {1: "1 确认光盘  →  2 格式化  →  3 验证  →  4 完成",
                  2: "1 确认光盘  →  2 格式化  →  3 验证  →  4 完成",
                  3: "正在执行：格式化并验证光盘",
                  4: "1 确认光盘  →  2 格式化  →  3 验证  →  4 完成"}
        self.steps.config(text=labels[step])
        getattr(self, f"_step_{step}")()

    def _step_1(self):
        card = self._card()
        tk.Label(card, text="已识别到空白光盘", bg=PANEL, fg=ACCENT,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(card, text=f"{self.drive.drive_text}  ·  {self.drive.profile_name}",
                 bg=PANEL, fg=TEXT, font=(FONT, 10)).pack(anchor="w", pady=(12, 4))
        tk.Label(card, text=f"容量 {format_size(self.drive.capacity_bytes)}  ·  可用 {format_size(self.drive.free_bytes)}",
                 bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        tk.Label(self.body, text="给这张光盘起个名字：", bg=BG, fg=TEXT,
                 font=(FONT, 9)).pack(anchor="w", pady=(20, 7))
        entry = ttk.Combobox(self.body, textvariable=self.volume_var,
                             values=("观海拾光", "工作资料", "文件交接", "重要备份", "项目归档", "照片留念", "音乐精选"),
                             font=(FONT, 11))
        entry.pack(fill="x", ipady=5)
        tk.Label(self.body, text="准备怎样使用这张光盘？", bg=BG, fg=TEXT,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(16, 7))
        modes = tk.Frame(self.body, bg=BG)
        modes.pack(fill="x")
        for text, value in (("标准光盘（推荐，适合长期保存和交接）", "CD"), ("像 U 盘一样反复复制文件", "UDF")):
            tk.Radiobutton(modes, text=text, variable=self.mode_var, value=value,
                           bg=BG, fg=TEXT, selectcolor=PANEL_2, activebackground=BG,
                           activeforeground=ACCENT, font=(FONT, 9), anchor="w").pack(fill="x", pady=3)
        rewritable = self.drive.profile in {3, 6, 8, 9, 14}
        note = ("标准光盘适合大多数电脑读取；反复复制方式需要先准备光盘，之后可直接增删文件。"
                if rewritable else
                "这是一次性写入光盘。选择任一方式都会把文件正式写入，写满或刻录完成后不能再擦除。")
        tk.Label(self.body, text=note, bg=BG, fg=MUTED, wraplength=int(430 * self.app.ui_scale),
                 justify="left", font=(FONT, 8)).pack(anchor="w", pady=10)
        self._button("取消", self.close).pack(side="right")
        self._button("下一步", self.next_from_identify, True).pack(side="right", padx=(0, 8))

    def next_from_identify(self):
        if not self.volume_var.get().strip():
            self.volume_var.set("观海拾光")
        self.app.volume_var.set(self.volume_var.get().strip())
        self.app.burn_mode = self.mode_var.get()
        if self.mode_var.get() == "CD" or self.drive.profile not in {3, 6, 8, 9, 14}:
            self.app.show_tab("burn")
            self.close()
            return
        self.show_step(2)

    def _step_2(self):
        card = self._card()
        tk.Label(card, text="准备为光盘建立文件目录", bg=PANEL, fg=TEXT,
                 font=(FONT, 12, "bold")).pack(anchor="w")
        details = (f"目标光驱：{self.drive.drive_text}\n"
                   f"光盘名称：{self.volume_var.get().strip()}\n"
                   "完成后可在 Windows 中直接打开光盘，像 U 盘一样复制文件。软件会自动检查光盘能否正常读取。")
        tk.Label(card, text=details, bg=PANEL, fg=MUTED, justify="left",
                 font=(FONT, 9)).pack(anchor="w", pady=14)
        tk.Label(self.body, text="请确认选择的是目标光驱。准备期间不要弹出光盘、休眠或关闭程序。",
                 bg=BG, fg=DANGER, wraplength=430, justify="left",
                 font=(FONT, 9)).pack(anchor="w", pady=18)
        self._button("上一步", lambda: self.show_step(1)).pack(side="left")
        self._button("开始准备", self.start_format, True).pack(side="right")

    def start_format(self):
        self.working = True
        self.show_step(3)
        volume = self.volume_var.get().strip() or "观海拾光"
        self.app.volume_var.set(volume)
        self.app.run_task(
            "准备空白光盘",
            lambda: self.app.service.format(self.drive.recorder_id, volume, self.app._progress_callback),
            on_complete=self.format_done,
            show_message=False,
        )

    def _step_3(self):
        card = self._card()
        tk.Label(card, text="正在准备光盘…", bg=PANEL, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(card, text="正在建立文件目录，随后会自动检查能否正常读取。\n进度也会同步显示在观海·拾光主面板底部。",
                 bg=PANEL, fg=MUTED, justify="left", font=(FONT, 9)).pack(anchor="w", pady=14)
        self.wizard_percent = tk.Label(card, text="0%", bg=PANEL, fg=ACCENT,
                                       font=("Segoe UI", 20, "bold"))
        self.wizard_percent.pack(anchor="w", pady=(8, 0))
        self.wizard_bar = ttk.Progressbar(card, mode="determinate", maximum=100)
        self.wizard_bar.pack(fill="x", pady=10)
        tk.Label(self.body, text="请不要操作光驱。低速 CD-RW 首次完整格式化可能需要几十分钟。",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(pady=22)
        self._sync_progress()

    def _sync_progress(self):
        if self.step != 3 or not self.winfo_exists():
            return
        value = self.app.last_progress
        if value is not None:
            self.wizard_percent.config(text=f"{value}%")
            self.wizard_bar.config(value=value)
        self.after(200, self._sync_progress)

    def format_done(self, result: OperationResult):
        self.working = False
        if not result.ok:
            self._clear()
            card = self._card()
            tk.Label(card, text="格式化未完成", bg=PANEL, fg=DANGER,
                     font=(FONT, 13, "bold")).pack(anchor="w")
            tk.Label(card, text=result.message, bg=PANEL, fg=MUTED, wraplength=400,
                     justify="left", font=(FONT, 9)).pack(anchor="w", pady=14)
            self._button("返回", lambda: self.show_step(2)).pack(side="right")
            return
        self.app.run_task(
            "后台检查光盘是否可读",
            lambda: self.app.service.list_files(self.drive.recorder_id),
            on_complete=self.verify_done,
            show_message=False,
        )

    def verify_done(self, result: OperationResult):
        if not result.ok:
            self.format_done(OperationResult(False, f"文件目录已写入，但读取检查失败：{result.message}"))
            return
        self.show_step(4)

    def _step_4(self):
        card = self._card()
        tk.Label(card, text="✓  光盘已可用", bg=PANEL, fg=ACCENT,
                 font=(FONT, 16, "bold")).pack(anchor="w")
        tk.Label(card, text="格式化与读取验证均已完成。现在可以拖入文件进行刻录，或进入光盘文件窗口。",
                 bg=PANEL, fg=MUTED, wraplength=400, justify="left",
                 font=(FONT, 9)).pack(anchor="w", pady=16)
        self._button("完成", self.close).pack(side="right")
        self._button("立即添加文件", self.start_burn, True).pack(side="right", padx=(0, 8))

    def start_burn(self):
        self.app.show_tab("burn")
        self.close()

    def close(self):
        if not self.working:
            self.destroy()
