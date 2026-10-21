"""热键管理器。

职责：
1. 注册 / 注销 F1–F6 功能热键（非抑制，仅触发回调）——对应总开关开启时启用；
2. 管理按键触发模式的"抑制钩子"——屏蔽白名单真实按键并路由到回调，
   输出自身字符时临时摘除单键抑制避免被自身拦截（见 typing_engine）。

注意：``keyboard`` 库的底层钩子会跳过 ``VK_PACKET``（type_unicode）事件，
因此 Unicode 字符输出不会触发回调、也不会被抑制；只有走 keybd_event 的
特殊键（Enter/Backspace 等）才需要在输出时临时摘钩。
"""
from __future__ import annotations

import threading
from typing import Callable

import keyboard

from ..utils.logger import get_logger

_log = get_logger("hotkey")

# 按键触发模式需屏蔽的白名单（覆盖字母、数字、空格、回车及常用标点）。
# 与原 AHK 脚本一致；Tab / 方向 / 退格 / 功能键不在其内，正常透传。
SUPPRESSED_KEYS: tuple[str, ...] = tuple(
    [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [chr(c) for c in range(ord("0"), ord("9") + 1)]
    + ["space", "enter"]
    + ["-", "=", "[", "]", "\\", ";", "'", ",", ".", "/", "`"]
)

# keyboard 库内部 Unicode 发送函数（VK_PACKET，绕过钩子）
try:
    _type_unicode = keyboard._os_keyboard.type_unicode  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - 兜底
    _type_unicode = None  # type: ignore


class HotkeyManager:
    """统一管理功能热键与按键抑制。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # action -> hotkey handle
        self._func_handles: dict[str, object] = {}
        # action -> callback
        self._func_callbacks: dict[str, Callable[[], None]] = {}
        # 抑制状态：key -> handle
        self._suppress_hooks: dict[str, object] = {}
        self._suppress_callback: Callable[[keyboard.KeyboardEvent], None] | None = None

    # ---------------- 功能热键（F1–F6） ----------------

    def register_function(self, key: str, callback: Callable[[], None]) -> bool:
        """注册一个功能热键。返回是否成功。"""
        key = key.strip()
        if not key:
            return False
        with self._lock:
            try:
                handle = keyboard.add_hotkey(key, callback, suppress=False)
            except Exception as e:  # noqa: BLE001
                _log.warning("注册热键 %s 失败: %s", key, e)
                return False
            self._func_handles[id(callback)] = handle
            self._func_callbacks[id(callback)] = callback
            _log.debug("已注册功能热键 %s", key)
            return True

    def unregister_all_functions(self) -> None:
        with self._lock:
            for handle in list(self._func_handles.values()):
                try:
                    keyboard.remove_hotkey(handle)
                except Exception:  # noqa: BLE001
                    pass
            self._func_handles.clear()
            self._func_callbacks.clear()
            _log.debug("已注销全部功能热键")

    # ---------------- 按键触发模式：抑制 ----------------

    def start_suppression(self, callback: Callable[[keyboard.KeyboardEvent], None]) -> None:
        """开启白名单按键抑制，路由到 callback。"""
        with self._lock:
            self.stop_suppression()
            self._suppress_callback = callback
            for k in SUPPRESSED_KEYS:
                try:
                    h = keyboard.hook_key(k, callback, suppress=True)
                    self._suppress_hooks[k] = h
                except Exception as e:  # noqa: BLE001
                    _log.warning("注册抑制键 %s 失败: %s", k, e)
            _log.info("按键抑制已开启（%d 键）", len(self._suppress_hooks))

    def stop_suppression(self) -> None:
        with self._lock:
            for k, h in list(self._suppress_hooks.items()):
                try:
                    keyboard.unhook(h)
                except Exception:  # noqa: BLE001
                    pass
            self._suppress_hooks.clear()
            self._suppress_callback = None
            _log.info("按键抑制已关闭")

    def is_suppressed(self, key: str) -> bool:
        with self._lock:
            return key in self._suppress_hooks

    def unsuppress_key(self, key: str) -> None:
        """临时摘除单个键的抑制（用于输出特殊键时避免自拦截）。"""
        with self._lock:
            h = self._suppress_hooks.pop(key, None)
            if h is not None:
                try:
                    keyboard.unhook(h)
                except Exception:  # noqa: BLE001
                    pass

    def resuppress_key(self, key: str, callback: Callable[[keyboard.KeyboardEvent], None] | None = None) -> None:
        """重新挂上单键抑制。"""
        with self._lock:
            if key in self._suppress_hooks:
                return
            cb = callback or self._suppress_callback
            if cb is None:
                return
            try:
                h = keyboard.hook_key(key, cb, suppress=True)
                self._suppress_hooks[key] = h
            except Exception as e:  # noqa: BLE001
                _log.warning("重新抑制键 %s 失败: %s", key, e)

    @property
    def suppress_active(self) -> bool:
        with self._lock:
            return bool(self._suppress_hooks)

    def unhook_all(self) -> None:
        """全部清理（退出前调用）。"""
        self.unregister_all_functions()
        self.stop_suppression()
