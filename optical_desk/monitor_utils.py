from __future__ import annotations

import ctypes
from ctypes import wintypes


def monitor_rects() -> list[tuple[int, int, int, int]]:
    """返回当前所有显示器的真实坐标，支持主屏左侧或上方的副屏。"""
    if not hasattr(ctypes, "windll") or not hasattr(ctypes.windll, "user32"):
        return []
    rects = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                       ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def collect(_monitor, _dc, rect_pointer, _data):
        rect = rect_pointer.contents
        rects.append((rect.left, rect.top, rect.right, rect.bottom))
        return True

    callback = callback_type(collect)
    if not ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0):
        return []
    return rects


def rect_contains(rect, x: int, y: int) -> bool:
    left, top, right, bottom = rect
    return left <= x < right and top <= y < bottom


def window_has_visible_monitor(rects, x: int, y: int, width: int, height: int) -> bool:
    """窗口中心必须落在某台显示器内，避免断屏后留在不可见坐标。"""
    return any(rect_contains(rect, x + width // 2, y + height // 2) for rect in rects)


def primary_rect(rects) -> tuple[int, int, int, int] | None:
    return next((rect for rect in rects if rect[0] == 0 and rect[1] == 0), None)
