"""Toast 提示：iOS 通知胶囊式（spec 5.3）。

- 顶部下拉出现，液态玻璃材质，超椭圆 8px；
- 2 秒自动消失（可配置时长）；
- 支持普通/成功/警告/错误四类，左色条区分；
- 静态调用 ``Toast.show(parent, text)``，自动管理实例生命周期。

设计为浮动子部件：贴在父窗口顶部居中，动画进出。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from .. import theme
from .liquid_glass import GlassContainer
from .squircle import squircle_path


# 类型 → 左色条颜色
_TYPE_COLORS = {
    "info": QColor(124, 111, 240, 220),
    "success": QColor(52, 211, 153, 220),
    "warning": QColor(250, 204, 21, 220),
    "error": QColor(239, 68, 68, 220),
}


class Toast(GlassContainer):
    """液态玻璃通知胶囊。"""

    DURATION = 2000  # 默认显示时长 ms
    ANIM_IN = 320
    ANIM_OUT = 260

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_SMALL)
        self._text = ""
        self._kind = "info"
        self._y_visible = 0.0
        self._y_hidden = 0.0
        self._shown = False
        self._anim: Optional[QPropertyAnimation] = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_toast)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)
        # 自适应宽度，固定高度
        self._h = 38
        self._min_w = 180
        self._max_w = 360
        self._y_offset = float(self.y())

    from PySide6.QtCore import Property

    def _get_slide(self) -> float:
        return self._y_offset

    def _set_slide(self, v: float) -> None:
        self._y_offset = v
        self.move(self.x(), int(v))
        self.update()

    slideFactor = Property(float, _get_slide, _set_slide)

    # ---- 显示/隐藏 ----
    def show_toast(self, text: str, *, kind: str = "info", duration: int = DURATION) -> None:
        self._text = text
        self._kind = kind if kind in _TYPE_COLORS else "info"
        self._resize_to_text()
        parent = self.parentWidget()
        if parent is not None:
            self._position(parent)
        self.show()
        self.raise_()
        self._animate_in()
        self._timer.start(duration)

    def hide_toast(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        self._animate_out()

    # ---- 几何 ----
    def _resize_to_text(self) -> None:
        from PySide6.QtGui import QFontMetrics, QFont
        font = QFont(theme.FONT_CN, 9, QFont.DemiBold)
        fm = QFontMetrics(font)
        pad = 40  # 左色条 + 内边距
        text_w = fm.horizontalAdvance(self._text)
        w = max(self._min_w, min(self._max_w, text_w + pad))
        self.setFixedSize(int(w), self._h)

    def _position(self, parent: QWidget) -> None:
        pw, ph = parent.width(), parent.height()
        w = self.width()
        x = (pw - w) // 2
        margin = 12
        self._y_visible = margin
        self._y_hidden = -self._h - margin
        if not self._shown:
            self.move(x, self._y_hidden)
            self._y_offset = self._y_hidden
        else:
            self.move(x, self._y_visible)

    # ---- 动画 ----
    def _animate_in(self) -> None:
        if self._anim is not None:
            self._anim.stop()
        self._shown = True
        a = QPropertyAnimation(self, b"slideFactor", self)
        a.setDuration(self.ANIM_IN)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.setStartValue(self._y_hidden)
        a.setEndValue(self._y_visible)
        a.start()
        self._anim = a

    def _animate_out(self) -> None:
        if self._anim is not None:
            self._anim.stop()
        a = QPropertyAnimation(self, b"slideFactor", self)
        a.setDuration(self.ANIM_OUT)
        a.setEasingCurve(QEasingCurve.InCubic)
        a.setStartValue(self._y_visible if self._shown else self._y_offset)
        a.setEndValue(self._y_hidden)
        a.finished.connect(self._on_hidden)
        a.start()
        self._anim = a

    def _on_hidden(self) -> None:
        self._shown = False
        self.hide()

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
            painter.drawPixmap(QPointF(0, 0), bd)

        # 染色（深色半透明）
        painter.fillRect(rect, QColor(30, 30, 52, 200))

        # 顶光带
        top = QLinearGradient(0, 0, 0, h * 0.5)
        top.setColorAt(0.0, QColor(255, 255, 255, 60))
        top.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.5), top)

        painter.setClipping(False)
        # 边缘描边
        pen = QPen(QColor(255, 255, 255, 50), 1.0)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPath(squircle_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), max(self._radius - 0.5, 1)))

        # 左色条（类型标识）
        bar_color = _TYPE_COLORS.get(self._kind, _TYPE_COLORS["info"])
        painter.setBrush(bar_color)
        painter.setPen(Qt.NoPen)
        bar_rect = QRectF(8, h * 0.28, 4.0, h * 0.44)
        painter.drawRoundedRect(bar_rect, 2.0, 2.0)

        # 文案
        font = QFont(theme.FONT_CN, 9, QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(242, 243, 251, 245))
        painter.drawText(QRectF(20, 0, w - 28, h), Qt.AlignLeft | Qt.AlignVCenter, self._text)


# ---- 静态便捷 API ----
_active_toasts: list[Toast] = []


def show_toast(parent: QWidget, text: str, *, kind: str = "info",
               duration: int = Toast.DURATION) -> Toast:
    """在父窗口顶部居中显示一条 toast（自动管理生命周期）。"""
    toast = Toast(parent)
    toast.show_toast(text, kind=kind, duration=duration)
    _active_toasts.append(toast)

    def _cleanup(*_args: object) -> None:
        try:
            _active_toasts.remove(toast)
        except ValueError:
            pass

    toast.destroyed.connect(_cleanup)
    return toast
