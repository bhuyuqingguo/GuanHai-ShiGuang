# -*- coding: utf-8 -*-
"""v0.0.27 UI 测试：醒目滚动条 + 开始刻录按钮钉在底部固定区。"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.abspath("optical_desk"))
import main as main_mod  # noqa: E402
from main import YaoKeApp, _ScrollBody, ACCENT_DARK, PANEL_2  # noqa: E402

results = {}


def check():
    try:
        burn_scroll = app._scrolls[id(app.pages["burn"])]
        results["scrollbar_is_classic"] = isinstance(burn_scroll.scrollbar, tk.Scrollbar)
        results["scrollbar_prominent"] = (
            burn_scroll.scrollbar.cget("bg") == main_mod.ACCENT and
            burn_scroll.scrollbar.cget("troughcolor") == main_mod.PANEL_2
        )
        results["footer_detached"] = app.burn_button.master is not burn_scroll.inner
        results["summary_detached"] = app.source_summary.master is app.burn_button.master

        # 压矮窗口后按钮仍完整可见
        app.root.update()
        app.root.update_idletasks()
        ry = app.root.winfo_rooty() + app.root.winfo_height()
        by = app.burn_button.winfo_rooty() + app.burn_button.winfo_height()
        results["burn_button_visible_short"] = by <= ry + 2

        # 滚动后按钮位置不动
        before = app.burn_button.winfo_rooty()
        burn_scroll.canvas.yview_moveto(0.5)
        app.root.update_idletasks()
        results["burn_button_stable_on_scroll"] = abs(app.burn_button.winfo_rooty() - before) <= 2
    except Exception as e:  # noqa: BLE001
        results["error"] = repr(e)
    app.force_close()


app = YaoKeApp()
app.root.after(2500, check)
app.run()

failed = [k for k, v in results.items() if v is not True]
print("RESULTS", results)
sys.exit(1 if failed else 0)
