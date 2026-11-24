import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
from main import YaoKeApp

sample = Path("test_mini_drop")
sample.mkdir(exist_ok=True)
(sample / "一.txt").write_text("one", encoding="utf-8")
(sample / "二.txt").write_text("two", encoding="utf-8")
app = YaoKeApp()


def check():
    app.close()
    assert app.mini_icon.window is not None
    app.mini_icon._drag_enter()
    assert app.mini_icon.window.cget("bg") == "#5EEAD4"
    event = SimpleNamespace(data="{" + str((sample / "一.txt").resolve()) + "}", action="copy")
    app.mini_icon._drop(event)
    app.mini_icon._drop(SimpleNamespace(data="{" + str((sample / "二.txt").resolve()) + "}", action="copy"))
    assert len(app.burn_queue.roots) == 2
    assert app.current_tab == "burn"
    assert app.root.state() == "withdrawn"
    assert (sample / "一.txt").exists() and (sample / "二.txt").exists()
    print("PASS: 收起状态拖入浮动图标、多次累计和原文件保护", flush=True)
    app.force_close()


app.root.after(3500, check)
app.run()
