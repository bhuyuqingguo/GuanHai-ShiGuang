# -*- coding: utf-8 -*-
"""v0.0.21：树形图选中保持、Ctrl 多选、折叠记忆的界面测试。"""
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "build_deps"))

from main import YaoKeApp  # noqa: E402

base = Path("test_v021_samples")
if base.exists():
    shutil.rmtree(base)
base.mkdir(exist_ok=True)
for name in ("甲.txt", "乙.txt", "丙.txt"):
    (base / name).write_text(name, encoding="utf-8")

app = YaoKeApp()
results = {}


def fake_event(tree, state=0, x=0, y=0):
    return SimpleNamespace(state=state, x=x, y=y, widget=tree)


def check():
    tree = app.source_tree
    try:
        app._add_sources([base / "甲.txt", base / "乙.txt"], None)
        app.create_source_folder()
        folder = next(e for e in app.burn_queue.roots if e.is_dir and e.source is None)
        file_a = next(e for e in app.burn_queue.roots if e.name == "甲.txt")
        file_b = next(e for e in app.burn_queue.roots if e.name == "乙.txt")

        # 1) 纯单击选中后松开：不重建树，选中不丢
        tree.identify_row = lambda _y: file_a.uid
        app._tree_drag_start(fake_event(tree))
        app._tree_drag_drop(fake_event(tree))
        results["click_keeps_selection"] = set(tree.selection()) == {file_a.uid}

        # 2) Ctrl+单击：加选第二个文件
        tree.identify_row = lambda _y: file_b.uid
        app._tree_drag_start(fake_event(tree, state=0x0004))
        app._tree_drag_drop(fake_event(tree))
        results["ctrl_click_adds"] = set(tree.selection()) == {file_a.uid, file_b.uid}

        # 3) Ctrl+单击已选中的文件：取消选中
        tree.identify_row = lambda _y: file_a.uid
        app._tree_drag_start(fake_event(tree, state=0x0004))
        app._tree_drag_drop(fake_event(tree))
        results["ctrl_click_removes"] = set(tree.selection()) == {file_b.uid}

        # 4) 真实拖拽：超过阈值后松手，文件移动进文件夹且保持选中
        tree.identify_row = lambda _y: file_b.uid
        app._tree_drag_start(fake_event(tree))
        tree.identify_row = lambda _y: folder.uid
        app._tree_drag_over(fake_event(tree, x=30, y=40))
        app._tree_drag_drop(fake_event(tree))
        results["drag_moves_into_folder"] = file_b.parent is folder
        results["drag_keeps_selection"] = set(tree.selection()) == {file_b.uid}

        # 5) 折叠记忆：收起文件夹 → 刷新后仍收起；展开 → 刷新后仍展开
        tree.focus(folder.uid)
        app._on_tree_collapsed(fake_event(tree))
        app._reload_sources()
        results["collapse_persists"] = not tree.item(folder.uid, "open")
        tree.focus(folder.uid)
        app._on_tree_expanded(fake_event(tree))
        app._reload_sources()
        results["expand_persists"] = bool(tree.item(folder.uid, "open"))
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
print("V021_TREE_INTERACTION_PASS")
