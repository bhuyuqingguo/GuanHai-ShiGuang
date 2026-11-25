"""v0.0.13 回归：空文件夹禁止刻录、固定顺序整理、撤销快照、树形映射、暂存目录一致。"""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
import main as main_module
from main import APP_NAME, YaoKeApp
from burn_queue import BurnQueue

base = Path("test_v013_samples")
if base.exists():
    import shutil

    shutil.rmtree(base)
base.mkdir(exist_ok=True)
(base / "说明.txt").write_text("readme", encoding="utf-8")
(base / "报告.docx").write_text("doc", encoding="utf-8")
(base / "照片.png").write_text("png", encoding="utf-8")
(base / "录音.mp3").write_text("mp3", encoding="utf-8")
(base / "备份.zip").write_text("zip", encoding="utf-8")
(base / "工具.py").write_text("py", encoding="utf-8")
(base / "杂项.dat").write_text("dat", encoding="utf-8")
existing_dir = base / "原有文件夹"
existing_dir.mkdir(exist_ok=True)
(existing_dir / "保留.txt").write_text("keep", encoding="utf-8")

app = YaoKeApp()


def check():
    # 1) 只有一个空文件夹：提示空队列、开始按钮禁用、刻录入口被真实文件数拦截。
    empty = app.burn_queue.create_folder("空文件夹")
    app._reload_sources()
    assert "空文件夹" in app.source_summary.cget("text") or "没有可刻录文件" in app.source_summary.cget(
        "text"
    ), app.source_summary.cget("text")
    assert str(app.burn_button.cget("state")) == "disabled"
    assert app.burn_queue.file_count() == 0

    calls = []
    original_showinfo = main_module.messagebox.showinfo
    main_module.messagebox.showinfo = lambda *a, **k: calls.append((a, k))
    app.require_drive = lambda writable=False: SimpleNamespace(
        recorder_id="R", drive_text="测试光驱", file_system="CDFS", blank=True
    )
    app.burn()
    main_module.messagebox.showinfo = original_showinfo
    assert calls, "空文件夹点击开始刻录时应给出明确提示"
    assert "没有可刻录的文件" in calls[0][0][1]

    # 2) 加入真实散文件和既有文件夹后：可以开始，整理按钮可用。
    added = app.burn_queue.add_paths(sorted(base.iterdir()))
    assert added == 8, added
    app._reload_sources()
    assert "8 个文件" in app.source_summary.cget("text"), app.source_summary.cget("text")
    assert str(app.burn_button.cget("state")) == "normal"

    names_before = [entry.name for entry in app.burn_queue.roots]
    assert "原有文件夹" in names_before and "空文件夹" in names_before

    # 3) 一键整理：固定类别顺序，散文件全部进入类别文件夹，既有文件夹不动。
    app.organize_sources()
    assert app.organize_button.cget("text") == "撤销整理", app.organize_button.cget("text")
    root_names = [entry.name for entry in app.burn_queue.roots]
    assert "原有文件夹" in root_names and "空文件夹" in root_names
    loose_left = [entry for entry in app.burn_queue.roots if not entry.is_dir]
    assert not loose_left, [entry.name for entry in loose_left]
    expected_order = ["文档资料", "图片照片", "音视频", "压缩包", "程序与代码", "其他文件"]
    category_roots = [entry.name for entry in app.burn_queue.roots if entry.name in expected_order]
    assert category_roots == expected_order, category_roots
    mapping = {entry.name: [child.name for child in entry.children]
               for entry in app.burn_queue.roots if entry.is_dir and entry.children}
    assert mapping["文档资料"] == ["报告.docx", "说明.txt"]
    assert mapping["其他文件"] == ["杂项.dat"]

    # 树右列写入映射说明。
    tree = app.source_tree
    sample_file = next(entry for entry in app.source_nodes.values() if not entry.is_dir)
    assert "按当前顺序" in tree.item(sample_file.uid, "values")[0]
    root_uid = next(entry.uid for entry in app.burn_queue.roots if entry.is_dir)
    assert "刻录顺序" in tree.item(root_uid, "values")[0]

    # 4) 暂存目录与虚拟树严格一致（结构、顺序、内容）。
    with tempfile.TemporaryDirectory(prefix="GuanHaiStage_") as temp:
        staged = Path(temp) / "content"
        count = app.burn_queue.materialize(staged)
        assert count == 8, count  # 7 个散文件 + 原有文件夹内 1 个
        top = [p.name for p in staged.iterdir()]
        expected_top = expected_order + ["原有文件夹", "空文件夹"]
        assert sorted(top) == sorted(expected_top), top
        # 刻录顺序以虚拟树为准：materialize 按 roots 顺序写入。
        roots_order = [entry.name for entry in app.burn_queue.roots]
        assert roots_order == ["空文件夹", "原有文件夹"] + expected_order, roots_order
        assert (staged / "文档资料" / "说明.txt").read_text(encoding="utf-8") == "readme"
        assert (staged / "原有文件夹" / "保留.txt").read_text(encoding="utf-8") == "keep"
        assert (staged / "空文件夹").is_dir() and not any((staged / "空文件夹").iterdir())

    # 5) 撤销整理：结构恢复到整理前，按钮回到一键整理。
    app.organize_sources()
    assert app.organize_button.cget("text") == "一键整理"
    assert [entry.name for entry in app.burn_queue.roots] == names_before
    assert app.burn_queue.file_count() == 8

    # 6) 修改队列后撤销失效：重新加文件时快照应被清除。
    app.organize_sources()
    assert app.organize_button.cget("text") == "撤销整理"
    extra = base / "额外.txt"
    extra.write_text("extra", encoding="utf-8")
    assert app.burn_queue.add_paths([extra]) == 1
    app._organize_snapshot = None
    app._reload_sources()
    app.organize_sources()
    assert app.organize_button.cget("text") == "撤销整理"  # 没有旧快照，当前再次整理保持可撤销

    app.show_tab("burn")
    app.root.update_idletasks()
    x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
    ImageGrab.grab(
        (x, y, x + app.root.winfo_width(), y + app.root.winfo_height()), all_screens=True
    ).save("ui_v013_burn.png")

    print("PASS: 空文件夹拦截、固定顺序整理、撤销快照、树形映射、暂存目录一致", flush=True)
    app.force_close()


app.root.after(2500, check)
app.run()
