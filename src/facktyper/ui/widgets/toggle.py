"""总开关 Toggle：iOS 风格液态玻璃大电源开关（spec 4.2 / 5.2.2）。

- 超椭圆轨道（液态玻璃材质）+ 圆形滑块；
- ON = 绿光激活态 + 柔光晕呼吸；OFF = 待命灰；
- 切换时弹性回弹曲线 + 玻璃光泽流动 + 波纹从触点扩散；
- ``toggled`` 信号通知总控开关状态变化。

布局：横向 Track（宽 ~96，高 ~52），滑块直径 ~44，留边 ~4。
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
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from .. import theme
from .liquid_glass import GlassContainer
from .ripple import RippleHostMixin
from .squircle import squircle_path


class MasterToggle(RippleHostMixin, GlassContainer):
    """总开关：大尺寸电源 Toggle。

    信号 ``toggled(bool)``：True=激活待命（注册热键），False=关闭。
    """

    toggled = Signal(bool)

    # Track 几何
    TRACK_W = 96.0
    TRACK_H = 52.0
    KNOB_D = 44.0
    PADDING = 4.0  # 滑块到轨道边的留白

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_BUTTON)
        self._ripple_setup()
        self._checked = False
        self._hover = False
        self._pressed = False
        # 滑块位置（0=关，1=开）
        self._knob = 0.0
        self._knob_anim: Optional[QPropertyAnimation] = None
        # 呼吸光晕相位（0..1 循环）
        self._breath = 0.0
        self._breath_anim: Optional[QPropertyAnimation] = None

        self.setFixedSize(int(self.TRACK_W), int(self.TRACK_H))
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    from PySide6.QtCore import Property

    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, v: float) -> None:
        self._knob = v
        self.update()

    knobFactor = Property(float, _get_knob, _set_knob)

    def _get_breath(self) -> float:
        return self._breath

    def _set_breath(self, v: float) -> None:
        self._breath = v
        if self._checked:
            self.update()

    breathFactor = Property(float, _get_breath, _set_breath)

    # ---- 状态 ----
    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, on: bool, *, animate: bool = True) -> None:
        if self._checked == on:
            return
        self._checked = on
        self._animate_knob(1.0 if on else 0.0, animate)
        if on:
            self._start_breath()
        else:
            self._stop_breath()
        self.toggled.emit(on)
        self.update()

    def toggle(self) -> None:
        self.setChecked(not self._checked)

    # ---- 动画 ----
    def _animate_knob(self, target: float, animate: bool) -> None:
        if self._knob_anim is not None:
            self._knob_anim.stop()
        if not animate:
            self._knob = target
            self.update()
            return
        a = QPropertyAnimation(self, b"knobFactor", self)
        a.setDuration(420)
        a.setEasingCurve(QEasingCurve.OutBack)
        a.setStartValue(self._knob)
        a.setEndValue(target)
        a.start()
        self._knob_anim = a

    def _start_breath(self) -> None:
        if self._breath_anim is not None and self._breath_anim.state() == QPropertyAnimation.Running:
            return
        a = QPropertyAnimation(self, b"breathFactor", self)
        a.setDuration(2200)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.InOutSine)
        a.finished.connect(self._restart_breath)
        a.start()
        self._breath_anim = a

    def _restart_breath(self) -> None:
        if self._checked:
            self._breath = 0.0
            self._start_breath()

    def _stop_breath(self) -> None:
        if self._breath_anim is not None:
            self._breath_anim.stop()
        self._breath = 0.0
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
            self.trigger_ripple(e.position())
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(e.position().toPoint()):
                self.toggle()
        super().mouseReleaseEvent(e)

    # ---- 绘制 ----
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(0, 0, w, h)

        # 轨道超椭圆裁剪
        clip = squircle_path(rect, self._radius)
        painter.setClipPath(clip)

        # 1) 玻璃底（复用 GlassContainer 的背景解析）
        bd = self._resolve_backdrop()
        if bd is not None and not bd.isNull():
            painter.drawPixmap(QPointF(0, 0), bd)

        # 2) 轨道染色：激活绿渐变 / 待命灰
        if self._checked:
            grad = QLinearGradient(QPointF(0, 0), QPointF(0, h))
            grad.setColorAt(0.0, QColor("#34D399"))
            grad.setColorAt(1.0, QColor("#10B981"))
            painter.fillRect(rect, grad)
        else:
            grad = QLinearGradient(QPointF(0, 0), QPointF(0, h))
            grad.setColorAt(0.0, QColor(70, 72, 108, 200))
            grad.setColorAt(1.0, QColor(48, 50, 78, 200))
            painter.fillRect(rect, grad)

        # 3) 顶光带（镜面反射）
        top = QLinearGradient(QPointF(0, 0), QPointF(0, h * 0.5))
        top.setColorAt(0.0, QColor(255, 255, 255, 90))
        top.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.5), top)

        # 4) 激活态呼吸光晕（随相位脉动）
        if self._checked:
            pulse = 0.5 + 0.5 * (1.0 - abs(self._breath * 2.0 - 1.0))  # 三角波 0..1..0
            glow = QRadialGradient(QPointF(w / 2, h / 2), w * 0.6)
            a = int(40 + 30 * pulse)
            glow.setColorAt(0.0, QColor(52, 211, 153, a))
            glow.setColorAt(1.0, QColor(52, 211, 153, 0))
            painter.fillRect(rect, glow)

        # 5) hover 柔光
        if self._hover and not self._pressed:
            painter.fillRect(rect, QColor(255, 255, 255, 25))

        # 6) 波纹
        self._paint_ripples(painter)

        painter.setClipping(False)

        # 7) 边缘折射描边
        self._paint_edge(painter, rect)

        # 8) 滑块
        self._paint_knob(painter, w, h)

    def _paint_knob(self, painter: QPainter, w: float, h: float) -> None:
        """滑块：圆形玻璃球，随 knob 因子横向滑动。"""
        travel = w - self.KNOB_D - self.PADDING * 2
        cx = self.PADDING + self.KNOB_D / 2.0 + travel * self._knob
        cy = h / 2.0
        r = self.KNOB_D / 2.0

        # 滑块阴影（悬浮感）
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy + 2.0), r, r)

        # 滑块主体：白色玻璃球 + 顶光
        body = QLinearGradient(QPointF(cx, cy - r), QPointF(cx, cy + r))
        body.setColorAt(0.0, QColor(255, 255, 255, 250))
        body.setColorAt(0.6, QColor(244, 245, 250, 250))
        body.setColorAt(1.0, QColor(210, 214, 230, 250))
        painter.setBrush(body)
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 顶部高光斑
        hl = QRadialGradient(QPointF(cx, cy - r * 0.35), r * 0.7)
        hl.setColorAt(0.0, QColor(255, 255, 255, 220))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(hl)
        painter.drawEllipse(QPointF(cx, cy - r * 0.2), r * 0.85, r * 0.6)

        # 激活态：滑块中心电源图标光晕（极简——一个小绿点）
        if self._checked:
            painter.setBrush(QColor(16, 185, 129, 230))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
