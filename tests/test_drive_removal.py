"""v0.0.15 回归：光驱拔出检测提示、检测卡死看门狗、取消操作不阻塞界面。"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from main import YaoKeApp
from optical.models import DriveInfo

app = YaoKeApp()


def check():
    drive = DriveInfo("REC-1", "测试光驱", ("E",), present=True, writable=True)

    # 1) 首次检测到光驱：不提示拔出。
    app._apply_drives([drive])
    assert not app._drive_removed_notice
    assert app.selected_drive and app.selected_drive.recorder_id == "REC-1"
    assert app._had_drives

    # 2) 光驱被拔出（列表变空）：提示一次，软件保持运行状态。
    toasts = []
    original = app._show_notice_toast
    app._show_notice_toast = lambda msg: toasts.append(msg)
    app._apply_drives([])
    app._show_notice_toast = original
    assert len(toasts) == 1, toasts
    assert "光驱已断开连接" in toasts[0] and "F5" in toasts[0] and "Ctrl+Q" in toasts[0]
    assert app._drive_removed_notice
    assert app.selected_drive is None
    assert app.media_label.cget("text") == "未检测到光驱"

    # 空列表再次刷新：不重复提示。
    app._apply_drives([])
    assert len(toasts) == 1

    # 3) 光驱重新插入：恢复识别并重置提示标记。
    app._apply_drives([drive])
    assert not app._drive_removed_notice
    assert app.selected_drive and app.selected_drive.recorder_id == "REC-1"

    # 4) 检测卡死看门狗：refreshing 超时后自动恢复并可再次检测。
    app.refreshing = True
    app._refresh_started = time.monotonic() - 61
    app._check_display_bounds()
    assert not app.refreshing, "看门狗应复位卡死的检测状态"
    assert "超时" in app.progress_label.cget("text")

    # 5) 取消不阻塞界面：service.cancel 挂起时 UI 线程立即返回。
    app.busy = True
    blocker = threading.Event()

    def stuck_cancel():
        blocker.wait(30)

    original_cancel = app.service.cancel
    app.service.cancel = stuck_cancel
    started = time.monotonic()
    app.cancel()
    elapsed = time.monotonic() - started
    app.service.cancel = original_cancel
    app.busy = False
    blocker.set()
    assert elapsed < 1.0, f"取消操作阻塞了界面 {elapsed:.2f} 秒"
    assert "正在请求取消" in app.progress_label.cget("text")

    print("PASS: 光驱拔出提示、检测看门狗、取消不阻塞界面", flush=True)
    app.force_close()


app.root.after(2500, check)
app.run()
