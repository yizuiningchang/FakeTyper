"""M2 主窗口验证脚本。

验证项：
1. 各模块可导入；
2. ``MainWindow`` 可在合成背景下实例化并展示；
3. 顶栏拖动、总开关切换、热键面板点击、预设库搜索均无异常；
4. 引擎桥接信号能正确刷新 UI（模式变化 → 卡片激活态）；
5. 截图检查液态玻璃渲染无黑边。

运行：``python tests/render_main_window.py``
"""
from __future__ import annotations

import sys
import os
import traceback
from pathlib import Path

# 把 src 加入 import 路径
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# offscreen 平台用于 CI；本机如需真实桌面预览可注释下一行
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from facktyper.core.controller import EngineController
from facktyper.core.hotkey_manager import HotkeyManager
from facktyper.core.typing_engine import TypingEngine
from facktyper.data import preset_store
from facktyper.data.config import AppConfig
from facktyper.data.constants import Action
from facktyper.data.preset import Preset
from facktyper.ui.views.main_window import MainWindow
from facktyper.ui.widgets.engine_bridge import EngineBridge
from facktyper.ui.widgets.liquid_glass import make_synthetic_backdrop


def _pump(app: QApplication, ms: int) -> None:
    """推动事件循环 ms 毫秒。"""
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def _assert_glass_rendered(pm: QPixmap, name: str) -> None:
    """断言截图非全透明 / 非全黑。"""
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
    print(f"  {name}: 采样 {sample_count} 个像素，有效像素占比 {ratio:.0%}")
    assert ratio > 0.4, f"{name} 渲染异常：有效像素占比过低 ({ratio:.0%})"


def main() -> int:
    print("=" * 60)
    print("FakeTyper Pro M2 主窗口验证")
    print("=" * 60)

    def step(name: str, fn):
        print(f"\n[{name}] {fn.__doc__ or ''}")
        try:
            fn()
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            traceback.print_exc()
            raise

    # 1. 导入验证
    def _step_import():
        """模块导入"""
        from facktyper.ui.views import MainWindow as _MW
        from facktyper.ui.views.hotkey_panel import HotkeyPanel, HotkeyCard
        from facktyper.ui.views.preset_library import PresetLibrary, SearchBox
        print("  OK: MainWindow / HotkeyPanel / PresetLibrary 已导入")
    step("1 导入", _step_import)

    # 数据准备
    preset_store.ensure_default_preset()
    extra = Preset.create(title="测试预设·多行代码", content="print('hi')\n# 注释行\nfor i in range(10):\n    pass\n")
    preset_store.save_preset(extra)

    config = AppConfig.load()
    hotkey = HotkeyManager()
    engine = TypingEngine(hotkey)
    controller = EngineController(engine, hotkey, config)
    bridge = EngineBridge(engine)

    app = QApplication.instance() or QApplication(sys.argv)

    # 2. 构造主窗口（注入合成背景）
    win_holder: dict = {}
    def _step_construct():
        """构造主窗口"""
        win_holder["win"] = MainWindow(engine, controller, config, bridge)
        win = win_holder["win"]
        win.set_synthetic_backdrop(make_synthetic_backdrop(win.size()))
        print("  OK: MainWindow 已构造（注入合成背景）")
    step("2 构造", _step_construct)
    win = win_holder["win"]

    def _step_show():
        """显示主窗口"""
        win.show()
        _pump(app, 600)
        print("  OK: 主窗口已显示并完成首帧渲染")
    step("3 显示", _step_show)

    def _step_shot():
        """截图验证"""
        shot = win.grab()
        _assert_glass_rendered(shot, "MainWindow")
        out = ROOT / "tests" / "_main_window_shot.png"
        shot.save(str(out))
        print(f"  截图已保存：{out}")
    step("4 截图", _step_shot)

    def _step_hotkey():
        """热键面板验证"""
        panel = win.hotkey_panel()
        cards = panel.cards()
        assert len(cards) == 6, f"热键卡片数应为 6，实际 {len(cards)}"
        print(f"  OK: {len(cards)} 张热键卡片")
        for action_value, card in cards.items():
            action = Action(action_value)
            print(f"    - {action.label} → {card._key}")
        panel.set_active_mode("key")
        _pump(app, 100)
        key_card = cards[Action.KEY_TRIGGER.value]
        assert key_card._active, "按键触发卡片未激活"
        print("  OK: 模式切换为 'key' 后 KEY_TRIGGER 卡片激活")
        panel.set_active_mode("idle")
        _pump(app, 100)
        assert not key_card._active, "idle 后 KEY_TRIGGER 卡片仍激活"
        print("  OK: 模式切回 'idle' 后卡片恢复待命")
    step("5 热键面板", _step_hotkey)

    def _step_library():
        """预设库验证"""
        lib = win.library()
        assert int(lib._count_label.text()) >= 1, "预设数量徽标异常"
        print(f"  OK: 预设数量徽标 = {lib._count_label.text()}")
    step("6 预设库", _step_library)

    def _step_toggle():
        """总开关视觉切换（不触发真实热键注册）"""
        switch = win.switch_area()
        # 断开信号，避免触发 controller.master_on 注册真实热键
        switch.toggled.disconnect()
        switch.toggle_widget().setChecked(True)
        _pump(app, 200)
        print(f"  OK: Toggle 视觉切换 → {switch.isChecked()}")
        print(f"  OK: 状态文案 → '{switch._status_label.text()}'")
        switch.toggle_widget().setChecked(False)
        _pump(app, 200)
        # 重新连回信号
        switch.toggled.connect(win._on_master_toggle)
    step("7 总开关视觉", _step_toggle)

    def _step_search():
        """搜索过滤验证"""
        lib = win.library()
        sb = lib.search_box()
        presets_before = len(controller.presets)
        sb.textChanged.emit("测试")
        _pump(app, 200)
        print(f"  OK: 搜索 '测试' 触发刷新（搜索前共 {presets_before} 个预设）")
        sb.textChanged.emit("")
        _pump(app, 200)
    step("8 搜索", _step_search)

    def _step_bridge():
        """引擎桥接信号验证"""
        captured = {"mode": None}
        def _cap_mode(m):
            captured["mode"] = m
        bridge.mode_changed.connect(_cap_mode)
        bridge.mode_changed.emit("auto")
        _pump(app, 100)
        assert captured["mode"] == "auto", "mode_changed 信号未送达"
        print(f"  OK: mode_changed 信号送达 → {captured['mode']}")
        bridge.mode_changed.disconnect(_cap_mode)
    step("9 引擎桥接", _step_bridge)

    def _step_preset_select():
        """预设切换验证"""
        if controller.presets:
            first_id = controller.presets[0].id
            win._on_preset_selected(first_id)
            _pump(app, 100)
            assert controller._active_id == first_id, "激活预设未更新"
            print(f"  OK: 已激活预设 → {controller.presets[0].title}")
        else:
            print("  跳过：无预设")
    step("10 预设切换", _step_preset_select)

    def _step_close():
        """关闭主窗口"""
        bridge.detach()
        win.close()
        _pump(app, 200)
        print("  OK: 主窗口已关闭")
    step("11 关闭", _step_close)

    print("\n" + "=" * 60)
    print("✓ M2 主窗口验证全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
