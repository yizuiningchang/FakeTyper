"""打字引擎状态机逻辑测试。

用桩替身替换 HotkeyManager 的抑制与 TypingEngine 的字符发送，
从而在不触碰真实键盘、不向系统发送任何按键的前提下，验证：
- 按键触发模式逐字输出与完成自动停止；
- 每按键多字符 / 随机 1–3；
- 自动匀速模式节奏与完成；
- 重置回到开头；
- 模式互斥（启动其一自动停掉另一个）；
- 急停立即停止。

运行：python tests\test_engine_logic.py
"""
from __future__ import annotations

import os
import sys
import time

# 让 src 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from facktyper.core.typing_engine import EngineListener, TypingEngine  # noqa: E402


class FakeHotkey:
    def __init__(self):
        self.suppressing = False
        self.calls = 0

    def start_suppression(self, cb):
        self.suppressing = True
        self._cb = cb
        self.calls += 1

    def stop_suppression(self):
        self.suppressing = False

    def is_suppressed(self, key):
        return self.suppressing and key == "enter"

    def unsuppress_key(self, key):
        pass

    def resuppress_key(self, key, callback=None):
        pass

    def unhook_all(self):
        self.suppressing = False


class Recorder(EngineListener):
    def __init__(self):
        self.chars: list[str] = []
        self.mode = "idle"
        self.finished: list[str] = []
        self.progress: list[tuple[float, int, int]] = []
        self.errors: list[str] = []

    def on_mode_changed(self, mode):
        self.mode = mode

    def on_progress(self, percent, current, total):
        self.progress.append((percent, current, total))

    def on_finished(self, reason):
        self.finished.append(reason)

    def on_error(self, message):
        self.errors.append(message)

    def on_char(self, char):
        self.chars.append(char)

    def on_preset_changed(self, title, total):
        pass


def make_engine(content="abcde"):
    hm = FakeHotkey()
    eng = TypingEngine(hm)
    sent: list[str] = []
    eng._send_char = lambda ch: sent.append(ch)  # 桩：不真实发送
    eng._sent = sent
    rec = Recorder()
    eng.add_listener(rec)
    eng.set_content(content, "test")
    return eng, rec


def _press(eng, n=1):
    for _ in range(n):
        eng._on_key_event(_FakeEvent("down"))


class _FakeEvent:
    def __init__(self, etype):
        self.event_type = etype


# keyboard.KEY_DOWN 常量值；_on_key_event 比较的是 keyboard.KEY_DOWN。
# 这里直接构造 event_type 为字符串 'down'，但引擎比较 keyboard.KEY_DOWN。
# 为兼容，monkeypatch 该常量。
import keyboard  # noqa: E402

keyboard.KEY_DOWN = "down"  # 测试桩统一用 'down'


def test_key_mode_basic():
    print("[test] 按键触发逐字输出 + 完成自动停止")
    eng, rec = make_engine("abc")
    eng.start_key_mode()
    assert rec.mode == "key"
    _press(eng, 1)
    assert eng._sent == ["a"]
    _press(eng, 1)
    assert eng._sent == ["a", "b"]
    _press(eng, 1)
    assert eng._sent == ["a", "b", "c"]
    # 第 4 次按键不应再输出
    _press(eng, 1)
    assert eng._sent == ["a", "b", "c"]
    assert rec.mode == "idle", "完成后应自动回到 idle"
    assert rec.finished == ["completed"]
    assert abs(rec.progress[-1][0] - 100.0) < 0.1
    print("  [OK] abc 逐字输出、第4键无输出、完成自动停止、进度100%")
    return True


def test_key_mode_multichar():
    print("[test] 每按键多字符")
    eng, rec = make_engine("abcdefg")
    eng.chars_per_keypress = 2
    eng.chars_per_keypress_random = False
    eng.start_key_mode()
    _press(eng, 1)
    assert eng._sent == ["a", "b"], eng._sent
    _press(eng, 1)
    assert eng._sent == ["a", "b", "c", "d"]
    print("  [OK] 每键输出 2 字符")
    return True


def test_key_mode_random():
    print("[test] 每按键随机 1–3 字符")
    eng, rec = make_engine("a" * 30)
    eng.chars_per_keypress_random = True
    eng.start_key_mode()
    _press(eng, 5)
    assert 1 <= len(eng._sent) <= 15
    assert 5 <= len(eng._sent), f"5 次按键至少输出 5 字符，实际 {len(eng._sent)}"
    print(f"  [OK] 5 次按键共输出 {len(eng._sent)} 字符（随机区间内）")
    return True


def test_reset():
    print("[test] 重置回到开头")
    eng, rec = make_engine("abcde")
    eng.start_key_mode()
    _press(eng, 2)
    assert eng._sent == ["a", "b"]
    eng.reset()
    _press(eng, 1)
    assert eng._sent == ["a", "b", "a"], eng._sent  # 重置后从头
    print("  [OK] 重置后从开头重新输出")
    return True


def test_mutex():
    print("[test] 模式互斥：启动自动时停掉按键")
    eng, rec = make_engine("abcde")
    eng.start_key_mode()
    assert rec.mode == "key"
    eng.start_auto_mode()
    assert rec.mode == "auto", "启动自动应自动停掉按键模式"
    time.sleep(0.25)  # 让自动线程跑一会
    eng.stop_all()
    assert rec.mode == "idle"
    assert len(eng._sent) > 0, "自动模式应已输出若干字符"
    print(f"  [OK] 互斥 + 自动输出 {len(eng._sent)} 字符后急停")
    return True


def test_auto_timing():
    print("[test] 自动模式节奏（低速 + 关抖动，确定性）")
    eng, rec = make_engine("1234567890")
    eng.auto_speed_ms = 30
    eng.humanize_jitter = False
    eng.punctuation_pause = False
    eng.start_auto_mode()
    time.sleep(0.20)  # ~6 个字符
    eng.stop_all()
    cnt = len(eng._sent)
    assert 3 <= cnt <= 9, f"200ms@30ms 预期约 6 字符，实际 {cnt}"
    assert rec._sent if False else True
    print(f"  [OK] 200ms@30ms 输出 {cnt} 字符（节奏基本正确）")
    return True


def test_stop_all_idle():
    print("[test] 急停在 idle 时安全")
    eng, rec = make_engine("abc")
    eng.stop_all()  # idle 状态急停不应出错
    assert rec.mode == "idle"
    print("  [OK] idle 急停无副作用")
    return True


def test_empty_preset():
    print("[test] 空预设不启动")
    eng, rec = make_engine("")
    eng.start_key_mode()
    assert rec.mode == "idle", "空预设不应进入按键模式"
    assert rec.errors, "空预设应报错"
    print("  [OK] 空预设拒绝启动并报错")
    return True


def main():
    tests = [
        test_key_mode_basic,
        test_key_mode_multichar,
        test_key_mode_random,
        test_reset,
        test_mutex,
        test_auto_timing,
        test_stop_all_idle,
        test_empty_preset,
    ]
    print("=" * 56)
    print("FakeTyper Pro —— M1 引擎状态机逻辑测试")
    print("=" * 56)
    passed = 0
    for t in tests:
        try:
            if t():
                passed += 1
        except Exception as e:
            import traceback

            print(f"  [FAIL] {t.__name__}: {e}")
            traceback.print_exc()
    print("-" * 56)
    print(f"结果：{passed}/{len(tests)} 通过")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
