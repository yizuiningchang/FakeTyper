"""单实例守卫：Windows 命名互斥体。

策略：
- 首实例 ``acquire()`` 创建命名互斥体成功 → 返回 True，持有句柄至 ``release()``；
- 第二实例 ``acquire()`` 检测到 ``ERROR_ALREADY_EXISTS`` → 返回 False，随即调用
  ``signal_existing()`` 通过窗口标题 ``FindWindowW`` 找到首实例主窗口，
  恢复（若最小化）并 ``SetForegroundWindow`` 置前唤起。

``SetForegroundWindow`` 受 Windows 前台锁限制，用 ``AttachThreadInput`` 把当前
线程附加到目标窗口的输入队列以绕过该限制。

非 Windows 平台降级为不加锁（``acquire()`` 永远返回 True）。

64 位安全：所有 Win32 函数显式声明 argtypes/restype，HANDLE/HWND 用指针类型，
避免默认 c_int 截断高位地址。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Optional

from ..utils.logger import get_logger

_log = get_logger("single_instance")

# Win32 常量
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9

# 窗口标题（与 MainWindow.setWindowTitle 一致，供 FindWindowW 匹配）
WINDOW_TITLE = "FakeTyper Pro"
# 命名互斥体名（Local\\ 前缀：仅当前会话，避免跨会话误判）
MUTEX_NAME = "Local\\FakeTyperPro_SingleInstance_v1"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _setup_types(kernel32: "ctypes.WinDLL", user32: "ctypes.WinDLL") -> None:
    """显式声明 Win32 函数类型（64 位安全）。"""
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL


class SingleInstance:
    """Windows 命名互斥体单实例守卫。"""

    def __init__(self) -> None:
        self._handle: Optional[int] = None
        self._owns: bool = False
        if _is_windows():
            self._kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            self._user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            _setup_types(self._kernel32, self._user32)
        else:
            self._kernel32 = None
            self._user32 = None

    # ---------------- 互斥体 ----------------

    def acquire(self) -> bool:
        """尝试创建命名互斥体。返回是否为首实例。"""
        if not _is_windows():
            self._owns = True
            return True

        # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName) -> HANDLE
        handle = self._kernel32.CreateMutexW(None, False, MUTEX_NAME)
        err = self._kernel32.GetLastError()
        if not handle:
            _log.warning("CreateMutexW 失败: err=%d", err)
            # 创建失败也允许继续运行（降级），不阻塞应用启动
            self._owns = True
            return True
        if err == _ERROR_ALREADY_EXISTS:
            _log.info("检测到已运行实例（命名互斥体已存在）")
            self._owns = False
            # 第二实例：立即关闭自己创建的冗余 handle，避免泄漏
            try:
                self._kernel32.CloseHandle(handle)
            except Exception:  # noqa: BLE001
                pass
            self._handle = None
            return False
        self._handle = handle
        self._owns = True
        _log.debug("已获得单实例互斥体")
        return True

    def release(self) -> None:
        """释放互斥体句柄（退出时调用）。"""
        if self._handle is not None and self._owns:
            try:
                self._kernel32.CloseHandle(self._handle)
            except Exception:  # noqa: BLE001
                pass
        self._handle = None
        self._owns = False

    # ---------------- 唤起已存在实例 ----------------

    def signal_existing(self) -> bool:
        """查找首实例主窗口并置前唤起。返回是否成功找到并唤起。"""
        if not _is_windows():
            return False
        hwnd = self._user32.FindWindowW(None, WINDOW_TITLE)
        if not hwnd:
            _log.warning("未找到已运行实例的窗口（标题=%r）", WINDOW_TITLE)
            return False

        # 若最小化则恢复
        if self._user32.IsIconic(hwnd):
            self._user32.ShowWindow(hwnd, _SW_RESTORE)

        # 绕过前台锁：AttachThreadInput 附加当前线程到目标窗口线程
        cur_tid = self._kernel32.GetCurrentThreadId()
        tgt_tid = self._user32.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if tgt_tid and tgt_tid != cur_tid:
            try:
                attached = bool(self._user32.AttachThreadInput(cur_tid, tgt_tid, True))
            except Exception:  # noqa: BLE001
                attached = False
        try:
            self._user32.SetForegroundWindow(hwnd)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if attached:
                try:
                    self._user32.AttachThreadInput(cur_tid, tgt_tid, False)
                except Exception:  # noqa: BLE001
                    pass

        # 兜底：再尝试一次置前（某些情况首次会被拒绝）
        try:
            self._user32.SetForegroundWindow(hwnd)
        except Exception:  # noqa: BLE001
            pass
        _log.info("已唤起已运行实例窗口 hwnd=%s", hwnd)
        return True
