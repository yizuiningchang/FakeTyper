"""预设库列表项：液态玻璃卡片（spec 4.4 / 5.2.4）。

- 超椭圆 12 玻璃材质 + 拖拽把手 + 标题 + 字符数 + 时间；
- 选中态高亮并标注「当前」徽标，选中触发波纹；
- hover 时右上角浮出上下文操作（编辑/重命名/复制/删除/置顶）；
- ``selected``、``clicked``、``doubleClicked``、``actionRequested`` 信号。

布局（高约 64px，宽度自适应）::

    [把手] [图标]  标题 ............... [徽标]
                   字符数 · 时间        [操作]
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
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from .. import theme
from .liquid_glass import GlassContainer
from .ripple import RippleHostMixin
from .squircle import squircle_path


class PresetCard(RippleHostMixin, GlassContainer):
    """预设库列表项。"""

    # 信号
    clicked = Signal(str)            # preset_id（单击选中）
    doubleClicked = Signal(str)      # preset_id（双击进入编辑）
    actionRequested = Signal(str, str)  # (preset_id, action) action ∈ {edit,rename,copy,delete,pin}

    CARD_H = 64
    ACTIONS = (("pin", "置顶"), ("edit", "编辑"), ("rename", "重命名"),
               ("copy", "副本"), ("delete", "删除"))

    def __init__(self, preset_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_CARD)
        self._ripple_setup()
        self._id = preset_id
        self._title = ""
        self._char_count = 0
        self._time_text = ""
        self._pinned = False
        self._selected = False
        self._hover = False
        self._pressed = False
        self._action_btns: list[tuple[str, QRectF]] = []  # 动态计算

        self.setFixedHeight(self.CARD_H)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    # ---- 数据 ----
    def setData(self, *, title: str, char_count: int, time_text: str,
               pinned: bool = False, selected: bool = False) -> None:
        self._title = title
        self._char_count = char_count
        self._time_text = time_text
        self._pinned = pinned
        self._selected = selected
        self.update()

    def setSelected(self, on: bool) -> None:
        self._selected = on
        self.update()

    def isSelected(self) -> bool:
        return self._selected

    @property
    def preset_id(self) -> str:
        return self._id

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
            # 先判断是否点中操作按钮
            for action, rect in self._action_btns:
                if rect.contains(e.position()):
                    self.actionRequested.emit(self._id, action)
                    return
            self._pressed = True
            self.trigger_ripple(e.position())
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(e.position().toPoint()):
                self.clicked.emit(self._id)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self.doubleClicked.emit(self._id)
        super().mouseDoubleClickEvent(e)

    # ---- 绘制 ----
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

        # 2) 染色：选中态主色渗入 / 普通态中性
        if self._selected:
            painter.fillRect(rect, QColor(124, 111, 240, 55))
        else:
            # M3-d：_tint 为 None 时跟随 current_palette() 动态主题
            pal = theme.current_palette()
            tint_color = self._tint if self._tint is not None else QColor(pal.card_tint)
            tint_alpha = self._tint_alpha if self._tint_alpha is not None else pal.card_tint_alpha
            tint = QColor(tint_color)
            tint.setAlpha(int(tint_alpha * self._base_alpha))
            painter.fillRect(rect, tint)

        # 3) 顶光带
        top = QColor(255, 255, 255, theme.GLASS_TOP_HIGHLIGHT_ALPHA)
        painter.fillRect(QRectF(0, 0, w, min(h * 0.18, 12)), top)

        # 4) hover / 选中柔光
        if self._hover or self._selected:
            painter.fillRect(rect, QColor(255, 255, 255, 20))

        # 5) 波纹
        self._paint_ripples(painter)

        painter.setClipping(False)

        # 6) 边缘
        if self._selected:
            pen = QPen(QColor(124, 111, 240, 160), 1.4)
        else:
            pen = QPen(QColor(255, 255, 255, 35), 1.0)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPath(squircle_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), max(self._radius - 0.5, 1)))

        # 7) 内容
        self._paint_content(painter, w, h)

    def _paint_content(self, painter: QPainter, w: float, h: float) -> None:
        self._action_btns = []
        pad_x = 14.0

        # 拖拽把手（左侧两列圆点）
        self._paint_handle(painter, 8.0, h / 2.0)

        x = pad_x + 10
        # 置顶/当前徽标
        if self._selected:
            self._paint_badge(painter, x, 10.0, "当前", QColor(124, 111, 240, 220))
            x += self._badge_width("当前") + 6
        if self._pinned:
            self._paint_pin_icon(painter, x + 4, 12.0)
            x += 16

        # 标题
        title_font = QFont(theme.FONT_CN, 10, QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor(theme.current_palette().text))
        max_title_w = w - x - pad_x - (120 if self._hover else 0)
        title = self._elide(painter, self._title, max_title_w)
        painter.drawText(QRectF(x, 8, max_title_w, 22), Qt.AlignLeft | Qt.AlignVCenter, title)

        # 副信息：字符数 · 时间
        sub = f"{self._char_count} 字 · {self._time_text}"
        sub_font = QFont(theme.FONT_CN, 8)
        painter.setFont(sub_font)
        painter.setPen(QColor(theme.current_palette().text_dim))
        painter.drawText(QRectF(x, 30, w - x - pad_x, 18), Qt.AlignLeft | Qt.AlignVCenter, sub)

        # hover 时右上角操作按钮
        if self._hover:
            self._paint_actions(painter, w, h)

    def _paint_handle(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.setPen(Qt.NoPen)
        for dy in (-5.0, 5.0):
            painter.drawEllipse(QPointF(cx - 3.0, cy + dy), 1.5, 1.5)
            painter.drawEllipse(QPointF(cx + 3.0, cy + dy), 1.5, 1.5)

    def _badge_width(self, text: str) -> float:
        from PySide6.QtGui import QFontMetrics, QFont
        f = QFont(theme.FONT_CN, 7, QFont.Bold)
        return QFontMetrics(f).horizontalAdvance(text) + 14.0

    def _paint_badge(self, painter: QPainter, x: float, y: float, text: str, color: QColor) -> None:
        from PySide6.QtGui import QFont
        bw = self._badge_width(text)
        bh = 16.0
        rect = QRectF(x, y, bw, bh)
        path = squircle_path(rect, 6.0)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)
        painter.setPen(QColor(255, 255, 255, 240))
        painter.setFont(QFont(theme.FONT_CN, 7, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _paint_pin_icon(self, painter: QPainter, x: float, y: float) -> None:
        """极简图钉图标：小三角 + 圆点。"""
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QPointF as PF
        painter.setBrush(QColor(250, 204, 21, 220))
        painter.setPen(Qt.NoPen)
        # 图钉头（小圆）
        painter.drawEllipse(PF(x + 3, y + 3), 3.0, 3.0)
        # 图钉尖（小三角）
        path = QPainterPath()
        path.moveTo(x + 1, y + 7)
        path.lineTo(x + 5, y + 7)
        path.lineTo(x + 3, y + 11)
        path.closeSubpath()
        painter.drawPath(path)

    def _paint_actions(self, painter: QPainter, w: float, h: float) -> None:
        """右上角浮出操作按钮组（置顶/编辑/重命名/副本/删除）。"""
        from PySide6.QtGui import QFont
        btn_w = 26.0
        btn_h = 22.0
        gap = 3.0
        total = len(self.ACTIONS) * btn_w + (len(self.ACTIONS) - 1) * gap
        x = w - total - 8.0
        y = (h - btn_h) / 2.0
        font = QFont(theme.FONT_EN, 7, QFont.Bold)
        painter.setFont(font)
        self._action_btns = []
        for action, label in self.ACTIONS:
            rect = QRectF(x, y, btn_w, btn_h)
            path = squircle_path(rect, 6.0)
            color = QColor(239, 68, 68, 180) if action == "delete" else QColor(255, 255, 255, 40)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(rect, Qt.AlignCenter, label[0])
            self._action_btns.append((action, QRectF(rect)))
            x += btn_w + gap

    @staticmethod
    def _elide(painter: QPainter, text: str, max_w: float) -> str:
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(painter.font())
        if fm.horizontalAdvance(text) <= max_w:
            return text
        ell = "…"
        elided = text
        while elided and fm.horizontalAdvance(elided + ell) > max_w:
            elided = elided[:-1]
        return elided + ell if elided else ell
