"""首启引导：全屏滑动卡片式 onboarding（spec 5.3）。

3 张液态玻璃卡片横向滑动切换：
1. 它能做什么 —— 应用简介 + 核心特性
2. 三步上手 —— 新建预设 / 开启总开关 / 按 F1·F3 开始
3. 快捷键表 —— F1–F6 默认功能

卡片为 ``GlassContainer``（继承液态玻璃质感），横向滑动由 ``QVariantAnimation``
驱动卡片容器 x 偏移。底部页码指示器 + 跳过 / 下一页 / 开始按钮。

对外信号 ``finished``：引导结束（跳过或完成），由 ``MainWindow`` 接收并持久化
``config.onboarding_shown``。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets.glass_button import GlassButton
from ..widgets.liquid_glass import GlassContainer
from ..widgets.squircle import squircle_path
from ...data.constants import Action, default_hotkey_map


def _paint_logo(painter: QPainter, x: float, y: float, d: float) -> None:
    """应用图标：紫色玻璃圆 + 内嵌键盘符号（与主窗口顶栏一致）。"""
    rect = QRectF(x, y, d, d)
    path = squircle_path(rect, d * 0.28)
    grad = QLinearGradient(QPointF(x, y), QPointF(x + d, y + d))
    grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
    grad.setColorAt(1.0, QColor(theme.current_palette().accent))
    painter.setBrush(grad)
    painter.setPen(Qt.NoPen)
    painter.drawPath(path)
    tg = QLinearGradient(QPointF(x, y), QPointF(x, y + d * 0.5))
    tg.setColorAt(0.0, QColor(255, 255, 255, 110))
    tg.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(x, y, d, d * 0.5), tg)
    painter.setBrush(QColor(255, 255, 255, 240))
    cell = d * 0.13
    gap = d * 0.04
    grid_x = x + (d - 3 * cell - 2 * gap) / 2
    grid_y = y + d * 0.42
    for r in range(2):
        for c in range(3):
            cx = grid_x + c * (cell + gap)
            cy = grid_y + r * (cell + gap)
            painter.drawRect(QRectF(cx, cy, cell, cell))


class _FeatureCard(GlassContainer):
    """单张引导卡片（液态玻璃材质）。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, radius=theme.RADIUS_CARD)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._content = QWidget(self)
        self._content.setAttribute(Qt.WA_TranslucentBackground, True)
        self._lay = QVBoxLayout(self._content)
        self._lay.setContentsMargins(22, 22, 22, 22)
        self._lay.setSpacing(10)

    def layout_main(self) -> QVBoxLayout:
        return self._lay

    def resizeEvent(self, e) -> None:  # noqa: D401
        super().resizeEvent(e)
        self._content.setGeometry(0, 0, self.width(), self.height())


class OnboardingPage(QWidget):
    """首启引导覆盖层。

    构造后调用 ``start()`` 显示并播放卡片入场；用户跳过或完成时发射 ``finished``。
    """

    finished = Signal()

    NUM_CARDS = 3

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._index = 0
        self._animating = False
        self._slide_anim: Optional[QVariantAnimation] = None

        self._build_ui()
        self._apply_card(0)

    # ---------------- UI 构建 ----------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 18)
        root.setSpacing(12)

        # 卡片滑动区：一个透明容器，内挂 3 张并排卡片，靠 move() 横向滑动
        self._track = QWidget(self)
        self._track.setAttribute(Qt.WA_TranslucentBackground, True)
        self._cards: list[_FeatureCard] = [
            self._build_card_intro(),
            self._build_card_steps(),
            self._build_card_hotkeys(),
        ]
        root.addWidget(self._track, 1)

        # 底栏：跳过按钮 + 页码点 + 下一页/开始按钮
        root.addLayout(self._build_bottom_bar())

    def _build_bottom_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 0, 4, 0)
        bar.setSpacing(8)

        # 跳过
        self._skip_btn = QPushButton("跳过", self)
        self._skip_btn.setCursor(Qt.PointingHandCursor)
        self._skip_btn.setFixedHeight(34)
        self._skip_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#9AA0C0;border:none;"
            "padding:0 10px;font-size:12px;}"
            "QPushButton:hover{color:#F2F3FB;}"
        )
        self._skip_btn.clicked.connect(self._on_skip)
        bar.addWidget(self._skip_btn)

        bar.addStretch(1)

        # 页码指示器（3 圆点）
        self._dots: list[QWidget] = []
        for i in range(self.NUM_CARDS):
            d = QWidget(self)
            d.setFixedSize(8, 8)
            self._dots.append(d)
            bar.addWidget(d)

        bar.addStretch(1)

        # 下一页 / 开始
        self._next_btn = GlassButton(self, text="下一页", radius=theme.RADIUS_BUTTON, accent=True)
        self._next_btn.setFixedHeight(36)
        self._next_btn.setMinimumWidth(92)
        self._next_btn.clicked.connect(self._on_next)
        bar.addWidget(self._next_btn)

        return bar

    # ---------------- 卡片1：它能做什么 ----------------
    def _build_card_intro(self) -> _FeatureCard:
        c = _FeatureCard(self._track)
        lay = c.layout_main()
        lay.addStretch(1)

        # logo + 标题（自绘）
        logo = _LogoTitle(c._content)
        logo.setFixedHeight(72)
        lay.addWidget(logo)

        sub = QLabel("录制教学视频时，把预设代码假装现场手敲", c._content)
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        theme.style_text(sub, "text_dim", "font-size:12px;")
        lay.addWidget(sub)

        lay.addSpacing(6)
        for text in (
            "按键触发 / 自动匀速 两种输出模式",
            "多预设库管理，拖拽排序 · 搜索过滤",
            "液态玻璃界面 · 主题随系统切换",
        ):
            row = QLabel("✓  " + text, c._content)
            theme.style_text(row, "text", "font-size:13px;")
            lay.addWidget(row, alignment=Qt.AlignCenter)
        lay.addStretch(2)
        return c

    # ---------------- 卡片2：三步上手 ----------------
    def _build_card_steps(self) -> _FeatureCard:
        c = _FeatureCard(self._track)
        lay = c.layout_main()
        lay.addStretch(1)

        title = QLabel("三步上手", c._content)
        title.setAlignment(Qt.AlignCenter)
        theme.style_text(title, "text", "font-size:18px;font-weight:600;")
        lay.addWidget(title)
        lay.addSpacing(8)

        steps = [
            ("1", "新建预设", "点击「＋ 新建预设」，粘贴或导入代码"),
            ("2", "开启总开关", "顶部电源开关，进入待命状态"),
            ("3", "开始输出", "F1 按键逐字输出 · F3 自动匀速"),
        ]
        for num, head, desc in steps:
            row = _StepRow(c._content, num, head, desc)
            lay.addWidget(row)
        lay.addStretch(2)
        return c

    # ---------------- 卡片3：快捷键表 ----------------
    def _build_card_hotkeys(self) -> _FeatureCard:
        c = _FeatureCard(self._track)
        lay = c.layout_main()
        lay.addStretch(1)

        title = QLabel("默认快捷键", c._content)
        title.setAlignment(Qt.AlignCenter)
        theme.style_text(title, "text", "font-size:18px;font-weight:600;")
        lay.addWidget(title)
        lay.addSpacing(6)

        hm = default_hotkey_map()
        order = [
            Action.KEY_TRIGGER,
            Action.STOP,
            Action.AUTO,
            Action.RESET,
            Action.RELOAD,
            Action.NEXT_PRESET,
        ]
        for a in order:
            key = hm[a.value]
            row = _HotkeyRow(c._content, key, a.label)
            lay.addWidget(row)

        tip = QLabel("可在「设置 → 快捷键」中重新绑定", c._content)
        tip.setAlignment(Qt.AlignCenter)
        theme.style_text(tip, "text_dim", "font-size:11px;")
        lay.addWidget(tip)
        lay.addStretch(2)
        return c

    # ---------------- 布局与绘制 ----------------
    def _apply_card(self, idx: int) -> None:
        """即时切换到第 idx 张卡片（无动画，初始化/resize 用）。"""
        self._index = idx
        self._layout_track()
        self._update_dots()
        self._update_next_btn()

    def _layout_track(self) -> None:
        """并排放置 3 张卡片；track 横向偏移到当前卡片。"""
        w = self._track.width()
        h = self._track.height()
        if w <= 0 or h <= 0:
            return
        gap = 14
        card_w = w
        for i, card in enumerate(self._cards):
            card.setGeometry(i * (card_w + gap), 0, card_w, h)
        # 偏移到当前卡片
        offset = -self._index * (card_w + gap)
        self._track.move(offset, 0)

    def resizeEvent(self, e) -> None:  # noqa: D401
        super().resizeEvent(e)
        self._layout_track()

    def paintEvent(self, e: QPaintEvent) -> None:
        """半透明深色遮罩，突出中央卡片。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pal = theme.current_palette()
        mask = QColor(pal.bg_bottom)
        mask.setAlpha(215)
        painter.fillRect(self.rect(), mask)

    def _update_dots(self) -> None:
        pal = theme.current_palette()
        for i, d in enumerate(self._dots):
            d.update()
            # 用 stylesheet 控圆点外观（当前页主色，其余灰）
            if i == self._index:
                col = pal.accent
                r = 4
            else:
                col = pal.off
                r = 3
            d.setFixedSize(r * 2, r * 2)
            d.setStyleSheet(
                f"background:{col};border-radius:{r}px;"
            )

    def _update_next_btn(self) -> None:
        if self._index >= self.NUM_CARDS - 1:
            self._next_btn.setText("开始使用")
        else:
            self._next_btn.setText("下一页")

    # ---------------- 滑动转场 ----------------
    def _slide_to(self, idx: int) -> None:
        if self._animating:
            return
        idx = max(0, min(self.NUM_CARDS - 1, idx))
        if idx == self._index:
            return
        w = self._track.width()
        gap = 14
        card_w = w
        start_offset = -self._index * (card_w + gap)
        end_offset = -idx * (card_w + gap)
        self._animating = True
        a = QVariantAnimation(self)
        a.setDuration(280)
        a.setStartValue(start_offset)
        a.setEndValue(end_offset)
        a.setEasingCurve(QEasingCurve.OutCubic)

        def _on_val(v: float) -> None:
            self._track.move(int(v), 0)

        def _on_done() -> None:
            self._index = idx
            self._animating = False
            self._update_dots()
            self._update_next_btn()

        a.valueChanged.connect(_on_val)
        a.finished.connect(_on_done)
        a.start()
        self._slide_anim = a

    # ---------------- 交互 ----------------
    def start(self) -> None:
        """显示并定位到首张卡片。"""
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self._apply_card(0)

    def _on_next(self) -> None:
        if self._index >= self.NUM_CARDS - 1:
            self.finished.emit()
        else:
            self._slide_to(self._index + 1)

    def _on_skip(self) -> None:
        self.finished.emit()

    def keyPressEvent(self, e) -> None:  # noqa: D401
        if e.key() == Qt.Key_Escape:
            self.finished.emit()
        elif e.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self._slide_to(self._index + 1)
        elif e.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self._slide_to(self._index - 1)
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_next()
        else:
            super().keyPressEvent(e)


# ============================================================
# 卡片内嵌小组件
# ============================================================

class _LogoTitle(QWidget):
    """卡片1 顶部：logo + 应用名（自绘）。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._name = QLabel("FakeTyper Pro", self)
        theme.style_text(self._name, "text", "font-size:20px;font-weight:700;")
        self._name.setAlignment(Qt.AlignCenter)

    def resizeEvent(self, e) -> None:  # noqa: D401
        super().resizeEvent(e)
        self._name.setGeometry(0, self.height() - 26, self.width(), 26)

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        d = 40
        _paint_logo(painter, (self.width() - d) / 2, 0, d)


class _StepRow(QWidget):
    """卡片2 单步：序号圆 + 标题 + 描述。"""

    def __init__(self, parent: QWidget, num: str, head: str, desc: str) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(56)
        self._num = num
        self._head = head
        self._desc = desc

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(12)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        h = QLabel(head, self)
        theme.style_text(h, "text", "font-size:13px;font-weight:600;")
        d = QLabel(desc, self)
        theme.style_text(d, "text_dim", "font-size:11px;")
        text_box.addWidget(h)
        text_box.addWidget(d)
        lay.addLayout(text_box, 1)

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pal = theme.current_palette()
        # 序号圆
        cx, cy = 20, self.height() / 2
        grad = QRadialGradient(QPointF(cx, cy), 14)
        grad.setColorAt(0.0, QColor(pal.accent_soft))
        grad.setColorAt(1.0, QColor(pal.accent))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 14, 14)
        # 序号文字
        painter.setPen(QColor(255, 255, 255, 240))
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(6, cy - 14, 28, 28), Qt.AlignCenter, self._num)


class _HotkeyRow(QWidget):
    """卡片3 单行：键帽 + 功能名。"""

    def __init__(self, parent: QWidget, key: str, label: str) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(34)
        self._key = key
        self._label = label

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pal = theme.current_palette()
        w, h = self.width(), self.height()
        # 键帽
        cap_w, cap_h = 44, 26
        cap_x, cap_y = 8, (h - cap_h) / 2
        cap_rect = QRectF(cap_x, cap_y, cap_w, cap_h)
        path = squircle_path(cap_rect, theme.RADIUS_SMALL)
        grad = QLinearGradient(QPointF(cap_x, cap_y), QPointF(cap_x, cap_y + cap_h))
        grad.setColorAt(0.0, QColor(255, 255, 255, 38))
        grad.setColorAt(1.0, QColor(255, 255, 255, 18))
        painter.setBrush(grad)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
        painter.drawPath(path)
        painter.setPen(QColor(pal.text))
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(cap_rect, Qt.AlignCenter, self._key)
        # 功能名
        painter.setPen(QColor(pal.text))
        f2 = QFont()
        f2.setPointSize(10)
        painter.setFont(f2)
        painter.drawText(QRectF(cap_x + cap_w + 14, 0, w - cap_x - cap_w - 14, h),
                         Qt.AlignVCenter | Qt.AlignLeft, self._label)
