"""液态玻璃按钮 + 键位胶囊。

- ``GlassButton``：主按钮（如「＋ 新建预设」），主色填充、超椭圆 10、
  按下波纹 + 轻微缩放；三态（常态/悬停/按下）。
- ``GlassIconButton``：小尺寸图标按钮（顶栏最小化/关闭、设置齿轮等），
  超椭圆 8。
- ``KeyCap``：F1–F6 键位胶囊，按下触发波纹。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QEnterEvent
from PySide6.QtWidgets import QWidget

from .. import theme
from .liquid_glass import GlassContainer
from .ripple import RippleHostMixin
from .squircle import squircle_path


class GlassButton(RippleHostMixin, GlassContainer):
    """主按钮：玻璃底 + 主色填充 + 文案 + 波纹 + 按压缩放。"""

    clicked = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        text: str = "",
        radius: float = theme.RADIUS_BUTTON,
        accent: bool = True,
    ) -> None:
        super().__init__(parent, radius=radius)
        self._ripple_setup()
        self._scale = 1.0
        self._scale_anim: Optional[QPropertyAnimation] = None
        self._text = text
        self._accent = accent
        self._hover = False
        self._pressed = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    # Qt 属性 scaleFactor（按压缩放动画）
    from PySide6.QtCore import Property

    def _get_scale(self) -> float:
        return self._scale

    def _set_scale(self, v: float) -> None:
        self._scale = v
        self.update()

    scaleFactor = Property(float, _get_scale, _set_scale)

    def setText(self, t: str) -> None:
        self._text = t
        self.update()

    def setAccent(self, on: bool) -> None:
        self._accent = on
        self.update()

    # ---- 事件 ----
    def enterEvent(self, e: QEnterEvent) -> None:
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e: QEvent) -> None:
        self._hover = False
        self._mouse_pos = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self._animate_scale(0.96, 140)
            self.trigger_ripple(e.position())
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self._animate_scale(1.0, 240)
            self.update()
            if self.rect().contains(e.position().toPoint()):
                self.clicked.emit()
        super().mouseReleaseEvent(e)

    def _animate_scale(self, target: float, duration: int) -> None:
        if self._scale_anim is not None:
            self._scale_anim.stop()
        a = QPropertyAnimation(self, b"scaleFactor", self)
        a.setDuration(duration)
        a.setEasingCurve(QEasingCurve.OutBack if target >= 1.0 else QEasingCurve.OutCubic)
        a.setStartValue(self._scale)
        a.setEndValue(target)
        a.start()
        self._scale_anim = a

    # ---- 绘制 ----
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()
        rect = QPointF(0, 0)
        # 缩放变换（围绕中心）
        from PySide6.QtCore import QRectF

        clip = squircle_path(QRectF(0, 0, w, h), self._radius)
        painter.setClipPath(clip)
        # 内容缩放
        cx, cy = w / 2.0, h / 2.0
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)

        # 玻璃底
        self._paint_glass_base(painter, QRectF(0, 0, w, h))
        # 主色填充（accent 时）
        if self._accent:
            from PySide6.QtGui import QLinearGradient
            grad = QLinearGradient(QPointF(0, 0), QPointF(0, h))
            a = 220 if not self._pressed else 255
            grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
            grad.setColorAt(1.0, QColor(theme.current_palette().accent))
            painter.fillRect(QRectF(0, 0, w, h), grad)
        # hover 柔光晕
        if self._hover and not self._pressed:
            from PySide6.QtGui import QRadialGradient
            g = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.7)
            c = QColor(255, 255, 255, 40)
            g.setColorAt(0.0, c)
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(QRectF(0, 0, w, h), g)
        # 波纹
        self._paint_ripples(painter)
        # 文案
        painter.setClipping(False)
        self._paint_text(painter, w, h)

    def _paint_glass_base(self, painter: QPainter, rect) -> None:
        # 复用玻璃材质的简化版：染底 + 顶光 + 边缘
        from PySide6.QtGui import QColor, QLinearGradient
        from PySide6.QtCore import QRectF, QPointF
        from .. import theme as T
        tint = QColor(T.DARK.card_tint)
        tint.setAlpha(120)
        painter.fillRect(rect, tint)
        # 顶光带
        grad = QLinearGradient(QPointF(rect.left(), rect.top()), QPointF(rect.left(), rect.top() + rect.height() * 0.5))
        grad.setColorAt(0.0, QColor(255, 255, 255, T.GLASS_TOP_HIGHLIGHT_ALPHA))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), min(rect.height() * 0.18, 12)), grad)

    def _paint_text(self, painter: QPainter, w: int, h: int) -> None:
        if not self._text:
            return
        from PySide6.QtGui import QFont
        font = QFont(theme.FONT_CN, 10, QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 240) if self._accent else QColor(theme.current_palette().text))
        painter.drawText(
            0, 0, w, h,
            Qt.AlignCenter,
            self._text,
        )


class GlassIconButton(GlassContainer):
    """小图标按钮（超椭圆 8）。``icon_painter`` 注入绘制回调。"""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None, *, radius: float = theme.RADIUS_SMALL):
        super().__init__(parent, radius=radius)
        self._hover = False
        self._pressed = False
        self._icon_painter = None
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def setIconPainter(self, fn) -> None:
        self._icon_painter = fn
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._mouse_pos = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(e.position().toPoint()):
                self.clicked.emit()
        super().mouseReleaseEvent(e)

    def paintEvent(self, e: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        from PySide6.QtCore import QRectF
        clip = squircle_path(QRectF(0, 0, self.width(), self.height()), self._radius)
        painter.setClipPath(clip)
        self._paint_glass_base(painter, QRectF(0, 0, self.width(), self.height()))
        if self._hover:
            painter.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(255, 255, 255, 30))
        if self._icon_painter:
            painter.setClipping(False)
            self._icon_painter(painter, self.width(), self.height())

    def _paint_glass_base(self, painter: QPainter, rect) -> None:
        """玻璃底：染底 + 顶光带（与 GlassButton 共用样式）。"""
        from PySide6.QtGui import QColor, QLinearGradient
        from PySide6.QtCore import QPointF, QRectF
        from .. import theme as T
        tint = QColor(T.DARK.card_tint)
        tint.setAlpha(120)
        painter.fillRect(rect, tint)
        grad = QLinearGradient(QPointF(rect.left(), rect.top()), QPointF(rect.left(), rect.top() + rect.height() * 0.5))
        grad.setColorAt(0.0, QColor(255, 255, 255, T.GLASS_TOP_HIGHLIGHT_ALPHA))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), min(rect.height() * 0.18, 12)), grad)


class KeyCap(RippleHostMixin, GlassContainer):
    """F1–F6 键位胶囊（小）。按下触发波纹。"""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None, *, text: str = "", radius: float = theme.RADIUS_SMALL):
        super().__init__(parent, radius=radius)
        self._ripple_setup()
        self._text = text
        self._hover = False
        self._pressed = False
        self._recording = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def setRecording(self, on: bool) -> None:
        self._recording = on
        self.update()

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self._mouse_pos = None; self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self.trigger_ripple(e.position())
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(e.position().toPoint()):
                self.clicked.emit()
        super().mouseReleaseEvent(e)

    def paintEvent(self, e: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont, QLinearGradient
        w, h = self.width(), self.height()
        clip = squircle_path(QRectF(0, 0, w, h), self._radius)
        painter.setClipPath(clip)
        # 键帽底
        grad = QLinearGradient(QPointF(0, 0), QPointF(0, h))
        if self._recording:
            grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
            grad.setColorAt(1.0, QColor(theme.current_palette().accent))
        else:
            grad.setColorAt(0.0, QColor(60, 62, 96, 220))
            grad.setColorAt(1.0, QColor(40, 42, 70, 220))
        painter.fillRect(QRectF(0, 0, w, h), grad)
        # 顶光
        tg = QLinearGradient(QPointF(0, 0), QPointF(0, h * 0.5))
        tg.setColorAt(0.0, QColor(255, 255, 255, 80))
        tg.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.5), tg)
        if self._hover:
            painter.fillRect(QRectF(0, 0, w, h), QColor(255, 255, 255, 25))
        self._paint_ripples(painter)
        # 文案
        painter.setClipping(False)
        font = QFont(theme.FONT_EN, 9, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 245))
        painter.drawText(0, 0, w, h, Qt.AlignCenter, self._text)
