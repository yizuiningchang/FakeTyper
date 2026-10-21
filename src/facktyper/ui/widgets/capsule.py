"""浮动状态胶囊：灵动岛风格（spec 5.3 可选项）。

- 悬浮于屏幕（或父窗口）之上，液态玻璃材质，超椭圆连续形变；
- 显示当前模式（按键/自动）+ 进度百分比 + 进度条；
- 可拖动定位；录屏时可隐藏（``setVisible``）；
- 形变动画：IDLE 收缩为小药丸，输出中展开为带进度条的胶囊。

设计为独立顶层窗口（``Qt.ToolTip`` 级别，无边框、不抢焦点、置顶），
默认贴在屏幕底部居中。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from .. import theme
from .liquid_glass import GlassContainer
from .squircle import squircle_path


# 模式 → 显示文案 + 色彩
_MODE_LABELS = {
    "idle": ("待命", QColor(91, 96, 128)),
    "key": ("按键触发", QColor(124, 111, 240)),
    "auto": ("自动匀速", QColor(45, 212, 191)),
}


class StatusCapsule(GlassContainer):
    """浮动状态胶囊：显示模式 + 进度，可拖动。"""

    # 尺寸
    W_EXPANDED = 240
    H_EXPANDED = 48
    W_COLLAPSED = 120
    H_COLLAPSED = 32

    moved = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_BUTTON)
        self._mode = "idle"
        self._percent = 0.0
        self._expanded = False
        self._w = self.W_COLLAPSED
        self._h = self.H_COLLAPSED
        self._drag_offset: Optional[QPoint] = None
        self._size_anim: Optional[QVariantAnimation] = None
        self._expand = 0.0

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._apply_size()
        self.setMouseTracking(True)

    def _apply_size(self) -> None:
        """根据 _expand 插值计算并设置尺寸。"""
        self._w = self.W_COLLAPSED + (self.W_EXPANDED - self.W_COLLAPSED) * self._expand
        self._h = self.H_COLLAPSED + (self.H_EXPANDED - self.H_COLLAPSED) * self._expand
        self.setFixedSize(int(self._w), int(self._h))

    @property
    def expand(self) -> float:
        return self._expand

    # ---- 状态 ----
    def set_mode(self, mode: str) -> None:
        self._mode = mode if mode in _MODE_LABELS else "idle"
        target_expand = 0.0 if self._mode == "idle" else 1.0
        self._animate_expand(target_expand)
        if self._mode == "idle":
            self._percent = 0.0
        self.update()

    def set_progress(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self.update()

    def _animate_expand(self, target: float) -> None:
        if self._size_anim is not None:
            self._size_anim.stop()
        cur = self._expand
        if abs(cur - target) < 0.01:
            self._expand = target
            self._apply_size()
            self.update()
            return
        a = QVariantAnimation(self)
        a.setDuration(360)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.setStartValue(cur)
        a.setEndValue(target)
        a.valueChanged.connect(self._on_expand_value)
        a.start()
        self._size_anim = a

    def _on_expand_value(self, v) -> None:
        self._expand = float(v)
        self._apply_size()
        self.update()

    # ---- 拖动 ----
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset is not None and e.buttons() & Qt.LeftButton:
            new_pos = e.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)
            self.moved.emit(self.pos())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(e)

    # ---- 定位 ----
    def attach_bottom_center(self, screen=None) -> None:
        """贴在屏幕底部居中。"""
        if screen is None:
            screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.center().x() - int(self._w) // 2
        y = geo.bottom() - int(self._h) - 24
        self.move(x, y)

    # ---- 绘制 ----
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(0, 0, w, h)
        clip = squircle_path(rect, self._radius)
        painter.setClipPath(clip)

        # 玻璃底
        bd = self._resolve_backdrop()
        if bd is not None and not bd.isNull():
            painter.drawPixmap(QPointF(0, 0), bd)

        # 染色
        _, mode_color = _MODE_LABELS.get(self._mode, _MODE_LABELS["idle"])
        painter.fillRect(rect, QColor(20, 20, 38, 210))

        # 模式色晕
        glow = QLinearGradient(QPointF(0, 0), QPointF(w, 0))
        glow.setColorAt(0.0, QColor(mode_color.red(), mode_color.green(), mode_color.blue(), 60))
        glow.setColorAt(0.5, QColor(mode_color.red(), mode_color.green(), mode_color.blue(), 20))
        glow.setColorAt(1.0, QColor(mode_color.red(), mode_color.green(), mode_color.blue(), 60))
        painter.fillRect(rect, glow)

        # 顶光带
        top = QLinearGradient(0, 0, 0, h * 0.5)
        top.setColorAt(0.0, QColor(255, 255, 255, 70))
        top.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.5), top)

        painter.setClipping(False)
        # 边缘
        pen = QPen(QColor(255, 255, 255, 60), 1.0)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPath(squircle_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), max(self._radius - 0.5, 1)))

        # 内容
        self._paint_content(painter, w, h, mode_color)

    def _paint_content(self, painter: QPainter, w: float, h: float, mode_color: QColor) -> None:
        label, _ = _MODE_LABELS.get(self._mode, _MODE_LABELS["idle"])

        if self._mode == "idle":
            # 收缩态：仅显示小圆点 + 文案
            painter.setBrush(mode_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(w * 0.22, h / 2), 3.5, 3.5)
            font = QFont(theme.FONT_CN, 8, QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(220, 222, 235, 230))
            painter.drawText(QRectF(w * 0.32, 0, w * 0.65, h), Qt.AlignLeft | Qt.AlignVCenter, label)
            return

        # 展开态：模式 + 百分比 + 进度条
        font = QFont(theme.FONT_CN, 8, QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(240, 242, 250, 245))
        painter.drawText(QRectF(14, 0, w * 0.5, h), Qt.AlignLeft | Qt.AlignVCenter, label)

        # 百分比
        pct_font = QFont(theme.FONT_EN, 8, QFont.Bold)
        painter.setFont(pct_font)
        painter.setPen(QColor(mode_color.red(), mode_color.green(), mode_color.blue(), 240))
        painter.drawText(QRectF(w * 0.5, 0, w * 0.5 - 14, h),
                        Qt.AlignRight | Qt.AlignVCenter, f"{self._percent:.0f}%")

        # 进度条（底部细条）
        bar_y = h - 6
        bar_h = 3.0
        bar_rect = QRectF(14, bar_y, w - 28, bar_h)
        painter.setBrush(QColor(255, 255, 255, 35))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)
        fill_w = (w - 28) * (self._percent / 100.0)
        if fill_w > 1:
            painter.setBrush(mode_color)
            painter.drawRoundedRect(QRectF(14, bar_y, fill_w, bar_h), bar_h / 2, bar_h / 2)
