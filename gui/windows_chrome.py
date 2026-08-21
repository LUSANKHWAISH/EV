"""
Windows native chrome integration for the E.V. Qt Quick window.

Purpose:
- Keep the E.V. custom QML title bar and controls.
- Preserve native Windows Aero Snap / edge docking.
- Preserve native minimize/maximize window semantics.
- Remove the standard Windows caption/frame visually.

Windows-only. Other platforms are a safe no-op.
"""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QAbstractNativeEventFilter


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    GWL_STYLE = -16

    WS_POPUP = 0x80000000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000

    WM_NCCALCSIZE = 0x0083

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    SWP_NOOWNERZORDER = 0x0200

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    GetWindowLongW = user32.GetWindowLongW
    GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    GetWindowLongW.restype = ctypes.c_long

    SetWindowLongW = user32.SetWindowLongW
    SetWindowLongW.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_long,
    ]
    SetWindowLongW.restype = ctypes.c_long

    SetWindowPos = user32.SetWindowPos
    SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    SetWindowPos.restype = wintypes.BOOL


class _EVWindowsNativeEventFilter(QAbstractNativeEventFilter):
    """Suppress the native caption/frame while retaining its capabilities."""

    def __init__(self, hwnd: int) -> None:
        super().__init__()
        self._hwnd = int(hwnd)

    def nativeEventFilter(self, event_type: Any, message: Any):
        if sys.platform != "win32":
            return False, 0

        try:
            event_name = bytes(event_type)
        except Exception:
            return False, 0

        if event_name not in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG",
        ):
            return False, 0

        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0

        msg_hwnd = int(msg.hWnd or 0)

        if msg_hwnd != self._hwnd:
            return False, 0

        # Returning zero for WM_NCCALCSIZE with wParam=True makes
        # the entire native window client area. Windows still sees
        # the caption/thick-frame style bits, but does not draw the
        # normal caption/frame over the E.V. custom chrome.
        if msg.message == WM_NCCALCSIZE and msg.wParam:
            return True, 0

        return False, 0


def install_windows_native_chrome(app, window):
    """Enable native Snap capabilities for the E.V. custom window."""

    if sys.platform != "win32":
        return None

    hwnd = int(window.winId())

    if not hwnd:
        raise RuntimeError(
            "E.V. Windows chrome: QWindow has no native HWND."
        )

    # Install the event filter BEFORE forcing a native frame recalculation.
    event_filter = _EVWindowsNativeEventFilter(hwnd)
    app.installNativeEventFilter(event_filter)

    old_style_signed = GetWindowLongW(hwnd, GWL_STYLE)
    old_style = int(old_style_signed) & 0xFFFFFFFF

    # Convert Qt's frameless WS_POPUP into a native-capable top-level
    # window while retaining the E.V. client-drawn frame.
    # Preserve the native capabilities Windows needs for Aero Snap,
    # resize, minimize and maximize, but DO NOT restore WS_CAPTION.
    #
    # WS_CAPTION is what makes Windows draw the normal title bar above
    # E.V.'s custom QML chrome.
    required_style = (
        WS_THICKFRAME
        | WS_SYSMENU
        | WS_MINIMIZEBOX
        | WS_MAXIMIZEBOX
    )

    new_style = (
        (old_style & ~WS_POPUP & ~WS_CAPTION)
        | required_style
    )
    new_style &= 0xFFFFFFFF

    ctypes.set_last_error(0)

    SetWindowLongW(
        hwnd,
        GWL_STYLE,
        ctypes.c_long(new_style).value,
    )

    error = ctypes.get_last_error()

    if error:
        raise ctypes.WinError(error)

    # Force Windows to recalculate the frame. WM_NCCALCSIZE above
    # removes the visual native frame during this recalculation.
    ok = SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        SWP_NOMOVE
        | SWP_NOSIZE
        | SWP_NOZORDER
        | SWP_NOACTIVATE
        | SWP_NOOWNERZORDER
        | SWP_FRAMECHANGED,
    )

    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())

    print(
        "EV_WINDOWS_CHROME: ENABLED "
        f"HWND=0x{hwnd:X} "
        f"STYLE=0x{new_style:08X}"
    )

    return event_filter
