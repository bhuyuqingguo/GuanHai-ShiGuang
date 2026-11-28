# -*- coding: utf-8 -*-
"""v0.0.26：刻录页/交接页滚动容器，保证高缩放小屏幕内容完整可达。"""
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "build_deps"))

from main import YaoKeApp  # noqa: E402

base = Path("test_v026_samples")
if base.exists():
    shutil.rmtree(base)
base.mkdir(exist_ok=True)
(base / "甲.txt").write_text("hi", encoding="utf-8")

app = YaoKeApp()
results = {}


def check():
    try:
        burn_scroll = app._scrolls.get(id(app.pages["burn"]))
        secure_scroll = app._scrolls.get(id(app.pages["secure"]))
        # 1) 两个页面都已包装为滚动容器
        results["scrolls_exist"] = burn_scroll is not None and secure_scroll is not None
        # 2) 内容装进滚动内框（拖放区/文件树归属正确）
        results["burn_content_wrapped"] = app.drop_zone.master is burn_scroll.inner \
            and app.source_tree.master.master is not app.pages["burn"]
        # 3) 窗口足够高（接近屏幕高）时滚动条隐藏
        app.show_tab("burn")
        tall = app.root.winfo_screenheight() - int(44 * app.ui_scale)
        app.root.geometry(f"{int(420*app.ui_scale)}x{tall}+100+100")
        app.root.update_idletasks()
        burn_scroll._update_bar()
        results["bar_hidden_when_tall"] = not burn_scroll.scrollbar_visible
        # 4) 窗口压矮时滚动条自动出现
        app.root.geometry(f"{int(420*app.ui_scale)}x500+100+100")
        app.root.update()
        app.root.update_idletasks()
        burn_scroll._update_bar()
        results["bar_shown_when_short"] = burn_scroll.scrollbar_visible
        # 5) 滚轮可以滚动内容
        before = burn_scroll.canvas.yview()[0]
        burn_scroll._on_wheel(SimpleNamespace(delta=-120))
        after = burn_scroll.canvas.yview()[0]
        results["wheel_scrolls"] = after > before
        # 6) 滚动条隐藏时滚轮不动作（也不会报错）
        burn_scroll.scrollbar_visible = False
        burn_scroll._on_wheel(SimpleNamespace(delta=-120))
        results["wheel_inert_when_hidden"] = burn_scroll.canvas.yview()[0] == after
        # 7) 内容总高超过窗口：即便超了也能通过滚动看全（scrollregion 覆盖内容）
        region = burn_scroll.canvas.bbox("all")
        results["scrollregion_covers_content"] = region is not None and region[3] > 500
        app._place_right()
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
print("V026_SCROLL_BODY_PASS")
