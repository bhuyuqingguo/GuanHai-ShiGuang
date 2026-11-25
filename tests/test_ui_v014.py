"""v0.0.14 回归：浮动图标可拖拽换位、位置持久化、屏幕变化自适应。"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
import mini_icon
from main import YaoKeApp
from monitor_utils import monitor_rects, window_has_visible_monitor

app = YaoKeApp()

SETTINGS = mini_icon.SETTINGS
backup = None
if SETTINGS.exists():
    backup = SETTINGS.read_text(encoding="utf-8")


def cleanup_settings():
    if backup is None:
        try:
            SETTINGS.unlink()
        except OSError:
            pass
    else:
        SETTINGS.write_text(backup, encoding="utf-8")


def check():
    mini = app.mini_icon
    mini.show()
    window = mini.window
    assert window is not None and window.winfo_exists()
    window.update_idletasks()

    # 1) 初始位置：在当前屏幕右侧边缘。
    rects = monitor_rects()
    assert rects, "应能枚举显示器"
    assert window_has_visible_monitor(rects, window.winfo_x(), window.winfo_y(),
                                      window.winfo_width(), window.winfo_height()), \
        (window.winfo_x(), window.winfo_y())
    right_edges = [r[2] for r in rects]
    gap = min(abs(e - (window.winfo_x() + window.winfo_width())) for e in right_edges)
    assert gap <= int(45 * app.ui_scale), (window.winfo_x(), window.winfo_width(), right_edges)

    # 2) 拖拽：按住移动超过阈值即拖动，松开后位置被记住。
    sx, sy = window.winfo_x(), window.winfo_y()
    start = SimpleNamespace(x_root=sx + 30, y_root=sy + 30)
    mini._on_press(start)
    # 小抖动不触发拖拽
    mini._on_motion(SimpleNamespace(x_root=sx + 33, y_root=sy + 32))
    assert not mini._dragging
    for step in range(1, 6):
        mini._on_motion(SimpleNamespace(x_root=sx + 30 - step * 15, y_root=sy + 30 + step * 10))
    assert mini._dragging
    window.update_idletasks()
    mini._on_release(SimpleNamespace())
    window.update_idletasks()
    ex, ey = window.winfo_x(), window.winfo_y()
    assert (ex, ey) != (sx, sy), (sx, sy, ex, ey)
    saved = mini._load_position()
    assert saved == (ex, ey), (saved, ex, ey)

    # 3) 单击（未拖动）触发恢复。
    restored = []
    original_restore = app.restore
    app.restore = lambda: restored.append(True)
    mini._on_press(SimpleNamespace(x_root=ex + 10, y_root=ey + 10))
    mini._on_release(SimpleNamespace())
    app.restore = original_restore
    assert restored, "未拖动的单击应恢复主面板"

    # 4) 屏幕变化：把图标挪到屏幕外，recover 后回到当前屏幕右侧边缘。
    window.geometry(f"-{window.winfo_screenwidth() + 4000}+100")
    window.update_idletasks()
    mini.recover(monitor_rects())
    window.update_idletasks()
    assert window_has_visible_monitor(monitor_rects(), window.winfo_x(), window.winfo_y(),
                                      window.winfo_width(), window.winfo_height()), \
        (window.winfo_x(), window.winfo_y())
    right_edges = [r[2] for r in monitor_rects()]
    gap = min(abs(e - (window.winfo_x() + window.winfo_width())) for e in right_edges)
    assert gap <= int(45 * app.ui_scale), (window.winfo_x(), window.winfo_width(), right_edges)

    # 5) 恢复后位置同样被记住，重启仍生效。
    saved = mini._load_position()
    assert saved == (window.winfo_x(), window.winfo_y()), saved
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert "mini_icon_pos" in data

    cleanup_settings()
    print("PASS: 浮动图标拖拽换位、位置持久化、屏幕变化自适应", flush=True)
    app.force_close()


app.root.after(2500, check)
app.run()
