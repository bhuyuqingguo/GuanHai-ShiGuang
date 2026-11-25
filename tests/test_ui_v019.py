"""v0.0.19 回归：主界面任意位置拖放、新建文件夹自动选中与重命名、多选整体拖拽。"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from main import YaoKeApp

base = Path("test_v019_samples")
if base.exists():
    import shutil

    shutil.rmtree(base)
base.mkdir(exist_ok=True)
for name in ("甲.txt", "乙.txt", "丙.txt"):
    (base / name).write_text(name, encoding="utf-8")

app = YaoKeApp()


def check():
    tree = app.source_tree

    # 1) 整个主界面任意位置可拖放：直接调用根窗口 Drop 处理。
    event = SimpleNamespace(data="{" + str((base / "甲.txt").resolve()) + "}", action="copy")
    app._on_root_drop(event)
    assert any(e.name == "甲.txt" for e in app.burn_queue.roots), [e.name for e in app.burn_queue.roots]
    assert app.current_tab == "burn", app.current_tab

    # 2) 新建文件夹后自动选中，且可以立即重命名（虚拟文件夹与真实文件都支持）。
    app.create_source_folder()
    folder = next(e for e in app.burn_queue.roots if e.is_dir and e.source is None)
    selection = tree.selection()
    assert selection and selection[0] == folder.uid, (selection, folder.uid)
    original_ask = app._ask_entry_name
    app._ask_entry_name = lambda _title, _initial: "资料汇总"
    app.rename_source_entry()
    app._ask_entry_name = original_ask
    assert folder.name == "资料汇总", folder.name

    # 3) 文件同样可以重命名。
    file_entry = next(e for e in app.burn_queue.roots if not e.is_dir)
    tree.selection_set(file_entry.uid)
    original_ask = app._ask_entry_name
    app._ask_entry_name = lambda _title, _initial: "改名后.txt"
    app.rename_source_entry()
    app._ask_entry_name = original_ask
    assert file_entry.name == "改名后.txt", file_entry.name
    assert (base / "甲.txt").exists(), "重命名绝不改动电脑上的原文件"

    # 4) Ctrl 多选 + 整体拖拽到文件夹。
    added = app.burn_queue.add_paths([base / "乙.txt", base / "丙.txt"])
    assert added == 2
    app._reload_sources()
    moving = [e for e in app.burn_queue.roots if not e.is_dir]
    assert len(moving) == 3, [e.name for e in moving]
    tree.selection_set(tuple(e.uid for e in moving))
    assert len(tree.selection()) == 3, "Ctrl 多选应保留多个选中项"
    app.show_tab("burn")
    app.root.update_idletasks()
    for e in moving:
        tree.see(e.uid)
    tree.update_idletasks()
    target = folder

    class Ev:
        def __init__(self, x=0, y=0):
            self.x = x
            self.y = y
            self.x_root = tree.winfo_rootx() + x
            self.y_root = tree.winfo_rooty() + y

    press_row = tree.bbox(moving[0].uid)
    target_row = tree.bbox(target.uid)
    app._tree_drag_start(Ev(press_row[0], press_row[1] + press_row[3] // 2))
    assert set(app._tree_drag_items) == {e.uid for e in moving}, app._tree_drag_items
    app._tree_drag_over(Ev(target_row[0], target_row[1] + target_row[3] // 2))
    assert app._tree_drop_target == target.uid
    app._tree_drag_drop(Ev(target_row[0], target_row[1] + target_row[3] // 2))
    assert all(e.parent is target for e in moving), [e.parent.name for e in moving]
    assert app.burn_queue.file_count() == 3
    assert len(app.burn_queue.roots) == 1 and app.burn_queue.roots[0] is target

    # 5) 拖文件经过浮动图标时主界面自动展开。
    app.close()
    assert app.root.state() == "withdrawn"
    mini = app.mini_icon
    mini.show()
    mini._drag_enter()
    app.root.update()
    assert app.root.state() != "withdrawn", "拖拽经过浮动图标应展开主界面"

    print("PASS: 主界面任意位置拖放、新建即选中可重命名、多选整体拖拽、拖入自动展开", flush=True)
    app.force_close()


app.root.after(2500, check)
app.run()
