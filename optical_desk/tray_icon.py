from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                            ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.DefWindowProcW.restype = wintypes.LPARAM
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.LONG, wintypes.LONG,
                                   ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

WM_APP_TRAY = 0x8001
WM_COMMAND = 0x0111
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_QUIT = 0x0012
NIM_ADD = 0
NIM_DELETE = 2
NIF_MESSAGE = 1
NIF_ICON = 2
NIF_TIP = 4
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
TPM_BOTTOMALIGN = 0x20
TPM_LEFTALIGN = 0
TPM_RETURNCMD = 0x0100
MF_STRING = 0


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", POINT)]


WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", ctypes.c_ubyte * 16),
                ("hBalloonIcon", wintypes.HICON)]


shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


class TrayIcon:
    def __init__(self, icon_path: str, tooltip: str, on_restore, on_exit):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.on_restore = on_restore
        self.on_exit = on_exit
        self.visible = False
        self.hwnd = None
        self.icon = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.wndproc = WNDPROC(self._window_proc)
        instance = kernel32.GetModuleHandleW(None)
        class_name = "GuanHaiShiGuangTray"
        wc = WNDCLASS(0, self.wndproc, 0, 0, instance, None, None, None, None, class_name)
        user32.RegisterClassW(wc)
        self.hwnd = user32.CreateWindowExW(0, class_name, class_name, 0, 0, 0, 0, 0,
                                           None, None, instance, None)
        self.icon = user32.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
        self.ready.set()
        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    def _data(self):
        data = NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_APP_TRAY
        data.hIcon = self.icon
        data.szTip = self.tooltip
        return data

    def show(self):
        self.ready.wait(2)
        if self.hwnd and not self.visible:
            self.visible = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._data())))

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_APP_TRAY:
            event = lparam & 0xFFFF
            if event == WM_LBUTTONDBLCLK:
                self.on_restore()
            elif event == WM_RBUTTONUP:
                point = POINT()
                user32.GetCursorPos(ctypes.byref(point))
                menu = user32.CreatePopupMenu()
                user32.AppendMenuW(menu, MF_STRING, 1001, "打开观海·拾光")
                user32.AppendMenuW(menu, MF_STRING, 1002, "彻底退出")
                user32.SetForegroundWindow(hwnd)
                command = user32.TrackPopupMenu(menu, TPM_BOTTOMALIGN | TPM_LEFTALIGN | TPM_RETURNCMD,
                                                point.x, point.y, 0, hwnd, None)
                user32.DestroyMenu(menu)
                if command == 1001:
                    self.on_restore()
                elif command == 1002:
                    self.on_exit()
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def hide(self):
        if self.visible and self.hwnd:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._data()))
            self.visible = False

    def stop(self):
        self.hide()
        if self.hwnd and self.thread.native_id:
            user32.PostThreadMessageW(self.thread.native_id, WM_QUIT, 0, 0)
