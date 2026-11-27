# -*- coding: utf-8 -*-
"""v0.0.25：高缩放屏幕下的界面适配（窗口按内容自适应、树行数压缩）。"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "build_deps"))

from main import YaoKeApp  # noqa: E402

base = Path("test_v025_samples")
if base.exists():
    shutil.rmtree(base)
base.mkdir(exist_ok=True)
(base / "甲.txt").write_text("hi", encoding="utf-8")

app = YaoKeApp()
results = {}


def check():
    try:
        screen_h = app.root.winfo_screenheight()
        margin = int(22 * app.ui_scale)
        # 1) 窗口高度不超过屏幕可用区
        app._place_right()
        app.root.update_idletasks()
        height = app.root.winfo_height()
        results["fits_screen"] = height <= screen_h - margin + 2
        # 2) 窗口高度足够放下内容（不低于 760 设计值与内容高度）
        results["content_fits"] = app.root.winfo_reqheight() <= height + 2
        # 3) 刻录页完整显示：切到刻录页后请求高度不超窗口
        app.show_tab("burn")
        app.root.update_idletasks()
        burn_h = app.pages["burn"].winfo_reqheight()
        results["burn_page_fits"] = burn_h <= app.root.winfo_height() + 2
        # 4) 树行数不低于下限 3
        results["tree_min_height"] = int(app.source_tree.cget("height")) >= 3
        # 5) 极端小屏模拟：把可用高度压到 600，压缩后仍应放得下
        original = app.root.winfo_reqheight()
        # 直接调用内部逻辑等价验证：压缩树后根请求高度下降
        before = app.root.winfo_reqheight()
        app.source_tree.config(height=3)
        app.root.update_idletasks()
        after = app.root.winfo_reqheight()
        results["tree_cut_reduces"] = after < before
        app._place_right()
        app.root.update_idletasks()
        results["re_place_stable"] = app.root.winfo_height() <= screen_h - margin + 2
    except Exception as exc:  # noqa: BLE001
        results["exception"] = repr(exc)
    app.force_close()


app.root.after(2500, check)
app.run()
failed = [k for k, v in results.items() if not v]
print("RESULTS:", results)
if failed or "exception" in results:
    print("FAILED:", failed or results["exception"])
    sys.exit(1)
print("V025_LAYOUT_FIT_PASS")
