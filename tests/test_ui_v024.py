# -*- coding: utf-8 -*-
"""v0.0.24：刻录设置区（类型/速度/校验）、ISO、整盘复制、体检、历史校验标记。"""
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "build_deps"))

import main as main_mod  # noqa: E402

from main import APP_NAME, YaoKeApp  # noqa: E402
from optical.models import DriveInfo, OperationResult  # noqa: E402

base = Path("test_v024_samples")
if base.exists():
    shutil.rmtree(base)
base.mkdir(exist_ok=True)
(base / "甲.txt").write_text("hello", encoding="utf-8")

app = YaoKeApp()
results = {}


def make_drive(**kwargs):
    values = dict(recorder_id="test", name="Test", drive_letters=("E:",),
                  present=True, writable=True, blank=True, file_system="")
    values.update(kwargs)
    return DriveInfo(**values)


def check():
    try:
        # 1) 刻录设置控件存在
        results["settings_widgets"] = all(
            hasattr(app, name) for name in
            ("disc_type_var", "speed_var", "verify_var", "type_buttons", "speed_buttons"))

        # 2) 类型切换更新按钮高亮与提示
        app._set_disc_type("audio")
        results["type_switch"] = app.disc_type_var.get() == "audio" \
            and "音乐 CD" in app.progress_label.cget("text")

        # 3) 速度切换
        app._set_speed("safe")
        results["speed_switch"] = app.speed_var.get() == "safe"

        # 4) burn() 分发到音乐 CD
        app._set_disc_type("audio")
        app._add_sources([base / "甲.txt"], None)
        drive = make_drive()
        app.require_drive = lambda writable=False: drive
        calls = {}
        app.service = SimpleNamespace(burn_audio=lambda rid, wavs, cb: calls.update(rid=rid, wavs=list(wavs)))
        tasks = []
        def fake_run_task(op, fn, **kw):
            tasks.append(op)
            fn()
        app.run_task = fake_run_task
        original_askokcancel = main_mod.messagebox.askokcancel
        main_mod.messagebox.askokcancel = lambda *a, **k: True
        try:
            app.burn()
        finally:
            main_mod.messagebox.askokcancel = original_askokcancel
        results["audio_dispatch"] = tasks == ["刻录音乐 CD"] and len(calls.get("wavs", [])) == 1

        # 5) DVD 视频盘缺 VIDEO_TS 时不启动任务并提示
        app._set_disc_type("dvdvideo")
        tasks.clear()
        warnings = []
        original_showwarning = main_mod.messagebox.showwarning
        main_mod.messagebox.showwarning = lambda *a, **k: warnings.append(a[1])
        try:
            app.burn()
        finally:
            main_mod.messagebox.showwarning = original_showwarning
        results["dvdvideo_guard"] = tasks == [] and any("VIDEO_TS" in w for w in warnings)

        # 6) _burn_and_verify 组合逻辑
        app.verify_var.set(True)
        app._write_queue = lambda d, u: OperationResult(True, "刻录完成")
        app._verify_disc = lambda d, cb: OperationResult(True, "校验通过", verified=True)
        combined = app._burn_and_verify(drive, False)
        results["verify_combined"] = combined.verified and "校验通过" in combined.message
        app.verify_var.set(False)
        plain = app._burn_and_verify(drive, False)
        results["verify_skipped"] = not plain.verified and plain.message == "刻录完成"

        # 7) 历史记录“已校验”标记
        app.history.add("刻录光盘", True, "测试", verified=True)
        app.reload_history()
        first = app.history_list.get(0)
        results["history_badge"] = "已校验" in first
        app.history.clear()
        app.reload_history()

        # 8) 生成 ISO：空队列时提示且不启动任务
        app.burn_queue.roots.clear()
        app._reload_sources()
        tasks.clear()
        infos = []
        original_showinfo = main_mod.messagebox.showinfo
        main_mod.messagebox.showinfo = lambda *a, **k: infos.append(a[1])
        try:
            app.create_iso_dialog()
        finally:
            main_mod.messagebox.showinfo = original_showinfo
        results["iso_empty_guard"] = tasks == [] and bool(infos)
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
print("V024_BURN_SETTINGS_PASS")
