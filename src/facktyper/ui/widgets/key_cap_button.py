"""可录制键帽按钮：点击进入录制态，按 F1–F6 完成绑定。

用法::

    btn = KeyCapButton(action_value="key_trigger", current_key="F1")
    btn.keyRecorded.connect(lambda action_value, key: ...)
    btn.recordingCanceled.connect(lambda: ...)
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ...data.constants import ALLOWED_HOTKEYS
from .. import theme
from .liquid_glass import GlassContainer
from .ripple import RippleHostMixin
from .squircle import squircle_path


class KeyCapButton(RippleHostMixin, GlassContainer):
    """可录制键帽：点击 → 录制态 → 按 F1–F6 完成绑定。

    信号：
    - ``keyRecorded(str action_value, str key)``：录制到合法键
    - ``recordingCanceled()``：Esc 或点击外部取消录制
    """

    keyRecorded = Signal(str, str)
    recordingCanceled = Signal()

    def __init__(
        self,
        action_value: str,
        current_key: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, radius=theme.RADIUS_SMALL)
        self._ripple_setup()
        self._action_value = action_value
        self._key = current_key
        self._recording = False
        self._hover = False
        self._pressed = False
        # 录制态脉冲相位 0..1
        self._pulse = 0.0
        self._pulse_anim: Optional[QPropertyAnimation] = None

        self.setFixedSize(64, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    from PySide6.QtCore import Property

    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, v: float) -> None:
        self._pulse = v
        if self._recording:
            self.update()

    pulseFactor = Property(float, _get_pulse, _set_pulse)

    # ---- 状态 ----
    def setKey(self, key: str) -> None:
        self._key = key
        self.update()

    def key(self) -> str:
        return self._key

    def isRecording(self) -> bool:
        return self._recording

    def setRecording(self, on: bool) -> None:
        if on == self._recording:
            return
        self._recording = on
        if on:
            self._start_pulse()
            self.setFocus(Qt.OtherFocusReason)
        else:
            self._stop_pulse()
        self.update()

    def _start_pulse(self) -> None:
        if self._pulse_anim is not None and self._pulse_anim.state() == QPropertyAnimation.Running:
            return
        a = QPropertyAnimation(self, b"pulseFactor", self)
        a.setDuration(1400)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.InOutSine)
        a.finished.connect(self._restart_pulse)
        a.start()
        self._pulse_anim = a

    def _restart_pulse(self) -> None:
        if self._recording:
            self._pulse = 0.0
            self._start_pulse()

    def _stop_pulse(self) -> None:
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
        self._pulse = 0.0

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
            if self._recording:
                # 录制中再次点击 → 取消
                self.setRecording(False)
                self.recordingCanceled.emit()
            else:
                self.setRecording(True)
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if not self._recording:
            super().keyPressEvent(e)
            return
        key = e.key()
        # Esc 取消录制
        if key == Qt.Key_Escape:
            self.setRecording(False)
            self.recordingCanceled.emit()
            return
        # 检查是否在 F1–F6 白名单
        key_name = _qt_key_to_name(key)
        if key_name and key_name in ALLOWED_HOTKEYS:
            self.setRecording(False)
            self._key = key_name
            self.update()
            self.keyRecorded.emit(self._action_value, key_name)
        else:
            # 非白名单键：忽略，继续录制
            pass

    def focusOutEvent(self, e: QEvent) -> None:
        if self._recording:
            self.setRecording(False)
            self.recordingCanceled.emit()
        super().focusOutEvent(e)

    # ---- 绘制 ----
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(0, 0, w, h)
        clip = squircle_path(rect, self._radius)
        painter.setClipPath(clip)

        # 键帽底色
        grad = QLinearGradient(0, 0, 0, h)
        if self._recording:
            # 录制态：主色渐变 + 脉冲
            pulse = 0.5 + 0.5 * (1.0 - abs(self._pulse * 2.0 - 1.0))
            grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
            grad.setColorAt(1.0, QColor(theme.current_palette().accent))
            painter.fillRect(rect, grad)
            # 脉冲光晕
            glow = QRadialGradient(rect.center(), max(w, h) * 0.7)
            a = int(60 + 50 * pulse)
            glow.setColorAt(0.0, QColor(255, 255, 255, a))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(rect, glow)
        else:
            grad.setColorAt(0.0, QColor(60, 62, 96, 220))
            grad.setColorAt(1.0, QColor(40, 42, 70, 220))
            painter.fillRect(rect, grad)

        # 顶光带
        tg = QLinearGradient(0, 0, 0, h * 0.5)
        tg.setColorAt(0.0, QColor(255, 255, 255, 80))
        tg.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.5), tg)

        # hover
        if self._hover:
            painter.fillRect(rect, QColor(255, 255, 255, 25))

        # 波纹
        self._paint_ripples(painter)
        painter.setClipping(False)

        # 文案
        font = QFont(theme.FONT_EN, 9, QFont.Bold)
        painter.setFont(font)
        if self._recording:
            text = "···"
            painter.setPen(QColor(255, 255, 255, 245))
        elif self._key:
            text = self._key
            painter.setPen(QColor(255, 255, 255, 245))
        else:
            text = "—"
            painter.setPen(QColor(theme.current_palette().text_dim))
        painter.drawText(rect, Qt.AlignCenter, text)


def _qt_key_to_name(key: int) -> str:
    """Qt 键值 → 热键名（仅 F1–F6）。"""
    if Qt.Key_F1 <= key <= Qt.Key_F6:
        return f"F{key - Qt.Key_F1 + 1}"
    return ""
