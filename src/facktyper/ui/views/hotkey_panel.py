"""F1–F6 热键面板：2×3 卡片栅格（spec 5.2.3）。

每张卡片为液态玻璃材质（超椭圆 12），含：
- 键帽样式键名（KeyCap 风格的小胶囊，置于卡片右上角）
- 功能名（中文）
- 状态指示灯（激活中的模式亮灯：按键/自动模式高亮）
- 卡片整体可点：触发一次该热键绑定的功能（与按下物理键等效）

布局：2 行 × 3 列等宽栅格，间距 8px。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEvent,
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
    QPen,
)
from PySide6.QtWidgets import QGridLayout, QWidget

from .. import theme
from ..widgets.glass_button import KeyCap
from ..widgets.liquid_glass import GlassContainer
from ..widgets.ripple import RippleHostMixin
from ..widgets.squircle import squircle_path
from ...data.constants import Action


# 功能图标（极简符号字符）——与 Action 顺序对齐
_ACTION_GLYPH: dict[str, str] = {
    Action.KEY_TRIGGER.value: "⌨",
    Action.STOP.value: "■",
    Action.AUTO.value: "▶",
    Action.RESET.value: "↺",
    Action.RELOAD.value: "⟳",
    Action.NEXT_PRESET.value: "⇥",
}


class HotkeyCard(RippleHostMixin, GlassContainer):
    """单张热键卡片：键名 + 功能 + 状态灯，可点击触发动作。"""

    clicked = Signal(str)  # action_value

    def __init__(self, action: Action, key: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_CARD)
        self._ripple_setup()
        self._action = action
        self._key = key
        self._active = False       # 该动作对应模式是否处于激活态（仅 KEY/AUTO 有意义）
        self._hover = False
        self._pressed = False
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def setKey(self, key: str) -> None:
        self._key = key
        self.update()

    def setActive(self, on: bool) -> None:
        self._active = on
        self.update()

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
                self.clicked.emit(self._action.value)
        super().mouseReleaseEvent(e)

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = float(self.width()), float(self.height())
        rect = QRectF(0, 0, w, h)
        clip = squircle_path(rect, self._radius)
        painter.setClipPath(clip)

        # 1) 玻璃底
        bd = self._resolve_backdrop()
        if bd is not None and not bd.isNull():
            painter.drawPixmap(QPointF(0, 0), bd)

        # 2) 染色：激活态主色渗入 / 普通态中性
        if self._active:
            painter.fillRect(rect, QColor(124, 111, 240, 60))
        else:
            # M3-d：_tint 为 None 时跟随 current_palette() 动态主题
            pal = theme.current_palette()
            tint_color = self._tint if self._tint is not None else QColor(pal.card_tint)
            tint_alpha = self._tint_alpha if self._tint_alpha is not None else pal.card_tint_alpha
            tint = QColor(tint_color)
            tint.setAlpha(int(tint_alpha * self._base_alpha))
            painter.fillRect(rect, tint)

        # 3) 顶光带
        top = QLinearGradient(QPointF(0, 0), QPointF(0, h * 0.5))
        top.setColorAt(0.0, QColor(255, 255, 255, theme.GLASS_TOP_HIGHLIGHT_ALPHA))
        top.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.18), top)

        # 4) hover / 激活柔光
        if self._hover or self._active:
            painter.fillRect(rect, QColor(255, 255, 255, 20))

        # 5) 波纹
        self._paint_ripples(painter)

        painter.setClipping(False)

        # 6) 边缘
        if self._active:
            pen = QPen(QColor(124, 111, 240, 170), 1.3)
        else:
            pen = QPen(QColor(255, 255, 255, 38), 1.0)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPath(squircle_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), max(self._radius - 0.5, 1)))

        # 7) 内容
        self._paint_content(painter, w, h)

    def _paint_content(self, painter: QPainter, w: float, h: float) -> None:
        # 左上：功能图标
        glyph = _ACTION_GLYPH.get(self._action.value, "•")
        painter.setFont(QFont(theme.FONT_EN, 14, QFont.Bold))
        painter.setPen(QColor(theme.current_palette().text))
        painter.drawText(QRectF(12, 8, 28, 28), Qt.AlignCenter, glyph)

        # 右上：键帽（F1–F6 胶囊）
        key_w, key_h = 36.0, 22.0
        kx = w - key_w - 8.0
        ky = 8.0
        key_rect = QRectF(kx, ky, key_w, key_h)
        kpath = squircle_path(key_rect, theme.RADIUS_SMALL)
        grad = QLinearGradient(QPointF(kx, ky), QPointF(kx, ky + key_h))
        if self._active:
            grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
            grad.setColorAt(1.0, QColor(theme.current_palette().accent))
        else:
            grad.setColorAt(0.0, QColor(60, 62, 96, 220))
            grad.setColorAt(1.0, QColor(40, 42, 70, 220))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawPath(kpath)
        # 顶光
        tg = QLinearGradient(QPointF(kx, ky), QPointF(kx, ky + key_h * 0.5))
        tg.setColorAt(0.0, QColor(255, 255, 255, 80))
        tg.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(kx, ky, key_w, key_h * 0.5), tg)
        # 键名文字
        painter.setPen(QColor(255, 255, 255, 245))
        painter.setFont(QFont(theme.FONT_EN, 8, QFont.Bold))
        painter.drawText(key_rect, Qt.AlignCenter, self._key)

        # 中部：功能名
        painter.setPen(QColor(theme.current_palette().text))
        painter.setFont(QFont(theme.FONT_CN, 9, QFont.DemiBold))
        painter.drawText(
            QRectF(12, 40, w - 24, 22),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._action.label,
        )

        # 底部：状态指示灯
        self._paint_status(painter, w, h)

    def _paint_status(self, painter: QPainter, w: float, h: float) -> None:
        # 左下小圆点 + 文案
        cx, cy = 16.0, h - 16.0
        if self._active:
            color = QColor(theme.current_palette().on)
        elif self._action.value in (Action.KEY_TRIGGER.value, Action.AUTO.value):
            color = QColor(theme.current_palette().off)
        else:
            color = QColor(120, 124, 150, 180)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        # 呼吸光环（激活态）
        if self._active:
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 80))
            painter.drawEllipse(QPointF(cx, cy), 6.0, 6.0)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(cx, cy), 3.2, 3.2)

        text = "激活中" if self._active else "待命"
        painter.setPen(QColor(theme.current_palette().text_dim))
        painter.setFont(QFont(theme.FONT_CN, 7))
        painter.drawText(QRectF(24, cy - 8, w - 30, 16), Qt.AlignLeft | Qt.AlignVCenter, text)


class HotkeyPanel(QWidget):
    """2×3 热键卡片栅格。

    信号 ``actionTriggered(str)``：用户在 UI 上点击卡片时发射，参数为 action_value。
    信号 ``editRequested(str)``：用户长按/右键卡片请求重绑定（M3 设置中心实装）。
    """

    actionTriggered = Signal(str)
    editRequested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._cards: dict[str, HotkeyCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)
        # 按 Action 枚举顺序填充 2×3
        actions = list(Action)
        for i, action in enumerate(actions):
            card = HotkeyCard(action, action.default_key, self)
            card.clicked.connect(lambda av=action.value: self.actionTriggered.emit(av))
            row = i // 3
            col = i % 3
            layout.addWidget(card, row, col)
            layout.setRowMinimumHeight(row, 96)
            self._cards[action.value] = card

    def set_hotkey_map(self, hotkey_map: dict[str, str]) -> None:
        """按 {action_value: key} 更新所有卡片键名。"""
        for action_value, card in self._cards.items():
            key = hotkey_map.get(action_value, "")
            if key:
                card.setKey(key)

    def set_active_mode(self, mode: str) -> None:
        """根据引擎模式刷新卡片激活态。``mode`` ∈ {'idle','key','auto'}。"""
        for card in self._cards.values():
            card.setActive(False)
        target = Action.KEY_TRIGGER.value if mode == "key" else (
            Action.AUTO.value if mode == "auto" else None
        )
        if target is not None:
            card = self._cards.get(target)
            if card is not None:
                card.setActive(True)

    def cards(self) -> dict[str, HotkeyCard]:
        return dict(self._cards)
