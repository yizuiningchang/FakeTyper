"""剪贴板保护器。

设计背景：原 AHK 脚本输出中文时直接覆盖用户剪贴板，是核心痛点之一。

本模块提供两种保护路径：
1. 默认主路径——打字引擎用 ``type_unicode``（VK_PACKET）直接输出任意字符，
   完全不碰剪贴板，剪贴板天然零损失；
2. 备用剪贴板路径——当某些目标应用不支持 VK_PACKET 时可启用，输出前备份
   原剪贴板文本，输出结束后恢复。

``ClipboardGuard`` 实现路径 2：上下文管理器，进入时备份、退出时恢复。
"""
from __future__ import annotations

import threading

try:
    import pyperclip
except Exception:  # noqa: BLE001
    pyperclip = None  # type: ignore

from ..utils.logger import get_logger

_log = get_logger("clipboard_guard")


class ClipboardGuard:
    """剪贴板备份/恢复上下文管理器（线程安全，可重入计数）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._backup: str | None = None
        self._depth = 0  # 支持嵌套，只在最外层备份/恢复

    def __enter__(self) -> "ClipboardGuard":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.restore()

    def acquire(self) -> None:
        """进入保护范围：最外层调用时备份剪贴板。"""
        with self._lock:
            self._depth += 1
            if self._depth == 1:
                self._backup = self._read_clipboard()

    def restore(self) -> None:
        """退出保护范围：最外层调用时恢复剪贴板。"""
        with self._lock:
            if self._depth == 0:
                return
            self._depth -= 1
            if self._depth == 0 and self._backup is not None:
                self._write_clipboard(self._backup)
                self._backup = None

    def copy_text(self, text: str) -> None:
        """向剪贴板写入文本（用于剪贴板粘贴路径）。"""
        if pyperclip is not None:
            try:
                pyperclip.copy(text)
            except Exception as e:  # noqa: BLE001
                _log.warning("写入剪贴板失败: %s", e)

    def _read_clipboard(self) -> str:
        if pyperclip is None:
            return ""
        try:
            return pyperclip.paste() or ""
        except Exception as e:  # noqa: BLE001
            _log.warning("读取剪贴板失败: %s", e)
            return ""

    def _write_clipboard(self, text: str) -> None:
        if pyperclip is None:
            return
        try:
            pyperclip.copy(text)
        except Exception as e:  # noqa: BLE001
            _log.warning("恢复剪贴板失败: %s", e)
