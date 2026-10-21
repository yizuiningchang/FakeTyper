"""真实键盘链路验证（M1 关键验收点）。

不依赖人工按键：用 ``keyboard.send`` 注入真实 keybd_event 按键，
这些事件会被 ``keyboard`` 库的低层钩子处理（区别于 VK_PACKET），
从而验证：
1. 按键触发模式的抑制钩子确实拦截了真实按键；
2. 被拦截的按键正确路由到引擎并推进游标；
3. 输出完毕后自动回到 idle。

字符的实际发送（type_unicode）用桩替换，避免向终端真实输出。
注意：本测试会注册真实的全局键盘钩子，运行期间若你手动按键会被拦截。

运行：python tests\test_real_suppression.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import keyboard  # noqa: E402

from facktyper.core.hotkey_manager import HotkeyManager  # noqa: E402
from facktyper.core.typing_engine import EngineListener, TypingEngine  # noqa: E402

keyboard.KEY_DOWN = "down"


class _Collector(EngineListener):
    def __init__(self):
        self.chars: list[str] = []
        self.mode = "idle"
        self.finished: list[str] = []
        self.errors: list[str] = []

    def on_mode_changed(self, mode):
        self.mode = mode

    def on_finished(self, reason):
        self.finished.append(reason)

    def on_error(self, msg):
        self.errors.append(msg)

    def on_char(self, char):
        self.chars.append(char)


def _wait(predicate, timeout=1.0, step=0.01):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def _inject_real_key(name: str) -> None:
    """用底层 keybd_event 注入一个真实按键（绕过 keyboard 库的 is_replaying 过滤），
    使其被低层钩子处理——等价于模拟一次真实硬件按键。"""
    os_kb = keyboard._os_keyboard
    scan_code = next(iter(os_kb.map_name(name)))[0]
    os_kb.press(scan_code)
    os_kb.release(scan_code)


def test_real_key_suppression():
    print("[test] 真实键盘链路：抑制 + 路由 + 推进游标")
    hm = HotkeyManager()
    eng = TypingEngine(hm)
    sent: list[str] = []
    eng._send_char = lambda ch: sent.append(ch)  # 桩：不真实输出，避免污染终端
    col = _Collector()
    eng.add_listener(col)
    eng.set_content("XY", "real")

    eng.start_key_mode()
    assert hm.suppress_active, "抑制钩子未注册"
    print("  · 抑制钩子已注册，注入真实按键 a ...")

    _inject_real_key("a")
    assert _wait(lambda: len(sent) >= 1, timeout=0.5), f"按键 a 未被路由，sent={sent}"
    assert sent == ["X"], f"首个输出应为 X，实际 {sent}"
    print("  [OK] 按键 a 被拦截并输出 X")

    _inject_real_key("b")
    assert _wait(lambda: len(sent) >= 2, timeout=0.5)
    assert sent == ["X", "Y"], sent
    print("  [OK] 按键 b 被拦截并输出 Y")

    # 再按一次应触发完成
    _inject_real_key("c")
    assert _wait(lambda: col.mode == "idle", timeout=0.5), "输出完毕未回到 idle"
    assert col.finished == ["completed"]
    assert sent == ["X", "Y"], "完成后不应再输出"
    print("  [OK] 输出完毕自动回到 idle 并触发 finished")

    eng.stop_all()
    hm.unhook_all()
    return True


def test_real_auto_mode():
    print("[test] 真实键盘链路：自动匀速输出推进游标")
    hm = HotkeyManager()
    eng = TypingEngine(hm)
    sent: list[str] = []
    eng._send_char = lambda ch: sent.append(ch)
    col = _Collector()
    eng.add_listener(col)
    eng.set_content("12345", "auto")
    eng.auto_speed_ms = 30
    eng.humanize_jitter = False
    eng.punctuation_pause = False

    eng.start_auto_mode()
    assert _wait(lambda: len(sent) >= 3, timeout=1.0), f"自动输出过少: {sent}"
    eng.stop_all()
    assert col.mode == "idle"
    print(f"  [OK] 自动模式输出 {len(sent)} 字符后急停")
    hm.unhook_all()
    return True


def test_type_unicode_smoke():
    print("[test] type_unicode 烟雾测试（不向终端输出，仅验证可调用）")
    from facktyper.core.hotkey_manager import _type_unicode

    if _type_unicode is None:
        print("  [SKIP] _type_unicode 不可用")
        return True
    # 备份剪贴板，验证 type_unicode 不碰剪贴板
    import pyperclip

    pyperclip.copy("CLIPBOARD_MARKER")
    _type_unicode("A")
    _type_unicode("中")
    assert pyperclip.paste() == "CLIPBOARD_MARKER", "type_unicode 不应改动剪贴板"
    print("  [OK] type_unicode 可调用且不触碰剪贴板")
    return True


def main():
    tests = [test_type_unicode_smoke, test_real_key_suppression, test_real_auto_mode]
    print("=" * 56)
    print("FakeTyper Pro —— M1 真实键盘链路验证")
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
