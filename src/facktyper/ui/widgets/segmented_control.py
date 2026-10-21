"""iOS 风格分段选择器。

N 个等宽段，选中段主色填充 + 顶光，滑块用 ``QPropertyAnimation`` 平滑滑动。
信号 ``currentChanged(int)`` 在切换段时发射。

用法::

    seg = SegmentedControl(["深色", "浅色", "跟随系统"])
    seg.currentChanged.connect(lambda i: ...)
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QPointF,
    QRectF,
    Qt,
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
)
from PySide6.QtWidgets import QWidget

from .. import theme
from .liquid_glass import GlassContainer
from .ripple import RippleHostMixin
from .squircle import squircle_path


class SegmentedControl(RippleHostMixin, GlassContainer):
    """分段选择器。"""

    currentChanged = Signal(int)

    def __init__(self, labels: list[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_BUTTON)
        self._ripple_setup()
        self._labels = list(labels)
        self._n = max(1, len(self._labels))
        self._current = 0
        self._slider = 0.0  # 滑块位置 0..n-1
        self._slider_anim: Optional[QPropertyAnimation] = None
        self._hover_idx = -1

        self.setFixedHeight(36)
        self.setMinimumWidth(44 * self._n)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    from PySide6.QtCore import Property

    def _get_slider(self) -> float:
        return self._slider

    def _set_slider(self, v: float) -> None:
        self._slider = v
        self.update()

    sliderPos = Property(float, _get_slider, _set_slider)

    # ---- 状态 ----
    def currentIndex(self) -> int:
        return self._current

    def setCurrentIndex(self, idx: int, animate: bool = True) -> None:
        idx = max(0, min(self._n - 1, idx))
        if idx == self._current:
            return
        self._current = idx
        target = float(idx)
        if self._slider_anim is not None and self._slider_anim.state() == QPropertyAnimation.Running:
            self._slider_anim.stop()
        if not animate:
            self._slider = target
            self.update()
        else:
            a = QPropertyAnimation(self, b"sliderPos", self)
            a.setDuration(200)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.setStartValue(self._slider)
            a.setEndValue(target)
            a.start()
            self._slider_anim = a
        self.currentChanged.emit(idx)

    def _seg_rect(self, i: int) -> QRectF:
        w = self.width() / self._n
        return QRectF(i * w, 0, w, self.height())

    # ---- 事件 ----
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton and self.width():
            i = int(e.position().x() / (self.width() / self._n))
            i = max(0, min(self._n - 1, i))
            self.trigger_ripple(e.position())
            if i != self._current:
                self.setCurrentIndex(i)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self.width():
            i = int(e.position().x() / (self.width() / self._n))
        else:
            i = -1
        i = max(-1, min(self._n - 1, i))
        if i != self._hover_idx:
            self._hover_idx = i
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e: QEnterEvent) -> None:
        self._hover_idx = -1
        self.update()
        super().leaveEvent(e)

    # ---- 绘制 ----
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(0, 0, w, h)
        clip = squircle_path(rect, self._radius)
        painter.setClipPath(clip)

        # 玻璃底
        bd = self._resolve_backdrop()
        if bd is not None and not bd.isNull():
            painter.drawPixmap(0, 0, bd)

        # 滑块（选中段主色填充）
        seg_w = w / self._n
        sx = self._slider * seg_w
        srect = QRectF(sx + 2, 2, seg_w - 4, h - 4)
        sclip = squircle_path(srect, max(2.0, self._radius - 2))
        grad = QLinearGradient(srect.topLeft(), srect.bottomLeft())
        grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
        grad.setColorAt(1.0, QColor(theme.current_palette().accent))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawPath(sclip)
        # 滑块顶光
        tg = QLinearGradient(srect.topLeft(), QPointF(srect.left(), srect.center().y()))
        tg.setColorAt(0.0, QColor(255, 255, 255, 80))
        tg.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(tg)
        painter.setPen(Qt.NoPen)
        painter.drawPath(sclip)

        # 文字
        painter.setClipping(False)
        painter.setClipPath(clip)
        painter.setFont(QFont(theme.FONT_CN, 8, QFont.DemiBold))
        for i, lbl in enumerate(self._labels):
            sr = self._seg_rect(i)
            if i == self._current:
                painter.setPen(QColor(255, 255, 255, 245))
            elif i == self._hover_idx:
                painter.setPen(QColor(theme.current_palette().text))
            else:
                painter.setPen(QColor(theme.current_palette().text_dim))
            painter.drawText(sr, Qt.AlignCenter, lbl)

        # 波纹
        self._paint_ripples(painter)
        painter.setClipping(False)
        self._paint_edge(painter, rect)
