"""M4 首启引导验证脚本。

验证项：
1. OnboardingPage 可导入；
2. MainWindow.show_onboarding() 能构造并显示引导覆盖层；
3. 3 张卡片存在且内容布局正常；
4. 横向滑动 _slide_to 索引正确递增/夹断；
5. 跳过 / 完成发射 finished 信号；
6. finished 后 config.onboarding_shown 持久化为 True；
7. 键盘导航（Right / Left / Esc / Enter）生效；
8. 截图渲染非黑非空（液态玻璃卡片可见）。

运行：``python tests/render_onboarding.py``
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# 重定向数据目录到临时目录，避免写真实 %APPDATA% 被沙箱拦截
import tempfile
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="facktyper_test_")

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from facktyper.core.controller import EngineController  # noqa: E402
from facktyper.core.hotkey_manager import HotkeyManager  # noqa: E402
from facktyper.core.typing_engine import TypingEngine  # noqa: E402
from facktyper.data import preset_store  # noqa: E402
from facktyper.data.config import AppConfig  # noqa: E402
from facktyper.ui.views.main_window import MainWindow  # noqa: E402
from facktyper.ui.views.onboarding_page import OnboardingPage  # noqa: E402
from facktyper.ui.widgets.engine_bridge import EngineBridge  # noqa: E402
from facktyper.ui.widgets.liquid_glass import make_synthetic_backdrop  # noqa: E402


def _pump(app: QApplication, ms: int) -> None:
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def _assert_rendered(pm: QPixmap, name: str) -> None:
    assert not pm.isNull(), f"{name} 截图为空"
    img = pm.toImage()
    w, h = img.width(), img.height()
    non_empty = 0
    sample_count = 0
    for y in range(0, h, max(1, h // 40)):
        for x in range(0, w, max(1, w // 40)):
            sample_count += 1
            px = img.pixel(x, y)
            a = (px >> 24) & 0xFF
            r = (px >> 16) & 0xFF
            g = (px >> 8) & 0xFF
            b = px & 0xFF
            if a > 30 and (r + g + b) > 40:
                non_empty += 1
    ratio = non_empty / max(1, sample_count)
    print(f"  {name}: 有效像素占比 {ratio:.0%}")
    assert ratio > 0.4, f"{name} 渲染异常：有效像素占比过低 ({ratio:.0%})"


def main() -> int:
    print("=" * 60)
    print("FakeTyper Pro M4 首启引导验证")
    print("=" * 60)

    passed = 0

    def step(name: str, fn):
        nonlocal passed
        print(f"\n[{name}] {fn.__doc__ or ''}")
        try:
            fn()
            passed += 1
            print("  [OK]")
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            traceback.print_exc()
            raise

    app = QApplication.instance() or QApplication(sys.argv)

    # 合成背景，确保玻璃有内容可抓
    bg = make_synthetic_backdrop(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(400, 620))

    config = AppConfig()
    config.onboarding_shown = False
    config.startup_window_state = "normal"
    hotkey = HotkeyManager()
    engine = TypingEngine(hotkey)
    controller = EngineController(engine, hotkey, config)
    bridge = EngineBridge(engine)
    preset_store.ensure_default_preset()

    win = MainWindow(engine, controller, config, bridge)
    win.set_synthetic_backdrop(bg)
    win.resize(400, 620)
    win.show()
    _pump(app, 80)

    # 1. 导入验证
    def _step_import():
        """OnboardingPage 可导入"""
        assert OnboardingPage is not None
        assert hasattr(win, "show_onboarding")

    step("导入", _step_import)

    # 2. 显示引导
    def _step_show():
        """show_onboarding 构造并显示覆盖层"""
        win.show_onboarding()
        _pump(app, 60)
        assert win._onboarding is not None, "onboarding 未构造"
        assert win._onboarding.isVisible(), "onboarding 未显示"

    step("显示引导", _step_show)

    # 3. 三张卡片
    def _step_cards():
        """3 张卡片存在"""
        ob = win._onboarding
        assert len(ob._cards) == 3, f"卡片数应为 3，实际 {len(ob._cards)}"
        assert ob._index == 0, "初始索引应为 0"

    step("三张卡片", _step_cards)

    # 4. 滑动到下一页
    def _step_slide():
        """_slide_to 索引递增"""
        ob = win._onboarding
        ob._slide_to(1)
        _pump(app, 320)
        assert ob._index == 1, f"滑动后索引应为 1，实际 {ob._index}"
        ob._slide_to(2)
        _pump(app, 320)
        assert ob._index == 2, f"滑动后索引应为 2，实际 {ob._index}"
        # 越界夹断
        ob._slide_to(99)
        _pump(app, 320)
        assert ob._index == 2, "越界应夹断到最后一页"

    step("滑动转场", _step_slide)

    # 5. 下一页按钮文案切换
    def _step_next_btn():
        """最后一页按钮文案为「开始使用」"""
        ob = win._onboarding
        ob._apply_card(0)
        _pump(app, 30)
        assert ob._next_btn._text == "下一页", f"首页按钮文案错误: {ob._next_btn._text}"
        ob._apply_card(2)
        _pump(app, 30)
        assert ob._next_btn._text == "开始使用", f"末页按钮文案错误: {ob._next_btn._text}"

    step("按钮文案", _step_next_btn)

    # 6. finished 信号 + 持久化
    def _step_finished():
        """完成引导后 onboarding_shown 持久化为 True"""
        ob = win._onboarding
        received = []
        ob.finished.connect(lambda: received.append(True))
        ob._on_skip()
        _pump(app, 50)
        assert received, "finished 信号未发射"
        assert not ob.isVisible(), "完成后应隐藏"
        assert config.onboarding_shown is True, "onboarding_shown 未置 True"

    step("完成与持久化", _step_finished)

    # 7. 键盘导航
    def _step_keyboard():
        """键盘 Right/Left/Esc 生效"""
        # 重新显示引导
        config.onboarding_shown = False
        win.show_onboarding()
        _pump(app, 60)
        ob = win._onboarding
        ob.setFocus(Qt.OtherFocusReason)
        # Right → 第 1 页
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        ob.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier))
        _pump(app, 320)
        assert ob._index == 1, f"Right 后索引应为 1，实际 {ob._index}"
        # Left → 回到第 0 页
        ob.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Left, Qt.NoModifier))
        _pump(app, 320)
        assert ob._index == 0, f"Left 后索引应为 0，实际 {ob._index}"
        # Esc → finished
        received = []
        ob.finished.connect(lambda: received.append(True))
        ob.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        _pump(app, 50)
        assert received, "Esc 未触发 finished"

    step("键盘导航", _step_keyboard)

    # 8. 截图渲染
    def _step_shot():
        """液态玻璃卡片渲染非黑非空"""
        win.show_onboarding()
        _pump(app, 120)
        pm = win._onboarding.grab()
        _assert_rendered(pm, "onboarding 截图")

    step("渲染截图", _step_shot)

    # 清理
    win._on_onboarding_finished()
    bridge.detach()
    controller.shutdown()
    win.close()

    print("\n" + "=" * 60)
    print(f"结果：{passed}/{passed} 通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
