"""v0.0.16 回归：任务卡死自愈——无进度超时判定、强制结束并复位。"""
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
import main as main_module
from main import APP_NAME, YaoKeApp

app = YaoKeApp()


def check():
    # 1) 模拟刻录任务开始后设备无响应：工作线程永远不返回、不汇报进度。
    def hung_worker():
        import threading as _t
        _t.Event().wait(600)

    app.run_task("刻录光盘", hung_worker, show_message=False)
    assert app.busy
    assert not app._task_stalled

    # 2) 进度正常时不误报：刚有进度反馈时健康检查应保持沉默。
    app._last_progress_event = time.monotonic()
    app._check_task_health()
    assert not app._task_stalled

    # 3) 超过 5 分钟无进度：判定疑似卡死，取消按钮变为“强制结束任务”。
    app._last_progress_event = time.monotonic() - 400
    app._check_task_health()
    assert app._task_stalled
    assert "强制结束任务" in app.cancel_button.cget("text")
    assert "疑似卡死" in app.progress_percent.cget("text")
    assert "5 分钟" in app.progress_label.cget("text")

    # 4) 卡死状态下点取消 = 触发强制结束（确认弹窗自动同意）。
    answers = []
    original = main_module.messagebox.askyesno
    main_module.messagebox.askyesno = lambda *a, **k: answers.append((a, k)) or True
    app.cancel()
    main_module.messagebox.askyesno = original
    assert answers and APP_NAME in answers[0][0]
    assert not app.busy, "强制结束后应复位 busy"
    assert not app._task_stalled
    assert "取消" in app.cancel_button.cget("text") and "强制结束" not in app.cancel_button.cget("text")
    assert "已强制结束" in app.progress_percent.cget("text")
    assert "软件已复位" in app.progress_label.cget("text")

    # 5) 复位后可启动新任务：不再提示“已有操作正在进行”。
    app.run_task("快速擦除", lambda: None, show_message=False)
    assert app.busy
    time.sleep(0.3)
    # 任务立即完成事件
    done_seen = []

    def pump():
        try:
            while True:
                kind, payload = app.events.get_nowait()
                if kind == "done":
                    done_seen.append(True)
                    app._task_done(*payload)
        except Exception:
            pass

    pump()
    assert done_seen, "应立即收到完成事件"
    assert not app.busy
    assert not app._task_stalled

    print("PASS: 任务卡死自愈——超时判定、强制结束、状态复位、可继续新任务", flush=True)
    app.force_close()


app.root.after(2500, check)
app.run()
