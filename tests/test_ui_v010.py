import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "optical_desk"))
import main
from main import YaoKeApp

app = YaoKeApp()


def check():
    real_rects = main.monitor_rects
    main.monitor_rects = lambda: [(0, 0, app.root.winfo_screenwidth(), app.root.winfo_screenheight())]
    app.root.geometry("+5000+300")
    app.root.update()
    app._check_display_bounds()
    app.root.update()
    assert 0 <= app.root.winfo_x() < app.root.winfo_screenwidth()
    app.mini_icon.show()
    app.mini_icon.window.geometry("+5000+300")
    app.mini_icon.window.update()
    app._check_display_bounds()
    app.mini_icon.window.update()
    assert 0 <= app.mini_icon.window.winfo_x() < app.root.winfo_screenwidth()
    main.monitor_rects = real_rects
    print("PASS: 主面板和浮动图标均可从失效副屏坐标回到主屏", flush=True)
    app.force_close()


app.root.after(3500, check)
app.run()
