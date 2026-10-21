"""引擎信号桥接：把 ``EngineListener`` 回调适配为 Qt 信号。

设计要点（spec 8）：
- 引擎与 UI 分离：``TypingEngine`` 是纯 Python，通过 listener 回调通信；
- 不阻塞 UI 线程：按键回调来自 keyboard 监听线程，自动模式回调来自工作线程；
- 线程安全：Qt 信号发射本身是线程安全的——当发射方与接收方 ``QObject``
  分属不同线程时，``AutoConnection`` 自动退化为 ``QueuedConnection``，
  回调会被排到接收方（UI 线程）的事件循环执行。因此本桥接只需直接 emit 信号。

UI 层用法::

    bridge = EngineBridge(engine)
    bridge.mode_changed.connect(ui.on_mode)        # "idle"/"key"/"auto"
    bridge.progress_changed.connect(ui.on_progress) # (percent, cur, total)
    bridge.finished.connect(ui.on_finish)           # reason
    bridge.error_occurred.connect(ui.on_error)       # message
    bridge.preset_changed.connect(ui.on_preset)     # (title, total)
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ...core.typing_engine import EngineListener, TypingEngine


class EngineBridge(QObject, EngineListener):
    """引擎事件 → Qt 信号（发射即线程安全）。"""

    # ---- 信号 ----
    mode_changed = Signal(str)
    progress_changed = Signal(float, int, int)   # percent, current, total
    finished = Signal(str)                        # reason
    error_occurred = Signal(str)                  # message
    char_output = Signal(str)                     # 单字符（调试/可视化用）
    preset_changed = Signal(str, int)            # title, total

    def __init__(self, engine: TypingEngine, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        # EngineListener 无 __init__（全是 no-op 方法）
        self._engine = engine
        engine.add_listener(self)

    # ---- EngineListener 回调（可能来自非 UI 线程，直接 emit 即线程安全）----

    def on_mode_changed(self, mode: str) -> None:
        self.mode_changed.emit(mode)

    def on_progress(self, percent: float, current: int, total: int) -> None:
        self.progress_changed.emit(percent, current, total)

    def on_finished(self, reason: str) -> None:
        self.finished.emit(reason)

    def on_error(self, message: str) -> None:
        self.error_occurred.emit(message)

    def on_char(self, char: str) -> None:
        self.char_output.emit(char)

    def on_preset_changed(self, title: str, total: int) -> None:
        self.preset_changed.emit(title, total)

    # ---- 生命周期 ----
    def detach(self) -> None:
        """从引擎解绑（窗口关闭时调用）。"""
        self._engine.remove_listener(self)
