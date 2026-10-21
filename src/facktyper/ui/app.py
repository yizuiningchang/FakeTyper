"""FakeTyper Pro GUI 入口。

组装各层组件并启动 Qt 事件循环：
- ``SingleInstance`` 单实例守卫（命名互斥体，重复启动唤起已有实例）
- ``TypingEngine`` + ``HotkeyManager`` + ``EngineController`` + ``AppConfig``
- ``EngineBridge`` 适配引擎事件 → Qt 信号
- ``TrayController`` 系统托盘（动态图标 + 右键菜单）
- ``MainWindow`` 液态玻璃主界面
- 全局异常钩子（toast 提示）

启动行为由 ``--minimized`` 参数和 ``config.startup_window_state`` 决定。
关闭按钮行为由 ``config.close_behavior`` 决定（最小化到托盘 / 直接退出）。
"""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from ..core.autostart import sync_to_registry
from ..core.controller import EngineController
from ..core.hotkey_manager import HotkeyManager
from ..core.single_instance import SingleInstance
from ..core.tray_controller import TrayController
from ..core.typing_engine import TypingEngine
from ..data import preset_store
from ..data.config import AppConfig
from ..data.paths import data_root
from ..utils.logger import get_logger, install_excepthook
from . import theme
from .views.main_window import MainWindow
from .widgets.engine_bridge import EngineBridge
from .widgets.toast import show_toast

_log = get_logger("app")


def _detect_system_dark() -> bool:
    """检测系统当前是否深色模式（Windows 读注册表 AppsUseLightTheme）。

    非 Windows 或读取失败时默认 True（深色）。
    """
    if sys.platform != "win32":
        return True
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            value, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        # 1 = 浅色，0 = 深色
        return int(value) == 0
    except Exception:  # noqa: BLE001
        return True


def run_gui(argv: Optional[list[str]] = None) -> int:
    """启动 GUI 主程序。

    Args:
        argv: 命令行参数（None 时取 sys.argv）。支持 ``--minimized`` 启动到托盘。
    """
    if argv is None:
        argv = sys.argv[1:]

    # 1. 单实例守卫
    instance = SingleInstance()
    if not instance.acquire():
        _log.info("已有实例运行，尝试唤起已存在窗口")
        instance.signal_existing()
        return 0

    # 2. 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FakeTyper Pro")
    app.setQuitOnLastWindowClosed(False)  # 关闭主窗口不退出（驻留托盘）

    # 3. 全局异常钩子
    def _on_crash(*_):
        try:
            show_toast(None, "发生异常，已记录日志", kind="error")
        except Exception:
            pass

    install_excepthook(on_crash=_on_crash)

    # 4. 数据层初始化
    preset_store.ensure_default_preset()

    # 5. 组装核心
    config = AppConfig.load()
    # 同步开机自启注册表状态（用户可能在外部修改过）
    sync_to_registry(config.auto_start)

    # 5b. 初始化主题（M3-d）：在 MainWindow 构造前设置，确保所有控件首次绘制即用正确配色
    theme.set_system_dark(_detect_system_dark())
    theme.set_theme(config.theme)
    _log.debug("主题初始化: raw=%s resolved=%s",
               theme.current_theme_raw(), theme.current_theme_resolved())

    hotkey = HotkeyManager()
    engine = TypingEngine(hotkey)
    controller = EngineController(engine, hotkey, config)
    bridge = EngineBridge(engine)

    # 6. 主窗口
    win = MainWindow(engine, controller, config, bridge)

    # 7. 托盘控制器
    tray = TrayController(config, controller, parent=win)
    tray.show()

    # 8. 启动行为
    minimized = "--minimized" in argv
    if minimized or config.startup_window_state == "minimized":
        # 静默启动到托盘，不显示主窗口
        _log.info("静默启动到托盘（--minimized / startup_window_state=minimized）")
    elif config.startup_window_state == "maximized":
        win.showMaximized()
    else:
        win.show()
        # 首启引导：窗口可见且未展示过时弹出（淡入后触发）
        if not config.onboarding_shown:
            QTimer.singleShot(280, win.show_onboarding)

    # 9. 引擎桥接 → 托盘图标状态同步
    def _on_mode_changed(mode: str):
        tray.update_state(engine_mode=mode)

    def _on_preset_changed(title: str, total: int):
        tray.update_state(preset_title=title)

    bridge.mode_changed.connect(_on_mode_changed)
    bridge.preset_changed.connect(_on_preset_changed)

    # 10. 关闭按钮行为
    def _on_close_to_tray():
        if config.close_behavior == "quit":
            # 直接退出
            _quit_app()
        else:
            # 最小化到托盘
            win.hide()
            tray.show_message("FakeTyper Pro", "已最小化到托盘", msecs=2000)

    win.closeToTrayRequested.connect(_on_close_to_tray)

    # 11. 托盘信号
    def _on_tray_show():
        win.show()
        win.raise_()
        win.activateWindow()
        # Windows: 恢复焦点
        if sys.platform == "win32":
            try:
                win.setWindowState(win.windowState() & ~Qt.WindowMinimized)
            except Exception:
                pass

    def _on_tray_toggle_master():
        if config.master_switch:
            controller.master_off()
            show_toast(win, "已关闭", kind="info")
        else:
            ok = controller.master_on()
            if ok:
                show_toast(win, "已激活", kind="success")
            else:
                show_toast(win, "激活失败", kind="error")
        config.save()
        tray.update_state(master_on=config.master_switch)
        win.switch_area().setChecked(config.master_switch)

    def _on_tray_quit():
        _quit_app()

    tray.showRequested.connect(_on_tray_show)
    tray.toggleMasterRequested.connect(_on_tray_toggle_master)
    tray.quitRequested.connect(_on_tray_quit)

    # 12. 主窗口总开关 → 托盘图标更新
    def _on_master_toggled(on: bool):
        tray.update_state(master_on=on)

    win.switch_area().toggled.connect(_on_master_toggled)

    _log.info("FakeTyper Pro GUI 已启动 (数据目录: %s)", data_root())

    # 13. 事件循环
    code = app.exec()

    # 14. 退出清理
    _cleanup(controller, bridge, tray, instance)
    return code


def _quit_app() -> None:
    """退出应用：关闭主窗口 + 退出事件循环。"""
    app = QApplication.instance()
    if app is not None:
        app.quit()


def _cleanup(
    controller: EngineController,
    bridge: EngineBridge,
    tray: TrayController,
    instance: SingleInstance,
) -> None:
    """退出前清理资源。"""
    try:
        bridge.detach()
    except Exception as e:
        _log.exception("bridge.detach 异常: %s", e)
    try:
        tray.hide()
    except Exception:
        pass
    try:
        controller.shutdown()
    except Exception as e:
        _log.exception("controller.shutdown 异常: %s", e)
    try:
        instance.release()
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(run_gui())
