import sys
import time
from pathlib import Path
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from main import YaoKeApp
from optical.models import FileEntry

sample = Path("test_export_media")
(sample / "会议资料").mkdir(parents=True, exist_ok=True)
(sample / "会议资料" / "纪要.docx").write_text("纪要", encoding="utf-8")
(sample / "照片.jpg").write_text("照片", encoding="utf-8")
(sample / "说明.txt").write_text("说明", encoding="utf-8")

app = YaoKeApp()


def check():
    entries = [FileEntry(p.name, p, p.is_dir(), p.stat().st_size, p.stat().st_mtime) for p in sample.iterdir()]
    app.service.list_files = lambda recorder_id, relative="": [e for e in entries if (e.path.parent == (sample / relative if relative else sample))]
    app.open_disc_browser("test-drive")
    app.root.after(700, verify)


def verify():
    browser = app.disc_browser
    assert browser.winfo_manager() == "pack"
    assert len(browser.tree.get_children()) == 3
    browser.tree.selection_set("1")
    output = Path("test_export_output")
    browser.destination_var.set(str(output.resolve()))
    browser.rule_var.set("按资料类型")
    browser.export_selected()
    deadline = time.time() + 5
    while not (output / "图片照片" / "照片.jpg").exists() and time.time() < deadline:
        app.root.update()
        time.sleep(0.05)
    assert (output / "图片照片" / "照片.jpg").is_file()
    assert (sample / "照片.jpg").is_file()
    app.root.update_idletasks()
    x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
    ImageGrab.grab((x, y, x + app.root.winfo_width(), y + app.root.winfo_height()), all_screens=True).save("ui_v009_disc.png")
    print("PASS: 内嵌浏览、分类导出、原盘文件保护和导出目录设置", flush=True)
    app.force_close()


app.root.after(3500, check)
app.run()
