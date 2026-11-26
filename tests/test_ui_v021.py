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
        tree.selection_set(file_a.uid)
        tree.identify_row = lambda _y: file_a.uid
        app._tree_drag_start(fake_event(tree))
        results["click_captures_row"] = app._tree_drag_items == (file_a.uid,)
        app._tree_drag_drop(fake_event(tree))
        results["click_keeps_selection"] = set(tree.selection()) == {file_a.uid}

        # 2) 点在未选中的项目上：记录为拖拽候选，松开不动则不重建、不动选中
        tree.identify_row = lambda _y: file_b.uid
        app._tree_drag_start(fake_event(tree))
        results["unselected_press_captured"] = app._tree_drag_items == (file_b.uid,)
        app._tree_drag_drop(fake_event(tree))
        results["click_no_rebuild"] = set(tree.selection()) == {file_a.uid}

        # 3) 点在已选中的项目上：整组作为拖拽候选
        tree.selection_set((file_a.uid, file_b.uid))
        tree.identify_row = lambda _y: file_a.uid
        app._tree_drag_start(fake_event(tree))
        results["group_drag_captured"] = set(app._tree_drag_items) == {file_a.uid, file_b.uid}

        # 4) 真实拖拽：超过阈值后松手，文件移动进文件夹且保持选中
        tree.selection_set((file_b.uid,))
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

        # 6) 拖拽处理不拦截系统行为：不返回 "break"，折叠箭头/多选交给系统默认处理
        tree.identify_row = lambda _y: folder.uid
        before = set(tree.selection())
        outcome = app._tree_drag_start(fake_event(tree))
        results["no_break_blocking"] = outcome is None
        app._tree_drag_drop(fake_event(tree))
        results["indicator_keeps_selection"] = set(tree.selection()) == before

        # 7) 双击文件夹：收起/展开并写入折叠记忆
        tree.item(folder.uid, open=True)
        app._tree_collapsed.discard(folder.uid)
        tree.identify_row = lambda _y: folder.uid
        app._toggle_tree_folder(fake_event(tree))
        results["dblclick_collapses"] = not tree.item(folder.uid, "open") \
            and folder.uid in app._tree_collapsed
        app._toggle_tree_folder(fake_event(tree))
        results["dblclick_expands"] = bool(tree.item(folder.uid, "open")) \
            and folder.uid not in app._tree_collapsed
        # 双击普通文件：不拦截
        tree.identify_row = lambda _y: file_a.uid
        results["dblclick_file_inert"] = app._toggle_tree_folder(fake_event(tree)) is None
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
