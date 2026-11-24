from __future__ import annotations
import math
import random
import time
import tkinter as tk

class StartupSplash:
    VARIANTS = ("tide", "rays", "stars", "ripples")
    def __init__(self, root, logo_path, on_complete, variant=None):
        self.root, self.on_complete = root, on_complete
        self.variant = variant if variant in self.VARIANTS else random.SystemRandom().choice(self.VARIANTS)
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.width, self.height = int(420*self.scale), min(int(720*self.scale), root.winfo_screenheight()-70)
        self.canvas = tk.Canvas(root, width=self.width, height=self.height, bg="#101515", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.logo = tk.PhotoImage(file=logo_path).subsample(4)
        self.started, self.finished = time.monotonic(), False
        c = self.width/2
        self.canvas.create_text(c, self.height*.70, text="观海·拾光", fill="#F2E8D5", font=("Noto Sans CJK SC", int(26*self.scale), "bold"))
        self.canvas.create_text(c, self.height*.755, text="GUANHAI · SHIGUANG · KYLIN", fill="#C9B991", font=("DejaVu Sans", int(9*self.scale)))
        self.canvas.create_text(c, self.height*.805, text="光盘读写中枢", fill="#93A69B", font=("Noto Sans CJK SC", int(10*self.scale)))
        self.canvas.create_text(c, self.height*.91, text="海光相映，静候启程 · 点击跳过", fill="#887F6C", font=("Noto Sans CJK SC", int(8*self.scale)))
        self.canvas.bind("<Button-1>", lambda _e:self.finish())
        self._animate()
    def _waves(self, elapsed, rows=3):
        for row, color in enumerate(("#6FA89A", "#D6B56C", "#8D784A")[:rows]):
            points=[]
            for x in range(-10,self.width+11,8):
                y=self.height*(.54+row*.032)+math.sin(x/(42*self.scale)+elapsed*2.2+row)*(8-row)*self.scale
                points.extend((x,y))
            self.canvas.create_line(*points, fill=color, width=2, smooth=True, tags="sea")
    def _animate(self):
        if self.finished or not self.canvas.winfo_exists(): return
        e=time.monotonic()-self.started
        if e>=2.1: self.finish(); return
        self.canvas.delete("sea"); cx,cy=self.width/2,self.height*.37
        if self.variant=="tide":
            for i in range(5,0,-1):
                r=(66+i*10)*self.scale; self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r,outline="#6E644B",tags="sea")
        elif self.variant=="rays":
            for i in range(24):
                a=i*math.tau/24+e*.12; r1,r2=90*self.scale,(110+i%3*8)*self.scale
                self.canvas.create_line(cx+math.cos(a)*r1,cy+math.sin(a)*r1,cx+math.cos(a)*r2,cy+math.sin(a)*r2,fill="#D6B56C",tags="sea")
        elif self.variant=="stars":
            for i in range(38):
                x=(i*83+27)%400*self.scale; y=(.12+(i*47%390)/1000)*self.height
                self.canvas.create_oval(x,y,x+2,y+2,fill="#D6B56C",outline="",tags="sea")
        else:
            for i in range(6):
                r=(85+(i*27+e*32)%150)*self.scale; self.canvas.create_oval(cx-r,cy-r*.4,cx+r,cy+r*.4,outline="#6E644B",tags="sea")
        self._waves(e); self.canvas.create_image(cx,cy,image=self.logo,tags="sea")
        self.root.after(40,self._animate)
    def finish(self):
        if self.finished:return
        self.finished=True
        if self.canvas.winfo_exists():self.canvas.destroy()
        self.on_complete()
