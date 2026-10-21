"""打字引擎：核心状态机 + 字符输出 + 人性化。

设计要点：
- 纯 Python（不依赖 Qt），通过 ``EngineListener`` 回调对外通信，
  UI 层（M2）用薄适配器转成 Qt 信号，满足"引擎与 UI 分离、不阻塞 UI 线程"；
- 三态：IDLE / KEY（按键触发）/ AUTO（自动匀速），两者互斥；
- 字符输出统一走 ``type_unicode``（VK_PACKET，绕过键盘钩子，不触发回调、
  不被抑制、且完全不碰剪贴板，天然满足"剪贴板保护"目标）；
  特殊键（Enter）在抑制期间临时摘单键钩子再发送；
- 自动模式用独立工作线程 + 可中断 sleep，支持随机抖动与标点停顿；
- 按键模式每按一键输出 n 个字符（可配，可随机 1–3）。

线程模型：键盘回调在 keyboard 库的监听线程触发；自动模式在自建工作线程触发。
所有状态读写经 ``_lock`` 保护，listener 回调在持锁外触发以防递归。
"""
from __future__ import annotations

import random
import threading
import time
from typing import Callable

import keyboard

from ..utils.logger import get_logger
from .hotkey_manager import HotkeyManager, _type_unicode

_log = get_logger("engine")

# 标点停顿字符集（中英文）—— 按停顿时长分级，差异化更接近真人节奏
# 短停点：逗号 / 分号 / 冒号（句中停顿）
_PUNCT_SHORT_CHARS = set(",;:，；：")
# 句末点：句号 / 感叹号 / 问号（句末停顿）
_PUNCT_SENTENCE_CHARS = set(".!?。！？")
# 换行：段落停顿（最长）
_PUNCT_NEWLINE_CHARS = set("\n\r")
# 合集（兼容旧逻辑判断"是否标点停顿"）
_PUNCT_PAUSE_CHARS = _PUNCT_SHORT_CHARS | _PUNCT_SENTENCE_CHARS | _PUNCT_NEWLINE_CHARS

# 思考停顿：低概率触发额外长停顿，模拟真人中途思考
_THINKING_PAUSE_PROB = 0.04        # 触发概率
_THINKING_PAUSE_MS = (500, 1200)   # 额外停顿时长区间

# 最小 / 最大自动延迟（毫秒），夹断人性化取值
_MIN_DELAY_MS = 10
_MAX_DELAY_MS = 5000


class EngineListener:
    """引擎事件监听基类，子类按需覆盖。默认实现均为 no-op。"""

    def on_mode_changed(self, mode: str) -> None: ...
    def on_progress(self, percent: float, current: int, total: int) -> None: ...
    def on_finished(self, reason: str) -> None: ...
    def on_error(self, message: str) -> None: ...
    def on_char(self, char: str) -> None: ...
    def on_preset_changed(self, title: str, total: int) -> None: ...


class _PrintingListener(EngineListener):
    """简单打印监听，用于命令行调试。"""

    def on_mode_changed(self, mode):
        print(f"[engine] mode -> {mode}")

    def on_progress(self, percent, current, total):
        print(f"[engine] progress {percent:.0f}% ({current}/{total})")

    def on_finished(self, reason):
        print(f"[engine] finished: {reason}")

    def on_error(self, message):
        print(f"[engine] ERROR: {message}")

    def on_char(self, char):
        rep = char.replace("\n", "\\n").replace("\t", "\\t")
        print(f"[engine] char '{rep}'")

    def on_preset_changed(self, title, total):
        print(f"[engine] preset='{title}' total={total}")


class TypingEngine:
    IDLE = "idle"
    KEY = "key"
    AUTO = "auto"

    def __init__(self, hotkey: HotkeyManager) -> None:
        self._hotkey = hotkey
        self._content: str = ""
        self._title: str = ""
        self._idx: int = 0
        self._mode: str = self.IDLE
        self._listeners: list[EngineListener] = []
        self._lock = threading.RLock()
        self._rng = random.Random()

        # 自动模式工作线程
        self._auto_thread: threading.Thread | None = None
        self._auto_stop = threading.Event()

        # 人性化参数（由配置注入）
        self.auto_speed_ms: int = 80
        self.humanize_jitter: bool = True
        self.jitter_amount: float = 0.3
        self.punctuation_pause: bool = True
        self.humanize_thinking_pause: bool = True
        self.chars_per_keypress: int = 1
        self.chars_per_keypress_random: bool = False

        self._last_char: str = ""

    # ---------------- 监听 ----------------

    def add_listener(self, listener: EngineListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: EngineListener) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _emit(self, method: str, *args, **kwargs) -> None:
        for ln in list(self._listeners):
            try:
                getattr(ln, method)(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                _log.exception("listener %s 异常: %s", method, e)

    # ---------------- 配置注入 ----------------

    def apply_params(
        self,
        auto_speed_ms: int,
        humanize_jitter: bool,
        jitter_amount: float,
        punctuation_pause: bool,
        chars_per_keypress: int,
        chars_per_keypress_random: bool,
        humanize_thinking_pause: bool = True,
    ) -> None:
        with self._lock:
            self.auto_speed_ms = auto_speed_ms
            self.humanize_jitter = humanize_jitter
            self.jitter_amount = jitter_amount
            self.punctuation_pause = punctuation_pause
            self.humanize_thinking_pause = humanize_thinking_pause
            self.chars_per_keypress = chars_per_keypress
            self.chars_per_keypress_random = chars_per_keypress_random

    # ---------------- 预设 ----------------

    def set_content(self, content: str, title: str = "") -> None:
        with self._lock:
            was_active = self._mode != self.IDLE
            if was_active:
                self._stop_locked()
            self._content = content or ""
            self._title = title or ""
            self._idx = 0
            self._last_char = ""
            total = len(self._content)
        self._emit("on_preset_changed", self._title, total)
        self._emit("on_progress", 0.0, 0, total)

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def progress(self) -> tuple[int, int]:
        with self._lock:
            return self._idx, len(self._content)

    @property
    def content(self) -> str:
        with self._lock:
            return self._content

    # ---------------- 模式控制（互斥） ----------------

    def toggle_key_mode(self) -> None:
        with self._lock:
            if self._mode == self.KEY:
                self._stop_locked()
            else:
                self._start_key_locked()
        self._emit_mode()

    def toggle_auto_mode(self) -> None:
        with self._lock:
            if self._mode == self.AUTO:
                self._stop_locked()
            else:
                self._start_auto_locked()
        self._emit_mode()

    def start_key_mode(self) -> None:
        with self._lock:
            self._start_key_locked()
        self._emit_mode()

    def start_auto_mode(self) -> None:
        with self._lock:
            self._start_auto_locked()
        self._emit_mode()

    def stop_all(self) -> None:
        """急停：停止一切输出并恢复键盘正常。"""
        with self._lock:
            self._stop_locked()
        self._emit_mode()
        self._emit("on_finished", "stopped")

    def reset(self) -> None:
        """重置输出游标到开头（当前模式保持不变）。"""
        with self._lock:
            self._idx = 0
            self._last_char = ""
            total = len(self._content)
        self._emit("on_progress", 0.0, 0, total)
        _log.info("已重置到开头")

    # ---------------- 内部：启停（持锁调用） ----------------

    def _start_key_locked(self) -> None:
        self._stop_locked()
        if not self._content:
            self._emit("on_error", "当前预设为空")
            return
        self._mode = self.KEY
        self._idx = 0
        self._last_char = ""
        self._hotkey.start_suppression(self._on_key_event)
        _log.info("按键触发模式 ON")

    def _start_auto_locked(self) -> None:
        self._stop_locked()
        if not self._content:
            self._emit("on_error", "当前预设为空")
            return
        self._mode = self.AUTO
        self._idx = 0
        self._last_char = ""
        self._auto_stop.clear()
        self._auto_thread = threading.Thread(
            target=self._auto_loop, name="FakeTyper-Auto", daemon=True
        )
        self._auto_thread.start()
        _log.info("自动匀速模式 ON (%dms)", self.auto_speed_ms)

    def _stop_locked(self) -> None:
        prev_mode = self._mode
        if prev_mode == self.IDLE:
            return
        self._mode = self.IDLE
        if prev_mode == self.KEY:
            self._hotkey.stop_suppression()
        elif prev_mode == self.AUTO:
            self._auto_stop.set()
        _log.info("已停止模式: %s", prev_mode)

    def _emit_mode(self) -> None:
        self._emit("on_mode_changed", self.mode)

    # ---------------- 按键触发回调 ----------------

    def _on_key_event(self, event) -> None:
        """keyboard 库抑制回调（监听线程触发）。仅处理 keydown。"""
        try:
            if event.event_type != keyboard.KEY_DOWN:
                return
        except Exception:  # noqa: BLE001
            # 某些事件对象结构异常时，保守按 down 处理
            pass
        try:
            self._output_step()
        except Exception as e:  # noqa: BLE001
            _log.exception("按键输出异常: %s", e)
            self._emit("on_error", f"按键输出异常: {e}")

    # ---------------- 自动模式工作线程 ----------------

    def _auto_loop(self) -> None:
        while not self._auto_stop.is_set():
            with self._lock:
                if self._mode != self.AUTO:
                    break
                done = self._output_step_locked()
            if done:
                break
            delay = self._next_auto_delay_ms()
            # 可中断 sleep
            if self._auto_stop.wait(delay / 1000.0):
                break

    def _next_auto_delay_ms(self) -> int:
        base = self.auto_speed_ms
        if self.humanize_jitter and self.jitter_amount > 0:
            base = base * (1.0 + self._rng.uniform(-self.jitter_amount, self.jitter_amount))
        # 标点停顿差异化：短停点 / 句末点 / 换行 三档
        if self.punctuation_pause and self._last_char in _PUNCT_PAUSE_CHARS:
            if self._last_char in _PUNCT_NEWLINE_CHARS:
                base += self._rng.uniform(250, 450)        # 换行：段落停顿
            elif self._last_char in _PUNCT_SENTENCE_CHARS:
                base += self._rng.uniform(250, 400)        # 句末：较长停顿
            else:  # _PUNCT_SHORT_CHARS
                base += self._rng.uniform(150, 250)        # 句中：短停顿
        # 思考停顿：低概率额外长停顿，模拟真人中途思考
        if self.humanize_thinking_pause and self._rng.random() < _THINKING_PAUSE_PROB:
            base += self._rng.uniform(*_THINKING_PAUSE_MS)
        return int(max(_MIN_DELAY_MS, min(_MAX_DELAY_MS, base)))

    # ---------------- 输出步进 ----------------

    def _output_step(self) -> bool:
        """按键触发模式输出步进（在监听线程调用）。返回是否完成。"""
        with self._lock:
            return self._output_step_locked()

    def _output_step_locked(self) -> bool:
        """输出下一步字符。返回是否已输出完毕。"""
        if self._mode == self.IDLE:
            return True
        total = len(self._content)
        if self._idx >= total:
            reason = "completed"
            self._stop_locked()
            self._emit_mode()
            self._emit("on_finished", reason)
            self._emit("on_progress", 100.0, total, total)
            return True

        # 按键模式可输出多字符；自动模式固定 1 字符
        if self._mode == self.KEY:
            n = self._chars_per_step()
        else:
            n = 1
        chunk = self._content[self._idx : self._idx + n]
        self._idx += len(chunk)

        # 逐字发送（保持节奏；自动模式每 tick 1 字，按键模式可连续）
        released = False
        for ch in chunk:
            try:
                self._send_char(ch)
            except Exception as e:  # noqa: BLE001
                _log.exception("发送字符失败 '%s': %s", ch, e)
                self._emit("on_error", f"发送字符失败: {e}")
                released = True
                break
            self._last_char = ch
            self._emit("on_char", ch)

        percent = (self._idx / total * 100.0) if total else 100.0
        self._emit("on_progress", percent, self._idx, total)

        if self._idx >= total:
            self._stop_locked()
            self._emit_mode()
            self._emit("on_finished", "completed")
            self._emit("on_progress", 100.0, total, total)
            return True
        return False

    def _chars_per_step(self) -> int:
        if self.chars_per_keypress_random:
            return self._rng.randint(1, 3)
        return max(1, int(self.chars_per_keypress))

    # ---------------- 底层字符发送 ----------------

    def _send_char(self, ch: str) -> None:
        code = ord(ch)
        if code in (10, 13):  # \n \r → Enter 键
            self._send_special_key("enter")
        elif code == 9:  # \t → Tab 键（未在抑制白名单，直接发送）
            keyboard.send("tab")
        elif code == 8:  # \b → Backspace（未抑制，直接发送）
            keyboard.send("backspace")
        else:
            # 其余所有可打印字符（含 ASCII 标点、空格、CJK）走 Unicode 发送，
            # 绕过键盘钩子：不触发回调、不被抑制、不碰剪贴板。
            self._type_unicode(ch)

    @staticmethod
    def _type_unicode(ch: str) -> None:
        if _type_unicode is not None:
            _type_unicode(ch)
        else:  # pragma: no cover - 兜底
            keyboard.write(ch, exact=True)

    def _send_special_key(self, key: str) -> None:
        """发送被抑制的特殊键：临时摘钩→发送→重挂。"""
        suppressed = self._hotkey.is_suppressed(key)
        if suppressed:
            self._hotkey.unsuppress_key(key)
        try:
            keyboard.send(key)
        finally:
            if suppressed:
                self._hotkey.resuppress_key(key)

    # ---------------- 生命周期 ----------------

    def shutdown(self) -> None:
        """退出前清理。"""
        self.stop_all()
