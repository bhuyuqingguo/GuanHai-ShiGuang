from __future__ import annotations

import json
import math
from fractions import Fraction
import os
import random
import time
import tkinter as tk
from pathlib import Path

try:
    import winsound
except ImportError:
    winsound = None


class StartupSplash:
    """在原面板位置随机播放轻量海光动画；保留统一字体并避免连续重复。"""

    VARIANTS = ("tide", "rays", "stars", "ripples")
    SETTINGS = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OpticalDesk" / "settings.json"

    def __init__(self, root, logo_path, on_complete, sound_path=None, variant=None):
        self.root = root
        self.on_complete = on_complete
        self.sound_path = sound_path
        self.sound_playing = False
        self.variant = variant if variant in self.VARIANTS else self._choose_variant()
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.width = int(420 * self.scale)
        self.height = min(int(760 * self.scale), root.winfo_screenheight() - int(70 * self.scale))
        self.canvas = tk.Canvas(root, width=self.width, height=self.height,
                                bg="#101515", highlightthickness=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        logo_ratio = Fraction(self.scale).limit_denominator(8)
        self.logo = tk.PhotoImage(file=logo_path).zoom(logo_ratio.numerator).subsample(4 * logo_ratio.denominator)
        self.started = time.monotonic()
        self.finished = False
        self.canvas.bind("<Button-1>", lambda _e: self.finish())
        center = self.width / 2
        self.canvas.create_text(center, self.height * 0.70, text="观海·拾光",
                                fill="#F2E8D5", font=("Microsoft YaHei UI", max(16, int(20 * self.scale)), "bold"))
        self.canvas.create_text(center, self.height * 0.742, text="GUANHAI · SHIGUANG · 0.0.25",
                                fill="#C9B991", font=("Segoe UI", max(7, int(8 * self.scale))))
        self.canvas.create_text(center, self.height * 0.782, text="光盘读写中枢",
                                fill="#93A69B", font=("Microsoft YaHei UI", max(8, int(9 * self.scale))))
        self.canvas.create_line(center - 24 * self.scale, self.height * 0.852,
                                center + 24 * self.scale, self.height * 0.852,
                                fill="#6E644B", width=max(1, int(self.scale)))
        self.canvas.create_text(center, self.height * 0.91, text="海光相映，静候启程　·　点击跳过",
                                fill="#887F6C", font=("Microsoft YaHei UI", int(8 * self.scale)))
        self._play_sound()
        self._animate()

    def _choose_variant(self):
        previous = None
        data = {}
        try:
            data = json.loads(self.SETTINGS.read_text(encoding="utf-8"))
            previous = data.get("last_splash")
        except (OSError, ValueError, TypeError):
            pass
        choices = [name for name in self.VARIANTS if name != previous] or list(self.VARIANTS)
        selected = random.SystemRandom().choice(choices)
        try:
            self.SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            if not isinstance(data, dict):
                data = {}
            data["last_splash"] = selected
            self.SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        return selected

    def _play_sound(self):
        if not winsound or not self.sound_path:
            return
        try:
            winsound.PlaySound(self.sound_path,
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            self.sound_playing = True
        except (OSError, RuntimeError):
            pass

    def _waves(self, elapsed, rows=3):
        for row, color in enumerate(("#6FA89A", "#D6B56C", "#8D784A")[:rows]):
            points = []
            baseline = self.height * (0.54 + row * 0.032)
            for x in range(-10, self.width + 11, 8):
                y = baseline + math.sin(x / (42 * self.scale) + elapsed * 2.2 + row) * (8 - row) * self.scale
                points.extend((x, y))
            self.canvas.create_line(*points, fill=color, width=max(2, int((3-row/2)*self.scale)),
                                    smooth=True, tags="sea")

    def _draw_tide(self, elapsed, cx, cy, pulse):
        for i in range(5, 0, -1):
            radius = (66 + i * 10 + pulse * 6) * self.scale
            shade = 32 + (5 - i) * 6
            color = f"#{shade + 20:02x}{shade + 15:02x}{shade:02x}"
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    outline=color, width=max(1, int(self.scale)), tags="sea")
        self._waves(elapsed)

    def _draw_rays(self, elapsed, cx, cy, pulse):
        for index in range(24):
            angle = index * math.tau / 24 + elapsed * 0.12
            inner = (91 + pulse * 3) * self.scale
            outer = (110 + (index % 3) * 8 + pulse * 8) * self.scale
            self.canvas.create_line(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner,
                                    cx + math.cos(angle) * outer, cy + math.sin(angle) * outer,
                                    fill="#8D784A" if index % 2 else "#D6B56C",
                                    width=max(1, int(self.scale)), tags="sea")
        for index in range(9):
            x = (index * 53 + 31) * self.scale % self.width
            y = cy + (105 - ((elapsed * 24 + index * 29) % 170)) * self.scale
            r = (1.5 + index % 2) * self.scale
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#C7AA68", outline="", tags="sea")
        self._waves(elapsed, rows=2)

    def _draw_stars(self, elapsed, cx, cy, pulse):
        for index in range(38):
            x = (index * 83 + 27) % 400 * self.scale
            y = (0.12 + ((index * 47) % 390) / 1000) * self.height
            brightness = 110 + int(70 * (0.5 + 0.5 * math.sin(elapsed * 2 + index)))
            color = f"#{brightness:02x}{int(brightness * .88):02x}{int(brightness * .60):02x}"
            r = (0.8 + index % 3 * 0.55) * self.scale
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="", tags="sea")
        travel = (elapsed / 2.1)
        sx = (-70 + travel * 560) * self.scale
        sy = self.height * (0.15 + travel * 0.15)
        self.canvas.create_line(sx - 45 * self.scale, sy - 12 * self.scale, sx, sy,
                                fill="#D6B56C", width=max(1, int(2 * self.scale)), tags="sea")
        self.canvas.create_oval(cx-83*self.scale, cy-83*self.scale, cx+83*self.scale, cy+83*self.scale,
                                outline="#665C42", width=max(1, int(self.scale)), tags="sea")
        self._waves(elapsed)

    def _draw_ripples(self, elapsed, cx, cy, pulse):
        for index in range(6):
            radius = (85 + ((index * 27 + elapsed * 32) % 150)) * self.scale
            flatten = 0.34 + index * 0.018
            self.canvas.create_oval(cx-radius, cy-radius*flatten, cx+radius, cy+radius*flatten,
                                    outline="#6E644B" if index % 2 else "#527A70",
                                    width=max(1, int(2 * self.scale)), tags="sea")
        for index in range(5):
            angle = elapsed * 0.45 + index * math.tau / 5
            x = cx + math.cos(angle) * 112 * self.scale
            y = cy + math.sin(angle) * 112 * self.scale
            r = 2.2 * self.scale
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill="#D6B56C", outline="", tags="sea")
        self._waves(elapsed, rows=2)

    def _animate(self):
        if self.finished or not self.canvas.winfo_exists():
            return
        elapsed = time.monotonic() - self.started
        if elapsed >= 2.1:
            self.finish()
            return
        self.canvas.delete("sea")
        cx, cy = self.width / 2, self.height * 0.37
        pulse = 0.5 + 0.5 * math.sin(elapsed * 3.2)
        drawer = {"tide": self._draw_tide, "rays": self._draw_rays,
                  "stars": self._draw_stars, "ripples": self._draw_ripples}[self.variant]
        drawer(elapsed, cx, cy, pulse)
        self.canvas.create_image(cx, cy, image=self.logo, tags="sea")
        self.root.after(35, self._animate)

    def finish(self):
        if self.finished:
            return
        self.finished = True
        if self.sound_playing:
            winsound.PlaySound(None, 0)
            self.sound_playing = False
        if self.canvas.winfo_exists():
            self.canvas.destroy()
        self.on_complete()
