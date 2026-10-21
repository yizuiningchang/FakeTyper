"""液态波纹动效（spec 5.1 核心交互标识）。

仅在主要可点元素触发：总开关、新建预设主按钮、预设卡片选中、键位胶囊。
波纹形态：从触点向外扩散的圆形光波（半透明白光 + 边缘高光描边），
扩散半径 0 → 元素边界外 8px，时长 400–600ms，ease-out；
释放后波纹继续完成扩散再消散；多次连击波纹叠加互不冲突。
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPointF,
    Property,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient


class Ripple(QObject):
    """单个波纹：触点扩散光波，``progress`` 0→1 由动画驱动。"""

    def __init__(self, origin: QPointF, radius_max: float, host: QObject) -> None:
        super().__init__(host)
        self.origin = QPointF(origin)
        self.radius_max = float(radius_max)
        self._progress = 0.0
        self._host: Optional[QObject] = host
        anim = QPropertyAnimation(self, b"progress", self)
        anim.setDuration(540)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(self._finish)
        anim.start()
        self._anim = anim  # 防 GC

    def _finish(self) -> None:
        host = self._host
        if host is not None and hasattr(host, "_remove_ripple"):
            host._remove_ripple(self)

    @Property(float)
    def progress(self) -> float:  # noqa: D401
        return self._progress

    @progress.setter
    def progress(self, v: float) -> None:
        self._progress = v
        if self._host is not None:
            self._host.update()  # type: ignore[attr-defined]

    def paint(self, painter: QPainter) -> None:
        p = self._progress
        r = p * self.radius_max
        if r < 1.0:
            return
        # 主光波：径向白光，随扩散衰减
        alpha = int(140 * (1.0 - p) ** 1.4)
        if alpha <= 0:
            return
        grad = QRadialGradient(self.origin, r + 2)
        grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
        grad.setColorAt(0.7, QColor(255, 255, 255, int(alpha * 0.35)))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.origin, r, r)
        # 边缘高光描边
        ring_alpha = int(180 * (1.0 - p) ** 1.2)
        if ring_alpha > 0:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, ring_alpha), 1.2))
            painter.drawEllipse(self.origin, r, r)


class RippleHostMixin:
    """混入可点玻璃控件，提供波纹管理。子类在 paintEvent 中调用
    ``self._paint_ripples(painter)`` 绘制。"""

    def _ripple_setup(self) -> None:
        self._ripples: List[Ripple] = []

    def trigger_ripple(self, pos: QPointF) -> None:
        if not hasattr(self, "_ripples"):
            self._ripple_setup()
        rmax = max(self.width(), self.height()) * 1.25 + 8
        self._ripples.append(Ripple(QPointF(pos), rmax, self))

    def _remove_ripple(self, rip: Ripple) -> None:
        try:
            self._ripples.remove(rip)
        except ValueError:
            pass
        self.update()

    def _paint_ripples(self, painter: QPainter) -> None:
        if not getattr(self, "_ripples", None):
            return
        painter.save()
        for rip in list(self._ripples):
            rip.paint(painter)
        painter.restore()
