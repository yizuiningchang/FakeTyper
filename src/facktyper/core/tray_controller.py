"""系统托盘控制器：QSystemTrayIcon + 动态图标 + 右键菜单。

职责：
- 运行时用 ``TrayIconPainter`` 按引擎状态自绘托盘图标（激活/关闭 + 输出模式角标）；
- 右键菜单：显示主窗口 / 切换总开关 / 退出；
- 双击托盘 → ``showRequested`` 信号；
- ``update_state()`` 由引擎桥接信号驱动，刷新图标 + tooltip。

不依赖资源文件，所有图标运行时 QPainter 绘制。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from ..utils.logger import get_logger
from .typing_engine import TypingEngine
from .controller import EngineController
from ..data.config import AppConfig
from ..ui.widgets.tray_backend import TrayIconPainter, TrayIconState

_log = get_logger("tray")


class TrayController(QObject):
    """系统托盘控制器。"""

    # 对外信号
    showRequested = Signal()           # 双击托盘 / 菜单「显示主窗口」
    toggleMasterRequested = Signal()   # 菜单「切换总开关」
    quitRequested = Signal()            # 菜单「退出」

    def __init__(
        self,
        config: AppConfig,
        controller: EngineController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._controller = controller
        self._tray: Optional[QSystemTrayIcon] = None
        self._state = TrayIconState(master_on=False, engine_mode="idle")
        self._build()

    def _build(self) -> None:
        self._tray = QSystemTrayIcon()
        self._tray.setToolTip("FakeTyper Pro")

        if not QSystemTrayIcon.isSystemTrayAvailable():
            _log.warning("系统托盘不可用，托盘功能将降级（菜单仍可用）")

        # 初始图标
        self._refresh_icon()

        # 右键菜单（即使托盘不可用也创建，保证信号链路完整）
        menu = QMenu()
        act_show = QAction("显示主窗口", menu)
        act_show.triggered.connect(self.showRequested.emit)
        menu.addAction(act_show)

        act_toggle = QAction("切换总开关", menu)
        act_toggle.triggered.connect(self.toggleMasterRequested.emit)
        menu.addAction(act_toggle)

        menu.addSeparator()

        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(self.quitRequested.emit)
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)

        # 双击 → 显示主窗口
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.showRequested.emit()

    def _refresh_icon(self) -> None:
        if self._tray is None:
            return
        pm: QPixmap = TrayIconPainter.render(self._state, 32)
        self._tray.setIcon(QIcon(pm))
        # tooltip
        if self._state.master_on:
            mode_label = {
                "idle": "待命",
                "key": "按键模式",
                "auto": "自动模式",
            }.get(self._state.engine_mode, "")
            preset = self._state.preset_title
            tip = f"FakeTyper Pro — 已激活"
            if mode_label:
                tip += f"（{mode_label}）"
            if preset:
                tip += f"\n当前预设：{preset}"
            self._tray.setToolTip(tip)
        else:
            self._tray.setToolTip("FakeTyper Pro — 已关闭")

    # ---------------- 对外接口 ----------------

    def show(self) -> None:
        """显示托盘图标。"""
        if self._tray is not None:
            self._tray.show()
            _log.info("托盘图标已显示")

    def hide(self) -> None:
        """隐藏托盘图标。"""
        if self._tray is not None:
            self._tray.hide()

    def update_state(
        self,
        master_on: Optional[bool] = None,
        engine_mode: Optional[str] = None,
        preset_title: Optional[str] = None,
    ) -> None:
        """更新托盘图标状态。None 表示不改变对应字段。"""
        changed = False
        if master_on is not None and master_on != self._state.master_on:
            self._state = TrayIconState(
                master_on=master_on,
                engine_mode=self._state.engine_mode,
                preset_title=self._state.preset_title,
            )
            changed = True
        if engine_mode is not None and engine_mode != self._state.engine_mode:
            self._state = TrayIconState(
                master_on=self._state.master_on,
                engine_mode=engine_mode,
                preset_title=self._state.preset_title,
            )
            changed = True
        if preset_title is not None and preset_title != self._state.preset_title:
            self._state = TrayIconState(
                master_on=self._state.master_on,
                engine_mode=self._state.engine_mode,
                preset_title=preset_title,
            )
            changed = True
        if changed:
            self._refresh_icon()

    def is_available(self) -> bool:
        """系统托盘是否可用。"""
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show_message(self, title: str, msg: str, msecs: int = 3000) -> None:
        """显示系统通知（托盘气泡）。"""
        if self._tray is not None and self._tray.isVisible():
            self._tray.showMessage(title, msg, QSystemTrayIcon.Information, msecs)
