# -*- coding: utf-8 -*-
"""v0.0.20：可擦写盘追加刻录提示的界面测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "build_deps"))

from optical.models import DriveInfo
from main import YaoKeApp  # noqa: E402


def make_drive(**kwargs):
    base = dict(recorder_id="test", name="Test Drive", drive_letters=("E:",),
                present=True, writable=True, erasable=True,
                file_system="UDF", capacity_bytes=700 * 1024 * 1024,
                free_bytes=400 * 1024 * 1024, blank=False)
    base.update(kwargs)
    return DriveInfo(**base)


def main():
    app = YaoKeApp()
    results = {}

    def check():
        try:
            # 1. UDF 可写盘（未封盘、有剩余空间）→ 显示追加提示
            app.selected_drive = make_drive()
            app._update_drive_card()
            text = app.append_hint.cget("text")
            results["append_hint_shown"] = "可直接追加" in text and "剩余" in text

            # 2. 空白盘 → 不显示
            app.selected_drive = make_drive(blank=True, file_system="")
            app._update_drive_card()
            results["blank_hidden"] = app.append_hint.cget("text") == ""

            # 3. UDF 盘但已满 → 不显示
            app.selected_drive = make_drive(free_bytes=0)
            app._update_drive_card()
            results["full_hidden"] = app.append_hint.cget("text") == ""

            # 4. 标准封盘（只读、CDFS）→ 不显示
            app.selected_drive = make_drive(writable=False, file_system="CDFS")
            app._update_drive_card()
            results["closed_hidden"] = app.append_hint.cget("text") == ""

            # 5. 无盘 → 清空
            app.selected_drive = None
            app._update_drive_card()
            results["nodrive_hidden"] = app.append_hint.cget("text") == ""
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
    print("V020_APPEND_HINT_PASS")


if __name__ == "__main__":
    main()
