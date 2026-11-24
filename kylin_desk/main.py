from __future__ import annotations
import os, queue, subprocess, sys, threading, time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = TkinterDnD = None
from optical.models import DriveInfo, OperationResult, format_size
from optical.linux_service import DiscService, dependency_message, split_dnd_paths
from history import HistoryStore
from splash import StartupSplash
from themes import THEMES, apply_theme, load_theme, save_theme

APP_NAME, APP_VERSION = "观海·拾光", "0.0.1"
BG="#101515"; PANEL="#19211F"; PANEL_2="#26332D"; PANEL_HOVER="#34453C"
TEXT="#F2E8D5"; MUTED="#B0A58F"; ACCENT="#D6B56C"; ACCENT_DARK="#79613A"
DANGER="#D88A80"; SUCCESS="#8DB9A2"; BORDER="#3B4438"; FONT="Noto Sans CJK SC"

def resource_path(name):
    return str(Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))/name)

class Button(tk.Button):
    def __init__(self,master,text,command,kind="secondary",**kw):
        colors={"primary":(ACCENT_DARK,"#fff",PANEL_HOVER),"secondary":(PANEL_2,TEXT,PANEL_HOVER),"danger":("#422635","#FECDD3","#71324A"),"ghost":(BG,MUTED,PANEL_2)}
        bg,fg,active=colors[kind]; opts={"font":(FONT,9),"padx":9,"pady":8};opts.update(kw)
        super().__init__(master,text=text,command=command,bg=bg,fg=fg,activebackground=active,activeforeground="#fff",relief="flat",bd=0,highlightthickness=0,cursor="hand2",**opts)

class DiscBrowser(tk.Toplevel):
    def __init__(self,app,device):
        super().__init__(app.root);self.app=app;self.device=device;self.relative="";self.entries=[]
        self.title("观海·拾光 · 光盘文件");self.geometry("800x550");self.configure(bg=BG)
        head=tk.Frame(self,bg=BG,padx=18,pady=14);head.pack(fill="x")
        tk.Label(head,text="光盘文件",bg=BG,fg=TEXT,font=(FONT,14,"bold")).pack(side="left")
        Button(head,"整盘导出",self.export_disc,"primary").pack(side="right")
        Button(head,"导出选中",self.export_selected).pack(side="right",padx=8)
        nav=tk.Frame(self,bg=BG,padx=18);nav.pack(fill="x",pady=(0,12))
        Button(nav,"← 上级",self.go_up,"ghost").pack(side="left")
        self.path_label=tk.Label(nav,text="光盘根目录",bg=BG,fg=MUTED,font=(FONT,9));self.path_label.pack(side="left",padx=10)
        body=tk.Frame(self,bg=BG,padx=18);body.pack(fill="both",expand=True)
        self.tree=ttk.Treeview(body,columns=("size","modified"),show="tree headings",selectmode="extended")
        self.tree.heading("#0",text="名称");self.tree.heading("size",text="大小");self.tree.heading("modified",text="修改时间")
        self.tree.column("#0",width=430);self.tree.column("size",width=110);self.tree.column("modified",width=150)
        self.tree.pack(fill="both",expand=True);self.tree.bind("<Double-1>",self.open_selected)
        self.status=tk.Label(self,text="正在读取…",bg=BG,fg=MUTED,padx=18,pady=12);self.status.pack(fill="x")
        Button(self,"刷新",self.load,"ghost").pack();self.load()
    def load(self):
        try:
            self.entries=self.app.service.list_files(self.device,self.relative);self.tree.delete(*self.tree.get_children())
            for i,e in enumerate(self.entries):self.tree.insert("","end",iid=str(i),text=("文件夹  " if e.is_dir else "文件  ")+e.name,values=("—" if e.is_dir else format_size(e.size),time.strftime("%Y-%m-%d %H:%M",time.localtime(e.modified))))
            self.path_label.config(text=self.relative or "光盘根目录");self.status.config(text=f"{len(self.entries)} 个项目 · 双击打开")
        except Exception as exc:self.status.config(text=str(exc));messagebox.showerror(APP_NAME,str(exc),parent=self)
    def go_up(self):
        if self.relative:self.relative=str(Path(self.relative).parent);self.relative="" if self.relative=="." else self.relative;self.load()
    def open_selected(self,_=None):
        if not self.tree.selection():return
        e=self.entries[int(self.tree.selection()[0])]
        if e.is_dir:self.relative=str(Path(self.relative)/e.name) if self.relative else e.name;self.load()
        else:
            try:subprocess.Popen(["xdg-open",str(e.path)])
            except OSError as exc:messagebox.showerror(APP_NAME,f"无法调用系统打开方式：{exc}",parent=self)
    def export_selected(self):
        dest=filedialog.askdirectory(parent=self)
        if dest and self.tree.selection():self.app.run_task("导出文件",lambda:self.app.service.export_files([self.entries[int(i)].path for i in self.tree.selection()],dest,self.app.progress_callback))
    def export_disc(self):
        dest=filedialog.askdirectory(parent=self)
        if dest:self.app.run_task("整盘导出",lambda:self.app.service.export_disc(self.device,dest,self.app.progress_callback))

class KylinApp:
    def __init__(self):
        self.theme_key=load_theme();apply_theme(self.theme_key,globals())
        root_class=TkinterDnD.Tk if TkinterDnD else tk.Tk;self.root=root_class()
        self.root.title(f"{APP_NAME} v{APP_VERSION} · Kylin");self.root.overrideredirect(True);self.root.attributes("-topmost",True);self.root.configure(bg=BORDER)
        self.service=DiscService();self.history=HistoryStore();self.drives=[];self.selected_drive=None;self.sources=[];self.busy=False;self.refreshing=False
        self.events=queue.Queue();self.topmost=True;self.last_progress=None;self._timer=None;self._drag_origin=(0,0);self._place_right()
        self.root.bind("<Escape>",lambda _e:self.close());self.splash=StartupSplash(self.root,resource_path("discore_512.png"),self._complete)
    def _complete(self):
        self._style();self._build();self.root.after(100,self.refresh);self.root.after(100,self._poll)
        msg=dependency_message(self.service.tools())
        if msg:self.root.after(400,lambda:messagebox.showwarning(APP_NAME,msg,parent=self.root))
    def _style(self):
        s=ttk.Style();s.theme_use("clam");s.configure("TCombobox",fieldbackground=PANEL_2,foreground=TEXT,padding=8)
        s.configure("Horizontal.TProgressbar",troughcolor=PANEL_2,background=ACCENT,thickness=5)
        s.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=30)
        s.configure("Treeview.Heading",background=PANEL_2,foreground=TEXT)
    def _build(self):
        outer=tk.Frame(self.root,bg=BG,padx=1,pady=1);outer.pack(fill="both",expand=True)
        h=tk.Frame(outer,bg=BG,height=76,padx=17);h.pack(fill="x");h.pack_propagate(False)
        h.bind("<Button-1>",self._start_drag);h.bind("<B1-Motion>",self._drag)
        self.logo=tk.PhotoImage(file=resource_path("discore_64.png"));tk.Label(h,image=self.logo,bg=BG).pack(side="left",pady=6)
        tk.Label(h,text=APP_NAME,bg=BG,fg=TEXT,font=(FONT,15,"bold")).pack(side="left",padx=10)
        close=tk.Label(h,text="×",bg=BG,fg=MUTED,font=("Arial",20));close.pack(side="right");close.bind("<Button-1>",lambda _e:self.close())
        self.pin=Button(h,"● 已置顶",self.toggle_top,"primary",pady=4);self.pin.pack(side="right",padx=10)
        row=tk.Frame(outer,bg=BG,padx=17);row.pack(fill="x",pady=(0,11));self.drive_box=ttk.Combobox(row,state="readonly");self.drive_box.pack(side="left",fill="x",expand=True);self.drive_box.bind("<<ComboboxSelected>>",self.select_drive);Button(row,"刷新",self.refresh,"ghost").pack(side="right")
        tabs=tk.Frame(outer,bg=PANEL,padx=4,pady=4);tabs.pack(fill="x",padx=17,pady=(0,12));self.tab_buttons={}
        for key,label in (("disc","光盘"),("burn","刻录"),("themes","皮肤"),("history","记录")):
            b=Button(tabs,label,lambda k=key:self.show_tab(k),"ghost",pady=6);b.pack(side="left",fill="x",expand=True,padx=2);self.tab_buttons[key]=b
        self.content=tk.Frame(outer,bg=BG,padx=17);self.content.pack(fill="both",expand=True)
        self.pages={k:tk.Frame(self.content,bg=BG) for k in ("disc","burn","themes","history")};self._disc();self._burn();self._themes();self._history()
        footer=tk.Frame(outer,bg=BG,padx=17,pady=11);footer.pack(fill="x",side="bottom");txt=tk.Frame(footer,bg=BG);txt.pack(fill="x")
        self.progress_label=tk.Label(txt,text="就绪",bg=BG,fg=MUTED,font=(FONT,8));self.progress_label.pack(side="left",fill="x",expand=True)
        self.percent=tk.Label(txt,text="",bg=BG,fg=ACCENT,font=("DejaVu Sans",12,"bold"));self.percent.pack(side="right")
        pr=tk.Frame(footer,bg=BG);pr.pack(fill="x",pady=5);self.progress=ttk.Progressbar(pr,maximum=100);self.progress.pack(side="left",fill="x",expand=True);Button(pr,"取消",self.cancel,"ghost",pady=2).pack(side="right")
        self.show_tab("disc")
    def title(self,page,text,hint=""):
        r=tk.Frame(page,bg=BG);r.pack(fill="x",pady=(0,7));tk.Label(r,text=text,bg=BG,fg=TEXT,font=(FONT,9,"bold")).pack(side="left");tk.Label(r,text=hint,bg=BG,fg=MUTED,font=(FONT,8)).pack(side="right")
    def _disc(self):
        p=self.pages["disc"];self.title(p,"当前介质","CD 优先 · 自动检测");card=tk.Frame(p,bg=PANEL,padx=15,pady=15,highlightbackground=BORDER,highlightthickness=1);card.pack(fill="x")
        self.media=tk.Label(card,text="正在检测…",bg=PANEL,fg=TEXT,font=(FONT,12,"bold"));self.media.pack(fill="x")
        self.profile=tk.Label(card,text="—",bg=PANEL,fg=MUTED);self.profile.pack(fill="x",pady=6);self.space=ttk.Progressbar(card,maximum=100);self.space.pack(fill="x");self.space_label=tk.Label(card,text="容量 —",bg=PANEL,fg=MUTED);self.space_label.pack(fill="x",pady=7)
        self.title(p,"读取与管理","使用系统挂载点")
        a=tk.Frame(p,bg=BG);a.pack(fill="x",pady=10)
        for i,(text,cmd) in enumerate((("读取光盘",self.browse),("整盘导出",self.export_disc),("弹出光盘",self.eject),("重新检测",self.refresh))):Button(a,text,cmd,"primary" if i==0 else "secondary").grid(row=i//2,column=i%2,sticky="ew",padx=4,pady=4)
        a.columnconfigure(0,weight=1);a.columnconfigure(1,weight=1)
        self.title(p,"介质维护","操作前请核对目标")
        Button(p,"快速擦除光盘",self.erase,"danger").pack(fill="x",pady=4);Button(p,"完整擦除（较慢）",lambda:self.erase(True),"danger").pack(fill="x",pady=4);Button(p,"初始化 UDF 可重写目录",self.format,"primary").pack(fill="x",pady=4)
        tk.Label(p,text="擦除和 UDF 初始化会改写介质。操作前请卸载光盘；\n读取光盘需由麒麟桌面先挂载。",bg=BG,fg=MUTED,justify="left").pack(fill="x",pady=12)
    def _burn(self):
        p=self.pages["burn"];self.title(p,"新建刻录","ISO/Joliet · CD 优先")
        self.drop=tk.Canvas(p,height=112,bg=PANEL,highlightthickness=1,highlightbackground=ACCENT_DARK);self.drop.pack(fill="x");self.drop.create_text(190,40,text="把文件或文件夹拖到这里",fill=TEXT,font=(FONT,12,"bold"));self.drop.create_text(190,75,text="或点击选择文件",fill=MUTED);self.drop.bind("<Button-1>",lambda _e:self.add_files());self.drop.bind("<Configure>",self._drop_resize)
        if DND_FILES:self.drop.drop_target_register(DND_FILES);self.drop.dnd_bind("<<Drop>>",self.on_drop)
        nr=tk.Frame(p,bg=BG);nr.pack(fill="x",pady=10);tk.Label(nr,text="卷标",bg=BG,fg=MUTED).pack(side="left");self.volume=tk.StringVar(value="GUANHAI_DISC");tk.Entry(nr,textvariable=self.volume,bg=PANEL_2,fg=TEXT,insertbackground=TEXT).pack(side="left",fill="x",expand=True,padx=10)
        self.mode=tk.StringVar(value="CD");modes=tk.Frame(p,bg=BG);modes.pack(fill="x")
        for text,value in (("CD / ISO+Joliet（推荐）","CD"),("UDF 写入","UDF")):tk.Radiobutton(modes,text=text,variable=self.mode,value=value,bg=BG,fg=TEXT,selectcolor=PANEL_2,font=(FONT,9)).pack(side="left")
        self.sources_list=tk.Listbox(p,bg=PANEL,fg=TEXT,selectbackground=ACCENT_DARK,height=7,relief="flat");self.sources_list.pack(fill="both",expand=True,pady=10)
        br=tk.Frame(p,bg=BG);br.pack(fill="x");Button(br,"+ 文件",self.add_files).pack(side="left",expand=True,fill="x");Button(br,"+ 文件夹",self.add_folder).pack(side="left",expand=True,fill="x");Button(br,"移除",self.remove_sources,"ghost").pack(side="left");Button(br,"清空",self.clear_sources,"ghost").pack(side="left")
        self.summary=tk.Label(p,text="刻录队列为空",bg=BG,fg=MUTED);self.summary.pack(fill="x",pady=8);Button(p,"开始刻录",self.burn,"primary",pady=11).pack(fill="x")
        if not DND_FILES:tk.Label(p,text="未安装 tkinterdnd2：仍可点击添加文件",bg=BG,fg=MUTED,font=(FONT,8)).pack()
    def _themes(self):
        p=self.pages["themes"];self.title(p,"面板皮肤","即时切换 · 自动记住")
        for key,v in THEMES.items():Button(p,f"{v['name']}  ·  {v['description']}",lambda k=key:self.set_theme(k),"primary" if key==self.theme_key else "secondary").pack(fill="x",pady=5)
    def _history(self):
        p=self.pages["history"];self.title(p,"本机操作记录","最多 100 条");self.history_list=tk.Listbox(p,bg=PANEL,fg=TEXT,selectbackground=ACCENT_DARK,relief="flat");self.history_list.pack(fill="both",expand=True);Button(p,"清空记录",self.clear_history).pack(fill="x",pady=8);Button(p,"退出观海·拾光",self.force_close,"danger").pack(fill="x")
    def _place_right(self):
        self.root.update_idletasks();w=420;h=min(720,self.root.winfo_screenheight()-70);self.root.geometry(f"{w}x{h}+{self.root.winfo_screenwidth()-w-22}+{max(24,(self.root.winfo_screenheight()-h)//2)}")
    def _start_drag(self,e):self._drag_origin=(e.x_root-self.root.winfo_x(),e.y_root-self.root.winfo_y())
    def _drag(self,e):self.root.geometry(f"+{e.x_root-self._drag_origin[0]}+{e.y_root-self._drag_origin[1]}")
    def _drop_resize(self,e):
        for item in self.drop.find_all():self.drop.coords(item,e.width/2,40 if item==1 else 75)
    def toggle_top(self):self.topmost=not self.topmost;self.root.attributes("-topmost",self.topmost);self.pin.config(text="● 已置顶" if self.topmost else "○ 未置顶")
    def show_tab(self,key):
        for k,p in self.pages.items():p.pack_forget();self.tab_buttons[k].config(bg=PANEL_2 if k==key else PANEL)
        self.pages[key].pack(fill="both",expand=True)
        if key=="history":self.reload_history()
    def set_theme(self,key):
        if self.busy:return
        save_theme(key);apply_theme(key,globals())
        for child in self.root.winfo_children():child.destroy()
        self._style();self._build();self._apply(self.drives);self._reload_sources();self.show_tab("themes")
    def select_drive(self,_=None):
        i=self.drive_box.current()
        if 0<=i<len(self.drives):self.selected_drive=self.drives[i];self._drive_card()
    def _drive_card(self):
        d=self.selected_drive
        if not d:self.media.config(text="未检测到光驱");self.profile.config(text="请检查设备连接");self.space_label.config(text="容量 —");return
        self.media.config(text=d.status,fg=SUCCESS if d.present else MUTED);self.profile.config(text=f"{d.profile_name} · {d.device} · {d.file_system or '未挂载'}");self.space_label.config(text=f"容量 {format_size(d.capacity_bytes)} · 可用 {format_size(d.free_bytes)}");self.space.config(value=100*(d.capacity_bytes-d.free_bytes)/d.capacity_bytes if d.capacity_bytes else 0)
    def refresh(self):
        if self.busy or self.refreshing:return
        self.refreshing=True;self.progress_label.config(text="正在只读检测光驱…")
        def worker():
            try:self.events.put(("refreshed",self.service.list_drives()))
            except Exception as e:self.events.put(("refresh_error",str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def _poll(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=="refreshed":self.refreshing=False;self._apply(payload)
                elif kind=="refresh_error":self.refreshing=False;self.progress_label.config(text=payload)
                elif kind=="progress":
                    text,value=payload;self.progress_label.config(text=text);self.percent.config(text=f"{value}%" if value is not None else "处理中")
                    if value is not None:self.progress.stop();self.progress.config(mode="determinate",value=value)
                elif kind=="done":self._done(*payload)
        except queue.Empty:pass
        if self.root.winfo_exists():self.root.after(100,self._poll)
    def _apply(self,drives):
        old=self.selected_drive.device if self.selected_drive else "";self.drives=drives;self.drive_box.config(values=[f"{d.device} | {d.name}" for d in drives]);i=next((i for i,d in enumerate(drives) if d.device==old),0 if drives else -1);self.selected_drive=drives[i] if i>=0 else None
        if i>=0:self.drive_box.current(i)
        self._drive_card();self.progress_label.config(text=f"检测到 {len(drives)} 个光驱" if drives else "未检测到光驱")
        if self._timer:self.root.after_cancel(self._timer)
        self._timer=self.root.after(5000,self.refresh)
    def require_drive(self,writable=False,erasable=False):
        d=self.selected_drive
        if not d:messagebox.showinfo(APP_NAME,"未检测到光驱。");return None
        if not d.present:messagebox.showinfo(APP_NAME,"请先放入光盘。");return None
        if writable and not d.writable:messagebox.showwarning(APP_NAME,"当前设备未报告写入能力。");return None
        if erasable and not d.erasable:messagebox.showwarning(APP_NAME,"当前介质未报告可重写能力。CD-R/DVD±R 不可擦除。");return None
        if (writable or erasable) and d.mountpoint:messagebox.showwarning(APP_NAME,"请先在麒麟文件管理器中卸载（不是弹出）光盘，再执行写操作。");return None
        return d
    def run_task(self,op,func):
        if self.busy:messagebox.showinfo(APP_NAME,"已有操作正在进行。");return
        self.busy=True;self.progress.config(mode="indeterminate");self.progress.start(12)
        def worker():
            try:r=func()
            except Exception as e:r=OperationResult(False,str(e))
            self.events.put(("done",(op,r)))
        threading.Thread(target=worker,daemon=True).start()
    def _done(self,op,r):
        self.busy=False;self.progress.stop();self.progress.config(mode="determinate",value=100 if r.ok else 0);self.progress_label.config(text=r.message);self.percent.config(text="100%" if r.ok else "失败");self.history.add(op,r.ok,r.message);messagebox.showinfo(APP_NAME,r.message) if r.ok else messagebox.showerror(APP_NAME,r.message);self.refresh()
    def progress_callback(self,text,value):self.events.put(("progress",(text,value)))
    def cancel(self):
        if self.busy:self.service.cancel()
    def browse(self):
        d=self.require_drive()
        if d:
            if d.blank:messagebox.showinfo(APP_NAME,"空白光盘请在“刻录”页添加文件。");self.show_tab("burn")
            else:DiscBrowser(self,d.device)
    def export_disc(self):
        d=self.require_drive();dest=filedialog.askdirectory() if d else ""
        if dest:self.run_task("整盘导出",lambda:self.service.export_disc(d.device,dest,self.progress_callback))
    def eject(self):
        d=self.require_drive()
        if d:self.run_task("弹出光盘",lambda:self.service.eject(d.device))
    def erase(self,full=False):
        d=self.require_drive(erasable=True)
        if d and messagebox.askyesno(APP_NAME,f"即将{'完整' if full else '快速'}擦除 {d.device}，数据无法恢复。\n请再次核对目标，确定继续吗？"):self.run_task("擦除光盘",lambda:self.service.erase(d.device,full,self.progress_callback))
    def format(self):
        d=self.require_drive(writable=True,erasable=True)
        if d and messagebox.askyesno(APP_NAME,f"将在 {d.device} 初始化 UDF，现有目录将不可用。\n确定继续吗？"):self.run_task("初始化 UDF",lambda:self.service.format(d.device,self.volume.get(),self.progress_callback))
    def add_files(self):self._add(Path(x) for x in filedialog.askopenfilenames())
    def add_folder(self):
        p=filedialog.askdirectory()
        if p:self._add([Path(p)])
    def on_drop(self,e):self._add(split_dnd_paths(e.data,self.root.tk.splitlist));return e.action
    def _add(self,paths):
        names={p.name.casefold() for p in self.sources}
        for p in paths:
            if p.exists() and p.name.casefold() not in names:self.sources.append(p);names.add(p.name.casefold())
        self._reload_sources();self.show_tab("burn")
    def remove_sources(self):
        selected=set(self.sources_list.curselection());self.sources=[p for i,p in enumerate(self.sources) if i not in selected];self._reload_sources()
    def clear_sources(self):self.sources.clear();self._reload_sources()
    def _reload_sources(self):
        self.sources_list.delete(0,"end")
        for p in self.sources:self.sources_list.insert("end",("文件夹  " if p.is_dir() else "文件  ")+str(p))
        self.summary.config(text=f"队列：{len(self.sources)} 个根目录项目" if self.sources else "刻录队列为空")
    def burn(self):
        d=self.require_drive(writable=True)
        if not d:return
        if not self.sources:messagebox.showinfo(APP_NAME,"请先添加文件。");return
        if d.mountpoint:return
        if messagebox.askokcancel(APP_NAME,f"目标 {d.device}\n模式 {self.mode.get()}\n项目 {len(self.sources)} 个\n\n确认刻录吗？"):self.run_task("刻录光盘",lambda:self.service.burn(d.device,list(self.sources),self.volume.get(),True,self.progress_callback,self.mode.get()))
    def reload_history(self):
        self.history_list.delete(0,"end")
        for r in self.history.load():self.history_list.insert("end",f"{r['time'][5:16]}  {r['operation']} · {r['status']}")
    def clear_history(self):
        if messagebox.askyesno(APP_NAME,"清空操作记录？"):self.history.clear();self.reload_history()
    def close(self):self.root.iconify()
    def force_close(self):
        if not self.busy or messagebox.askyesno(APP_NAME,"任务尚未结束，仍要退出吗？"):self.root.destroy()
    def run(self):self.root.mainloop()

def main():
    if not sys.platform.startswith("linux"):
        print("当前源码面向银河麒麟 V10 / Linux；Windows 上仅运行静态与模拟测试。")
        return 1
    try:KylinApp().run();return 0
    except tk.TclError as e:print(f"无法启动图形界面：{e}\n请确认麒麟系统已安装 Tk 和图形桌面。");return 1
if __name__=="__main__":raise SystemExit(main())
