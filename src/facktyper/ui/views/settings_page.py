"""设置中心主页面：左分栏导航 + 右内容堆栈（spec 4.6）。

左 120px 分栏（6 个 ``_NavItem`` 自绘，选中态主色高亮），右 ``QStackedWidget``
承载 6 个分栏面板（``settings_panes``）。分栏切换 120ms 淡入淡出。

对外信号：
- ``closeRequested``：返回 / Esc，请求 pop 回主页
- ``configChanged``：任意设置项变更（触发 controller 重绑热键 / 引擎参数 / 主题）
- ``openDataDirRequested`` / ``exportRequested`` / ``importRequested`` / ``clearRequested``：数据分栏
- ``checkUpdateRequested``：关于分栏检查更新

接口：
- ``load_from_config()``：进入设置页时从 config 灌入各分栏
- ``apply_to_config()``：把各分栏当前值写回 config（就地修改传入的 config）
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.controller import EngineController
from ...data.config import AppConfig
from .. import theme
from ..widgets.glass_button import GlassIconButton
from ..widgets.liquid_glass import GlassContainer
from ..widgets.squircle import squircle_path
from .settings_panes import (
    AboutPane,
    AppearancePane,
    DataPane,
    GeneralPane,
    HotkeysPane,
    TypingPane,
)


def _paint_back_arrow(painter: QPainter, w: int, h: int) -> None:
    painter.setPen(QPen(QColor(242, 243, 251, 230), 1.6, Qt.SolidLine, Qt.RoundCap))
    m = 9
    painter.drawLine(QPointF(w - m, h / 2), QPointF(m, h / 2))
    painter.drawLine(QPointF(m, h / 2), QPointF(m + 6, h / 2 - 6))
    painter.drawLine(QPointF(m, h / 2), QPointF(m + 6, h / 2 + 6))


class _NavItem(QWidget):
    """分栏导航项：自绘，选中态主色高亮条 + 文字。"""

    clicked = Signal(int)

    def __init__(self, idx: int, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._idx = idx
        self._label = label
        self._selected = False
        self._hover = False
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def setSelected(self, on: bool) -> None:
        self._selected = on
        self.update()

    def enterEvent(self, e: QEnterEvent) -> None:
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e: QEvent) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._idx)
        super().mousePressEvent(e)

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(4, 4, w - 8, h - 8)

        # 选中态：主色渐变圆角条
        if self._selected:
            clip = squircle_path(rect, theme.RADIUS_SMALL)
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
            grad.setColorAt(1.0, QColor(theme.current_palette().accent))
            painter.setBrush(grad)
            painter.setPen(Qt.NoPen)
            painter.drawPath(clip)
            text_color = QColor(255, 255, 255, 245)
        elif self._hover:
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.setPen(Qt.NoPen)
            painter.drawPath(squircle_path(rect, theme.RADIUS_SMALL))
            text_color = QColor(theme.current_palette().text)
        else:
            text_color = QColor(theme.current_palette().text_dim)

        painter.setPen(text_color)
        painter.setFont(QFont(theme.FONT_CN, 9, QFont.DemiBold))
        painter.drawText(rect, Qt.AlignCenter, self._label)


class SettingsPage(QWidget):
    """设置中心主容器。"""

    closeRequested = Signal()
    configChanged = Signal()
    openDataDirRequested = Signal()
    exportRequested = Signal()
    importRequested = Signal()
    clearRequested = Signal()
    checkUpdateRequested = Signal()

    def __init__(
        self,
        config: AppConfig,
        controller: EngineController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._config = config
        self._controller = controller
        self._nav_items: list[_NavItem] = []

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # 顶栏：返回 + 标题
        topbar = QWidget(self)
        topbar.setAttribute(Qt.WA_TranslucentBackground, True)
        topbar.setFixedHeight(44)
        th = QHBoxLayout(topbar)
        th.setContentsMargins(4, 4, 4, 4)
        th.setSpacing(8)
        self._back_btn = GlassIconButton(topbar, radius=theme.RADIUS_SMALL)
        self._back_btn.setFixedSize(34, 34)
        self._back_btn.setIconPainter(_paint_back_arrow)
        self._back_btn.clicked.connect(self.closeRequested.emit)
        th.addWidget(self._back_btn)
        self._title = QLabel("设置中心", topbar)
        self._title.setFont(QFont(theme.FONT_CN, 11, QFont.Bold))
        theme.style_text(self._title, "text")
        th.addWidget(self._title)
        th.addStretch(1)
        root.addWidget(topbar)

        # 内容：左分栏 + 右堆栈
        body = QHBoxLayout()
        body.setSpacing(8)
        body.setContentsMargins(0, 0, 0, 0)

        self._nav = GlassContainer(self, radius=theme.RADIUS_CARD)
        nav_lay = QVBoxLayout(self._nav)
        nav_lay.setContentsMargins(6, 10, 6, 10)
        nav_lay.setSpacing(4)
        labels = ["通用", "快捷键", "打字", "外观", "数据", "关于"]
        for i, lbl in enumerate(labels):
            item = _NavItem(i, lbl, self._nav)
            item.clicked.connect(self.select_nav)
            self._nav_items.append(item)
            nav_lay.addWidget(item)
        nav_lay.addStretch(1)
        self._nav.setFixedWidth(96)
        body.addWidget(self._nav, 0)

        self._stack = QStackedWidget(self)
        self._panes = [
            GeneralPane(self._config, self._controller, self._stack),
            HotkeysPane(self._config, self._controller, self._stack),
            TypingPane(self._config, self._controller, self._stack),
            AppearancePane(self._config, self._controller, self._stack),
            DataPane(self._config, self._controller, self._stack),
            AboutPane(self._config, self._controller, self._stack),
        ]
        for pane in self._panes:
            self._stack.addWidget(pane)
            # 转发各分栏的 changed 信号为 SettingsPage.configChanged
            pane.changed.connect(self.configChanged.emit)
        body.addWidget(self._stack, 1)
        root.addLayout(body, 1)

        # 右区淡入效果（必须在 select_nav 之前初始化）
        self._stack_opacity = QGraphicsOpacityEffect(self._stack)
        self._stack_opacity.setOpacity(1.0)
        self._stack.setGraphicsEffect(self._stack_opacity)
        self._fade_anim: Optional[QPropertyAnimation] = None

        # 数据/关于分栏信号转发
        data_pane = self._panes[4]  # type: ignore[assignment]
        data_pane.openDataDirRequested.connect(self.openDataDirRequested.emit)
        data_pane.exportRequested.connect(self.exportRequested.emit)
        data_pane.importRequested.connect(self.importRequested.emit)
        data_pane.clearRequested.connect(self.clearRequested.emit)
        about_pane = self._panes[5]  # type: ignore[assignment]
        about_pane.checkUpdateRequested.connect(self.checkUpdateRequested.emit)

        # 选中第一项（最后调用，依赖前面的 _stack_opacity/_fade_anim）
        self.select_nav(0)

    # ---------------- 导航 ----------------
    def select_nav(self, idx: int) -> None:
        """切换分栏：更新 NavItem 选中态 + 切换 stack + 淡入动画。"""
        for i, item in enumerate(self._nav_items):
            item.setSelected(i == idx)
        self._stack.setCurrentIndex(idx)
        # 120ms 淡入
        if self._fade_anim is not None and self._fade_anim.state() == QPropertyAnimation.Running:
            self._fade_anim.stop()
        a = QPropertyAnimation(self._stack_opacity, b"opacity", self)
        a.setDuration(120)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.start()
        self._fade_anim = a

    # ---------------- 对外接口 ----------------
    def load_from_config(self) -> None:
        for pane in self._panes:
            pane.load()

    def apply_to_config(self) -> None:
        for pane in self._panes:
            pane.apply()

    def hotkeys_pane(self) -> HotkeysPane:
        return self._panes[1]  # type: ignore[return-value]

    def keyPressEvent(self, e) -> None:  # type: ignore[override]
        if e.key() == Qt.Key_Escape:
            self.closeRequested.emit()
        else:
            super().keyPressEvent(e)
