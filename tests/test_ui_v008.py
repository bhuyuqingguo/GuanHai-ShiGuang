import sys
from pathlib import Path
from types import SimpleNamespace
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from main import YaoKeApp

sample = Path("test_media_v008")
(sample / "原有目录").mkdir(parents=True, exist_ok=True)
(sample / "原有目录" / "保留.txt").write_text("保留", encoding="utf-8")
for name in ("报告.docx", "照片.jpg", "录音.mp3", "附件.zip", "工具.py", "其他.bin"):
    (sample / name).write_text(name, encoding="utf-8")

app = YaoKeApp()


def capture(name):
    app.root.update_idletasks()
    x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
    ImageGrab.grab((x, y, x + app.root.winfo_width(), y + app.root.winfo_height()), all_screens=True).save(name)


def run():
    app.show_tab("burn")
    app._add_sources([sample / "原有目录", sample / "报告.docx", sample / "照片.jpg", sample / "录音.mp3", sample / "附件.zip", sample / "工具.py", sample / "其他.bin"])
    app.create_source_folder()
    created = app.burn_queue.roots[-1]
    assert created.is_dir
    app.burn_queue.rename(created, "待交接")
    app.organize_sources()
    assert any(entry.name == "文档资料" for entry in app.burn_queue.roots)
    assert app.burn_queue.roots[0].name == "原有目录"
    documents = next(entry.uid for entry in app.burn_queue.roots if entry.name == "文档资料")
    app.source_tree.selection_set(documents)
    app.source_tree.see(documents)
    app.root.update_idletasks()
    app._on_tree_drag_position(SimpleNamespace(x=10, y=app.source_tree.bbox(documents)[1] + 5), app.source_tree)
    assert "文档资料" in app.tree_hint.cget("text")
    app._set_drop_target(app.source_tree)
    assert app.secure_page.file_tree.exists(documents)
    capture("ui_v008_burn.png")
    app.show_tab("secure")
    app.root.update()
    original = next(entry.uid for entry in app.burn_queue.roots if entry.name == "原有目录")
    pending = next(entry.uid for entry in app.burn_queue.roots if entry.name == "待交接")
    assert app.secure_page.file_tree.exists(original)
    app.secure_page.file_tree.selection_set(pending)
    app.remove_sources(app.secure_page.file_tree)
    assert not app.source_tree.exists(pending)
    capture("ui_v008_secure.png")
    assert (sample / "原有目录" / "保留.txt").exists()
    print("PASS: 两页树同步、新建重命名删除、整理、目标提示和原文件保护", flush=True)
    app.force_close()


app.root.after(3500, run)
app.run()
