"""M3-b 设置中心验证脚本。

验证项：
1. 各模块可导入（settings_page / settings_panes / 4 个新控件）；
2. SettingsPage 可独立构造并展示（6 个分栏）；
3. 导航点击切换分栏 + 淡入动画无异常；
4. load_from_config / apply_to_config 双向同步正确；
5. 各分栏控件渲染（SegmentedControl / SliderWithLabel / SettingRow / MiniToggle）；
6. ConflictDialog 弹出 / accepted / rejected 信号；
7. MainWindow 接入：设置按钮 → push 设置页 → Esc → pop 回主页；
8. 设置变更 → configChanged 信号 → 实时写回 config；
9. 截图验证液态玻璃渲染无黑边。

运行：``python tests/render_settings_page.py``
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import faulthandler  # noqa: E402
_fault_log = open(str(Path(__file__).parent / "_m3b_fault.log"), "w")
faulthandler.enable(file=_fault_log, all_threads=True)

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from facktyper.core.controller import EngineController  # noqa: E402
from facktyper.core.hotkey_manager import HotkeyManager  # noqa: E402
from facktyper.core.typing_engine import TypingEngine  # noqa: E402
from facktyper.data import preset_store  # noqa: E402
from facktyper.data.config import AppConfig  # noqa: E402
from facktyper.data.constants import Action  # noqa: E402
from facktyper.ui.views.main_window import MainWindow  # noqa: E402
from facktyper.ui.views.settings_page import SettingsPage  # noqa: E402
from facktyper.ui.views.settings_panes import (  # noqa: E402
    AboutPane,
    AppearancePane,
    DataPane,
    GeneralPane,
    HotkeysPane,
    TypingPane,
)
from facktyper.ui.widgets.conflict_dialog import ConflictDialog  # noqa: E402
from facktyper.ui.widgets.engine_bridge import EngineBridge  # noqa: E402
from facktyper.ui.widgets.liquid_glass import make_synthetic_backdrop  # noqa: E402
from facktyper.ui.widgets.segmented_control import SegmentedControl  # noqa: E402
from facktyper.ui.widgets.setting_row import SettingRow  # noqa: E402
from facktyper.ui.widgets.slider_with_label import SliderWithLabel  # noqa: E402


def _pump(app: QApplication, ms: int) -> None:
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def _assert_rendered(pm: QPixmap, name: str, threshold: float = 0.4) -> None:
    assert not pm.isNull(), f"{name} 截图为空"
    img = pm.toImage()
    w, h = img.width(), img.height()
    non_empty = 0
    sample = 0
    for y in range(0, h, max(1, h // 40)):
        for x in range(0, w, max(1, w // 40)):
            sample += 1
            px = img.pixel(x, y)
            a = (px >> 24) & 0xFF
            v = ((px >> 16) & 0xFF) + ((px >> 8) & 0xFF) + (px & 0xFF)
            if a > 30 and v > 40:
                non_empty += 1
    ratio = non_empty / max(1, sample)
    print(f"  {name}: 有效像素占比 {ratio:.0%}")
    assert ratio > threshold, f"{name} 渲染异常：有效像素占比过低 ({ratio:.0%})"


def main() -> int:
    print("=" * 60)
    print("FakeTyper Pro M3-b 设置中心验证")
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
        print("  OK: SettingsPage / 6 个 Pane / 4 个新控件 已导入")
    step("1 导入", _step_import)

    # 数据准备
    preset_store.ensure_default_preset()
    config = AppConfig.load()
    hotkey = HotkeyManager()
    engine = TypingEngine(hotkey)
    controller = EngineController(engine, hotkey, config)
    bridge = EngineBridge(engine)

    app = QApplication.instance() or QApplication(sys.argv)

    # 2. 独立构造 SettingsPage（用普通 QWidget 宿主，GlassContainer 子项用染底渲染）
    sp_holder: dict = {}
    def _step_construct():
        """独立构造 SettingsPage"""
        host = QWidget()
        host.resize(720, 560)
        sp = SettingsPage(config, controller, host)
        sp.setGeometry(host.rect())
        host.show()
        _pump(app, 300)
        sp_holder["sp"] = sp
        sp_holder["host"] = host
        print(f"  OK: SettingsPage 已构造（{len(sp._panes)} 个分栏）")
    step("2 构造", _step_construct)
    sp = sp_holder["sp"]
    host = sp_holder["host"]

    # 3. 导航切换
    def _step_nav():
        """导航点击切换分栏"""
        labels = ["通用", "快捷键", "打字", "外观", "数据", "关于"]
        for i, lbl in enumerate(labels):
            sp.select_nav(i)
            _pump(app, 180)
            cur = sp._stack.currentIndex()
            assert cur == i, f"点击 {lbl} 后 stack currentIndex={cur} ≠ {i}"
            assert sp._nav_items[i]._selected, f"{lbl} NavItem 未选中"
            print(f"  OK: 切换到「{lbl}」(stack idx={cur})")
    step("3 导航切换", _step_nav)

    # 4. load_from_config / apply_to_config 双向同步
    def _step_roundtrip():
        """load → apply 双向同步"""
        sp.load_from_config()
        # 记录 load 后的值
        general: GeneralPane = sp._panes[0]
        s_idx_before = general._startup_seg.currentIndex()
        typing: TypingPane = sp._panes[2]
        speed_before = typing._speed_sld.value()
        # 修改 UI 值
        general._startup_seg.setCurrentIndex(2)  # 最大化
        typing._speed_sld.setValue(500)
        # apply 写回 config
        sp.apply_to_config()
        assert config.startup_window_state == "maximized", config.startup_window_state
        assert config.auto_speed_ms == 500, config.auto_speed_ms
        print(f"  OK: 启动状态 → {config.startup_window_state}")
        print(f"  OK: 自动速度 → {config.auto_speed_ms}ms")
        # 恢复原值（避免污染后续测试）
        general._startup_seg.setCurrentIndex(s_idx_before)
        typing._speed_sld.setValue(speed_before)
        sp.apply_to_config()
    step("4 双向同步", _step_roundtrip)

    # 5. 各分栏控件渲染
    def _step_panes_render():
        """6 个分栏分别截图"""
        for i, name in enumerate(["通用", "快捷键", "打字", "外观", "数据", "关于"]):
            sp.select_nav(i)
            _pump(app, 200)
            pm = sp.grab()
            # 外观/关于分栏内容稀疏，降低阈值
            thr = 0.15 if name in ("外观", "关于") else 0.3
            _assert_rendered(pm, f"Pane[{name}]", threshold=thr)
            out = ROOT / "tests" / f"_settings_pane_{i}_{name}.png"
            pm.save(str(out))
        print("  OK: 6 个分栏全部渲染")
    step("5 分栏渲染", _step_panes_render)

    # 6. 通用分栏：开机自启 toggle
    def _step_autostart():
        """通用分栏：开机自启 toggle"""
        sp.select_nav(0)
        _pump(app, 100)
        general: GeneralPane = sp._panes[0]
        orig = config.auto_start
        # 不真正写注册表：直接调 _on_autostart 的逻辑但 mock autostart.sync_to_registry
        from facktyper.core import autostart
        orig_sync = autostart.sync_to_registry
        autostart.sync_to_registry = lambda on: True  # type: ignore
        try:
            general._autostart_tg.setChecked(not orig, animate=False)
            _pump(app, 100)
            assert config.auto_start == (not orig), "auto_start 未同步"
            print(f"  OK: 开机自启 toggle → {config.auto_start}")
            # 恢复
            general._autostart_tg.setChecked(orig, animate=False)
            _pump(app, 100)
            assert config.auto_start == orig
        finally:
            autostart.sync_to_registry = orig_sync  # type: ignore
    step("6 通用-自启", _step_autostart)

    # 7. 打字分栏：滑块 + 分段 + toggle 联动
    def _step_typing():
        """打字分栏：滑块/分段/toggle 联动"""
        sp.select_nav(2)
        _pump(app, 100)
        typing: TypingPane = sp._panes[2]
        # 关闭人性化抖动 → 抖动幅度滑块应禁用
        orig_jitter = typing._jitter_tg.isChecked()
        typing._jitter_tg.setChecked(False, animate=False)
        _pump(app, 100)
        assert not typing._jamount_sld._slider.isEnabled(), "抖动关闭后幅度滑块应禁用"
        typing._jitter_tg.setChecked(True, animate=False)
        _pump(app, 100)
        assert typing._jamount_sld._slider.isEnabled(), "抖动开启后幅度滑块应启用"
        print("  OK: 抖动 toggle 联动滑块启用/禁用")
        # 改字符数分段
        typing._cpk_seg.setCurrentIndex(3)  # 4 字符
        _pump(app, 100)
        sp.apply_to_config()
        assert config.chars_per_keypress == 4, config.chars_per_keypress
        print(f"  OK: 每按键字符数 → {config.chars_per_keypress}")
        # 恢复
        typing._cpk_seg.setCurrentIndex(orig_jitter and 0 or 0)
        typing._jitter_tg.setChecked(orig_jitter, animate=False)
    step("7 打字联动", _step_typing)

    # 8. 快捷键分栏：录制 + 冲突交换 + 恢复默认
    def _step_hotkeys_reset():
        """快捷键分栏：KeyCapButton 录制 + 冲突交换 + 恢复默认"""
        sp.select_nav(1)
        _pump(app, 100)
        hk: HotkeysPane = sp._panes[1]
        # 验证 6 个 KeyCapButton
        assert len(hk._cap_buttons) == 6, f"KeyCapButton 数 {len(hk._cap_buttons)} ≠ 6"
        for action, btn in zip(Action, hk._cap_buttons):
            txt = btn.key()
            assert txt, f"{action.label} 键位为空"
            print(f"    - {action.label} → {txt}")

        # 录制：点击第 0 个（KEY_TRIGGER，当前 F1）→ 录制态 → 按 F3
        # F3 当前绑定 AUTO，应自动交换
        orig_map = dict(config.hotkey_map)
        btn0 = hk._cap_buttons[0]
        assert btn0.key() == "F1"
        # 模拟点击进入录制态
        btn0.setRecording(True)
        _pump(app, 200)
        assert btn0.isRecording(), "KeyCapButton 未进入录制态"
        # 模拟按 F3 键
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        app.postEvent(btn0, QKeyEvent(QEvent.KeyPress, Qt.Key_F3, Qt.NoModifier))
        _pump(app, 300)
        # 验证：KEY_TRIGGER → F3, AUTO → F1（交换）
        assert config.hotkey_map[Action.KEY_TRIGGER.value] == "F3", \
            f"KEY_TRIGGER 应为 F3，实际 {config.hotkey_map[Action.KEY_TRIGGER.value]}"
        assert config.hotkey_map[Action.AUTO.value] == "F1", \
            f"AUTO 应交换为 F1，实际 {config.hotkey_map[Action.AUTO.value]}"
        assert btn0.key() == "F3"
        assert hk._cap_buttons[2].key() == "F1"  # AUTO 的按钮也刷新
        print("  OK: 录制 F3 → KEY_TRIGGER↔AUTO 自动交换")

        # 录制：点击第 1 个（STOP，当前 F2）→ 按 Esc 取消
        btn1 = hk._cap_buttons[1]
        assert btn1.key() == "F2"
        btn1.setRecording(True)
        _pump(app, 200)
        app.postEvent(btn1, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        _pump(app, 200)
        assert not btn1.isRecording(), "Esc 后应退出录制态"
        assert btn1.key() == "F2", "取消后键位应不变"
        print("  OK: Esc 取消录制，键位不变")

        # 恢复默认
        hk._on_reset()
        _pump(app, 100)
        from facktyper.data.constants import default_hotkey_map
        assert config.hotkey_map == default_hotkey_map(), "恢复默认后映射不一致"
        assert hk._cap_buttons[0].key() == "F1"
        print("  OK: 恢复默认映射正确")
        # 清理：恢复原映射
        config.hotkey_map = orig_map
        hk.load()
    step("8 快捷键录制", _step_hotkeys_reset)

    # 9. 外观分栏：主题切换
    def _step_appearance():
        """外观分栏：主题分段"""
        sp.select_nav(3)
        _pump(app, 100)
        app_pane: AppearancePane = sp._panes[3]
        app_pane._theme_seg.setCurrentIndex(1)  # 浅色
        _pump(app, 100)
        sp.apply_to_config()
        assert config.theme == "light", config.theme
        app_pane._theme_seg.setCurrentIndex(0)  # 深色
        _pump(app, 100)
        sp.apply_to_config()
        assert config.theme == "dark"
        print("  OK: 主题切换 dark↔light 写回 config")
    step("9 外观-主题", _step_appearance)

    # 10. 数据分栏：信号转发
    def _step_data_signals():
        """数据分栏：4 个按钮信号转发"""
        sp.select_nav(4)
        _pump(app, 100)
        data: DataPane = sp._panes[4]
        captured = {"a": 0, "b": 0, "c": 0, "d": 0}
        sp.openDataDirRequested.connect(lambda: captured.__setitem__("a", 1))
        sp.exportRequested.connect(lambda: captured.__setitem__("b", 1))
        sp.importRequested.connect(lambda: captured.__setitem__("c", 1))
        sp.clearRequested.connect(lambda: captured.__setitem__("d", 1))
        data._open_dir_btn.clicked.emit()
        data._export_btn.clicked.emit()
        data._import_btn.clicked.emit()
        data._clear_btn.clicked.emit()
        _pump(app, 100)
        assert captured == {"a": 1, "b": 1, "c": 1, "d": 1}, captured
        print("  OK: 4 个数据按钮信号全部转发到 SettingsPage")
    step("10 数据-信号", _step_data_signals)

    # 11. 关于分栏：版本号 + 检查更新
    def _step_about():
        """关于分栏：版本号显示"""
        sp.select_nav(5)
        _pump(app, 100)
        about: AboutPane = sp._panes[5]
        assert "FakeTyper" in about._name_lbl.text()
        assert "版本" in about._ver_lbl.text()
        print(f"  OK: {about._name_lbl.text()} / {about._ver_lbl.text()}")
        captured = {"u": 0}
        sp.checkUpdateRequested.connect(lambda: captured.__setitem__("u", 1))
        about._check_btn.clicked.emit()
        _pump(app, 100)
        assert captured["u"] == 1
        print("  OK: 检查更新信号已转发")
    step("11 关于", _step_about)

    # 12. configChanged 信号
    def _step_changed_signal():
        """configChanged 信号触发"""
        captured = {"n": 0}
        sp.configChanged.connect(lambda: captured.__setitem__("n", captured["n"] + 1))
        sp.select_nav(0)
        _pump(app, 100)
        general: GeneralPane = sp._panes[0]
        general._close_seg.setCurrentIndex(1)  # 直接退出
        _pump(app, 200)
        assert captured["n"] >= 1, f"configChanged 未触发 (n={captured['n']})"
        print(f"  OK: configChanged 触发 {captured['n']} 次")
        # 恢复
        general._close_seg.setCurrentIndex(0)
        _pump(app, 100)
    step("12 configChanged", _step_changed_signal)

    # 13. Esc 关闭信号
    def _step_esc():
        """Esc 触发 closeRequested"""
        captured = {"c": 0}
        sp.closeRequested.connect(lambda: captured.__setitem__("c", 1))
        sp.setFocus(Qt.OtherFocusReason)
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        app.postEvent(sp, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        _pump(app, 200)
        assert captured["c"] == 1, "Esc 未触发 closeRequested"
        print("  OK: Esc → closeRequested")
    step("13 Esc 关闭", _step_esc)

    # 14. ConflictDialog
    def _step_conflict():
        """ConflictDialog 弹出 + accepted/rejected"""
        accepted = {"a": 0}
        rejected = {"r": 0}
        dlg = ConflictDialog(sp, title="键位冲突",
                            desc="F1 已被占用，是否交换？",
                            primary="交换", secondary="取消")
        dlg.accepted.connect(lambda: accepted.__setitem__("a", 1))
        dlg.rejected.connect(lambda: rejected.__setitem__("r", 1))
        dlg.exec_modal()
        _pump(app, 200)
        assert dlg.isVisible(), "对话框未显示"
        dlg._primary_btn.clicked.emit()
        _pump(app, 200)
        assert accepted["a"] == 1, "accepted 未触发"
        assert not dlg.isVisible(), "accepted 后对话框未关闭"
        print("  OK: ConflictDialog accepted 信号")

        # rejected 路径
        dlg2 = ConflictDialog(sp, title="清空确认",
                              desc="将清空全部预设（已备份）",
                              primary="清空", secondary="取消")
        rej = {"r": 0}
        dlg2.rejected.connect(lambda: rej.__setitem__("r", 1))
        dlg2.exec_modal()
        _pump(app, 200)
        dlg2._secondary_btn.clicked.emit()
        _pump(app, 200)
        assert rej["r"] == 1
        print("  OK: ConflictDialog rejected 信号")
    step("14 ConflictDialog", _step_conflict)

    # 15. 单独控件渲染
    def _step_widgets():
        """4 个新控件独立渲染"""
        host2 = QWidget()
        host2.resize(400, 240)
        host2.show()
        _pump(app, 100)

        seg = SegmentedControl(["A", "B", "C"], host2)
        seg.move(20, 20)
        seg.show()
        _pump(app, 100)
        sld = SliderWithLabel(0, 100, 50, unit="%", step=5, parent=host2)
        sld.move(20, 80)
        sld.show()
        _pump(app, 100)
        row = SettingRow("测试行", "描述文本", seg, host2)
        row.move(20, 140)
        row.resize(360, 60)
        row.show()
        _pump(app, 200)
        pm = host2.grab()
        _assert_rendered(pm, "独立控件", threshold=0.3)
        # 切换分段验证滑块动画
        seg.setCurrentIndex(2)
        _pump(app, 300)
        assert seg.currentIndex() == 2
        print("  OK: SegmentedControl / SliderWithLabel / SettingRow 渲染")
        host2.close()
    step("15 独立控件", _step_widgets)

    # 16. MainWindow 集成：push 设置页
    mw_holder: dict = {}
    def _step_mainwindow():
        """MainWindow 集成：设置按钮 → push → pop"""
        # 重置 config 避免污染
        config.save()
        win = MainWindow(engine, controller, config, bridge)
        win.set_synthetic_backdrop(make_synthetic_backdrop(win.size()))
        win.show()
        _pump(app, 600)
        mw_holder["win"] = win
        # 验证主页在栈顶
        assert len(win._page_stack) == 1, f"初始栈深 {len(win._page_stack)} ≠ 1"
        assert win._page_stack[-1] is win._main_page
        print("  OK: MainWindow 初始栈深=1（主页）")

        # 触发设置按钮
        win._settings_btn.clicked.emit()
        _pump(app, 400)  # push 动画 260ms
        assert len(win._page_stack) == 2, f"push 后栈深 {len(win._page_stack)} ≠ 2"
        assert win._page_stack[-1] is win._settings_page, "栈顶非设置页"
        assert win._settings_page is not None
        assert win._settings_page.isVisible(), "设置页不可见"
        print("  OK: 设置按钮 → push 设置页（栈深=2）")

        # 截图
        pm = win.grab()
        _assert_rendered(pm, "MainWindow+Settings", threshold=0.4)
        pm.save(str(ROOT / "tests" / "_settings_pushed_shot.png"))
        print("  OK: 设置页 push 后截图已保存")

        # Esc → closeRequested → _on_settings_close → pop
        win._settings_page.setFocus(Qt.OtherFocusReason)
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        app.postEvent(win._settings_page, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        _pump(app, 500)  # pop 动画 260ms
        assert len(win._page_stack) == 1, f"pop 后栈深 {len(win._page_stack)} ≠ 1"
        assert win._page_stack[-1] is win._main_page, "pop 后栈顶非主页"
        print("  OK: Esc → pop 回主页（栈深=1）")
    step("16 MainWindow集成", _step_mainwindow)

    # 17. 关闭清理
    def _step_cleanup():
        """关闭所有窗口"""
        if "win" in mw_holder:
            bridge.detach()
            mw_holder["win"].close()
        if host is not None:
            host.close()
        _pump(app, 200)
        print("  OK: 全部关闭")
    step("17 清理", _step_cleanup)

    print("\n" + "=" * 60)
    print("✓ M3-b 设置中心验证全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
