"""v0.0.17 回归：历史强制结束红色标记；浮动图标右键菜单不再直接退出。"""
import sys
from pathlib import Path

import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from main import YaoKeApp

app = YaoKeApp()


def check():
    # 1) 历史记录：强制结束带标记并显示为红色，普通失败不受影响（新记录在前）。
    app.history.clear()
    app.history.add("读取光盘", True, "完成")
    app.history.add("刻录光盘", False, "写入失败")
    app.history.add("快速擦除", False, "设备无响应，任务被强制结束", forced=True)
    app.reload_history()
    forced_record = next(r for r in app.history_records if r.get("forced"))
    assert forced_record["status"] == "强制结束"
    assert any(r["status"] == "未完成" and not r.get("forced") for r in app.history_records)
    assert any(r["status"] == "成功" for r in app.history_records)
    forced_index = next(i for i, r in enumerate(app.history_records) if r.get("forced"))
    normal_index = next(i for i, r in enumerate(app.history_records) if r["status"] == "未完成")
    fg_forced = app.history_list.itemconfig(forced_index, "foreground")[-1]
    fg_normal = app.history_list.itemconfig(normal_index, "foreground")[-1]
    assert fg_forced == "#D88A80", fg_forced  # 当前古典·黛金皮肤的 DANGER 色
    assert fg_normal != fg_forced
    app.history.clear()
    app.reload_history()

    # 2) 浮动图标右键：弹出菜单（含“彻底退出”选项）而不是直接退出。
    mini = app.mini_icon
    mini.show()
    window = mini.window
    assert window is not None and window.winfo_exists()

    class Event:
        x_root = window.winfo_x() + 10
        y_root = window.winfo_y() + 10

    captured = []
    real_popup = tk.Menu.tk_popup

    def fake_popup(self, x, y):
        labels = []
        for i in range(self.index("end") + 1):
            config = self.entryconfigure(i)
            label = config.get("label")
            if label and label[-1]:
                labels.append(label[-1])
        captured.append(labels)
        return real_popup(self, x, y)

    tk.Menu.tk_popup = fake_popup
    try:
        mini._show_menu(Event())
    finally:
        tk.Menu.tk_popup = real_popup
    labels = [label for label in captured[0] if label]
    assert "打开观海·拾光" in labels, labels
    assert "彻底退出观海·拾光" in labels, labels
    assert window.winfo_exists(), "右键不应直接退出"

    # 3) 菜单命令确实未执行退出：窗口仍在，主窗口未关闭。
    assert app.root.winfo_exists()
    window.destroy()
    mini.window = None

    print("PASS: 强制结束红色标记、右键菜单不直接退出", flush=True)
    app.force_close()


app.root.after(2500, check)
app.run()
