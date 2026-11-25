from __future__ import annotations

import queue
import threading
import tkinter as tk

BG = "#101515"
PANEL = "#19211F"
PANEL_2 = "#26332D"
TEXT = "#F2E8D5"
MUTED = "#B0A58F"
ACCENT = "#D6B56C"
ACCENT_DARK = "#79613A"
BORDER = "#3B4438"
FONT = "Microsoft YaHei UI"

SECTIONS = (
    ("第一课：认识主面板", (
        "观海·拾光固定显示在屏幕右侧。顶部可以选择光驱，下方依次是光盘、刻录、交接和历史四页。",
        "主面板最底部显示当前操作、进度百分比和取消按钮。进行刻录或擦除时，请优先看这里，不要反复点击按钮。",
        "如果任务超过 5 分钟没有任何进度，取消按钮会变成“强制结束任务”：点击后软件立即复位，请重新插拔光驱再试。",
        "收缩为桌面浮动图标后，可直接把文件或文件夹拖到图标上加入刻录队列；多次拖入会累计，单击图标可返回检查。",
        "浮动图标可以用鼠标左键按住拖动，放到任意顺手的位置，位置会自动记住；更换显示器或屏幕布局变化后，图标会自动回到当前屏幕右侧边缘。",
        "按住顶部空白区域可以拖动面板；点置顶按钮可决定是否始终浮在其他窗口上方。",
        "点击右上角关闭不会直接退出，而会收缩为桌面右侧的小图标。单击小图标恢复；在小图标上点右键会弹出菜单，可以选择打开软件、重新检测光驱或彻底退出。",
    )),
    ("第二课：第一次使用与读取光盘", (
        "第一步，把光盘放入光驱并等待光驱停止加速。软件会自动检测，也可以按 F5 立即重新检测。",
        "第二步，确认顶部选中的是正确光驱。如果有多台光驱，请先核对盘符，避免选错。",
        "第三步，按 Ctrl+R 或点击读取光盘。文件目录会直接显示在光盘页内，双击文件夹进入，点击返回光盘可回到介质操作。", 
        "如果识别为空白光盘，软件会进入准备向导。想直接刻录时选择标准光盘；需要反复复制文件且光盘支持擦写时，再选择像 U 盘一样使用。",
        "空白光盘没有文件目录是正常现象。第一次使用时无法直接看到文件，并不代表光盘损坏。",
    )),
    ("第三课：把文件刻录到光盘", (
        "进入刻录页，把文件或文件夹直接拖入虚线区域；也可以按 Ctrl+O 添加文件，按 Ctrl+Shift+O 添加整个文件夹。",
        "文件会以树形目录显示。拖动项目到文件夹上即可调整分类；拖动时目标文件夹会高亮，并明确显示移动到的位置。",
        "用新建文件夹整理结构，选中文件或文件夹按 F2 重命名；按 Delete 只从队列删除，电脑原文件不会受影响。",
        "一键整理只把根目录的散文件按固定顺序分类；已经建立的文件夹和内部结构保持不动。整理后可点击“撤销整理”恢复整理前结构，修改队列后撤销入口会自动失效。",
        "树形图右列显示目录对应和刻录顺序；开始刻录会以暂存目录严格复制这棵树，只含空文件夹时不能开始。",  
        "点击光盘名称标签即可选择用途，例如工作资料、文件交接或重要备份。默认自动带当天日期，便于以后辨认；也可以关闭日期并自行输入名称。",
        "点击开始刻录或按 Ctrl+B。核对光驱、光盘名称和文件数量后再确认。刻录期间不要弹出光盘，不要让电脑休眠或断电。",
        "完成后先查看底部结果，再读取光盘检查文件。标准光盘适合交接和长期保存，也能在其他 Windows 电脑上读取。",
    )),
    ("第四课：导出与保存光盘资料", (
        "只保存部分文件时，在光盘页选中文件或文件夹，点击导出选中；导出整张光盘会处理当前根目录的所有项目。",
        "导出设置默认保留原目录，也可按资料类型、修改月份、文件大小或扩展名自动建立分类文件夹。同名文件会自动编号，不会覆盖旧文件。",
        "保存位置可直接填写或选择。导出完成后点击打开导出目录即可检查结果；整理导出只复制文件，不改变光盘内容。", 
    )),
    ("第五课：擦除与重新准备光盘", (
        "只有明确标注可重复擦写的光盘才能擦除。一次性刻录光盘不能通过软件变成空白盘。",
        "快速擦除主要清除光盘上的目录信息，速度快，适合日常重新使用。执行前必须确认其中的资料已经备份。",
        "深度擦除会清除整张光盘，耗时明显更长。普通重新刻录通常不需要每次深度擦除。",
        "建立 Windows 文件目录适合可重复擦写光盘。准备完成后，可以在 Windows 中像 U 盘一样复制和删除文件。",
        "擦除和重新准备都无法撤销。操作时务必核对目标光驱，不要中途强制结束。",
    )),
    ("第六课：制作 Windows 和麒麟通用交接文件", (
        "进入交接页，填写日期、交接内容和交接人。文件名会按日期、内容、交接人自动组合，便于归档。",
        "加入需要交接的文件，可以使用与刻录页相同的树形编辑：新建文件夹、F2 重命名、Delete 删除和一键整理；生成的 ZIP 会保留编辑后的目录。",
        "设置密码并再次确认，也可以使用随机密码。密码会加密归档在当前 Windows 账户下，仍建议通过其他安全渠道告知接收方。", 
        "选择仅生成，可先把交接文件保存在电脑上；选择生成并刻录，会在生成后直接写入光盘并读回复核。",
        "交接文件统一使用观海·八分 BFQ 格式。软件先保留目录生成 ZIP，再调用八分核心封装；生成后还会实际解包复核。",
        "Windows 与银河麒麟使用各自平台的观海·八分核心恢复同一个 BFQ 文件，不需要联网。交接页也可选择已有 BFQ，输入密码并恢复到指定目录。", 
    )),
    ("第七课：快捷键速查", (
        "Ctrl+1、Ctrl+2、Ctrl+3、Ctrl+4 分别打开光盘、刻录、交接和历史。F1 随时打开教程，F5 重新检测光驱。",
        "Ctrl+R 读取光盘，Ctrl+E 整盘导出，Ctrl+J 弹出光盘，Ctrl+B 开始刻录。",
        "Ctrl+O 添加文件，Ctrl+Shift+O 添加文件夹，Delete 移除选中项，Ctrl+Shift+Delete 清空列表。",
        "Ctrl+Shift+X 快速擦除，Ctrl+Shift+D 深度擦除，Ctrl+Shift+F 建立 Windows 文件目录。",
        "Ctrl+T 换皮肤，Ctrl+P 切换置顶，Ctrl+句点取消当前操作，Esc 收缩为桌面图标。",
        "交接页中，Ctrl+G 生成随机密码，Ctrl+Shift+C 复制密码，Ctrl+K 查看密码归档，Ctrl+Shift+B 生成并刻录。",
    )),
    ("第八课：常见问题处理", (
        "检测不到光驱时，先确认光驱在 Windows 设备管理器中正常，再按 F5。外置光驱还要检查供电和数据线。",
        "能检测到光驱但读不出文件时，确认光盘确实有内容、盘面没有严重划痕，并等待光驱完成读取。",
        "无法刻录时，检查光盘是否支持写入、是否已经封盘、剩余空间是否足够，以及所选文件是否仍然存在。",
        "擦除失败时，先确认光盘是否支持重复擦写。一次性光盘不能擦除，已经有严重损伤的光盘也不应继续用于重要资料。",
        "交接文件打不开时，更换新版浏览器再试；提示密码错误时，注意完整输入，不要多复制空格。",
        "如果操作已经异常中断，不要立即重复写入。先重新检测光盘状态，再决定读取、重新准备或更换光盘。",
    )),
    ("第九课：历史与安全建议", (
        "历史页保存本机操作时间、功能和结果，方便排查问题。它不会代替文件备份，也不会保存光盘里的完整文件。",
        "重要资料建议至少保留两份，不要只保存在一张光盘上。交接前抽查文件，交接后妥善保管密码。",
        "清空历史需要确认；彻底退出可使用历史页按钮，或在桌面浮动图标上点右键选择“彻底退出”。光盘任务进行中不建议强制退出。",
    )),
)


class LocalSpeech:
    """使用 Windows 本机语音组件；所有 COM 调用都留在同一后台线程。"""

    def __init__(self, on_status):
        self.on_status = on_status
        self.jobs = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _clear_jobs(self):
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                break

    def _worker(self):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            while True:
                title, lines = self.jobs.get()
                if title is None:
                    break
                self.stop_event.clear()
                self.on_status("正在朗读：" + title)
                voice.Speak(title + "。" + "\n".join(lines), 1)
                while not voice.WaitUntilDone(100):
                    if self.stop_event.is_set():
                        voice.Speak("", 3)
                        break
                if self.stop_event.is_set():
                    self._clear_jobs()
            self.on_status("朗读已停止")
        except Exception as exc:
            self.on_status("本机语音暂不可用：" + str(exc))
        finally:
            pythoncom.CoUninitialize()

    def play(self, title, lines, replace=True):
        if replace:
            self.stop(clear_status=False)
        self.jobs.put((title, lines))

    def stop(self, clear_status=True):
        self.stop_event.set()
        self._clear_jobs()
        if clear_status:
            self.on_status("朗读已停止")

    def close(self):
        self.stop()
        self.jobs.put((None, ()))


class HelpWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.title("观海·拾光 · 详细教学")
        self.configure(bg=BG)
        self.transient(app.root)
        scale = app.ui_scale
        width, height = int(680 * scale), int(700 * scale)
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, app.root.winfo_x() - width - int(14 * scale))
        y = max(0, min(app.root.winfo_y(), screen_h - height))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.speech = LocalSpeech(self._speech_status)
        header = tk.Frame(self, bg=BG, padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="详细教学 · 本地语音讲解", bg=BG, fg=TEXT,
                 font=(FONT, 15, "bold")).pack(side="left")
        tk.Label(header, text="F1 打开 · Esc 关闭", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="right", pady=5)
        controls = tk.Frame(self, bg=BG, padx=20)
        controls.pack(fill="x", pady=(0, 10))
        self._button(controls, "▶ 连续播放全部课程", self.play_all, True).pack(side="left")
        self._button(controls, "■ 停止朗读", lambda: self.speech.stop()).pack(side="left", padx=8)
        self.speech_label = tk.Label(self, text="点击每章的“朗读本章”，即可离线收听",
                                     bg=BG, fg=ACCENT, anchor="w", padx=20, font=(FONT, 9))
        self.speech_label.pack(fill="x", pady=(0, 8))
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=BG, padx=20)
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        for title, lines in SECTIONS:
            card = tk.Frame(body, bg=PANEL, padx=16, pady=13,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", pady=(0, 10))
            heading = tk.Frame(card, bg=PANEL)
            heading.pack(fill="x")
            tk.Label(heading, text=title, bg=PANEL, fg=ACCENT,
                     font=(FONT, 11, "bold"), anchor="w").pack(side="left")
            self._button(heading, "朗读本章", lambda t=title, l=lines: self.speech.play(t, l)).pack(side="right")
            for line in lines:
                tk.Label(card, text=line, bg=PANEL, fg=TEXT, justify="left",
                         wraplength=width - int(74 * scale), anchor="w",
                         font=(FONT, 9)).pack(fill="x", pady=(7, 0))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self.focus_set()

    @staticmethod
    def _button(parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT_DARK if primary else PANEL_2,
                         fg=TEXT, activebackground=ACCENT_DARK, activeforeground="#FFFFFF",
                         relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                         padx=10, pady=5, font=(FONT, 8, "bold" if primary else "normal"))

    def _speech_status(self, text):
        if self.winfo_exists():
            self.after(0, lambda: self.speech_label.config(text=text) if self.winfo_exists() else None)

    def play_all(self):
        self.speech.stop(clear_status=False)
        while not self.speech.jobs.empty():
            try:
                self.speech.jobs.get_nowait()
            except queue.Empty:
                break
        for title, lines in SECTIONS:
            self.speech.play(title, lines, replace=False)

    def close(self):
        self.speech.close()
        self.destroy()
