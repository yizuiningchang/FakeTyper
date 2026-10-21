"""预设库视图：标题行 + 数量徽标 + 搜索框 + 滚动列表（spec 5.2.4）。

- 列表项为 ``PresetCard``（液态玻璃卡片），支持点击选中、双击编辑、
  hover 操作菜单（置顶/编辑/重命名/副本/删除）、拖拽排序。
- 搜索框实时过滤标题/内容。
- 数量徽标显示当前/总数。

对外信号：
- ``selected(str)``：preset_id 被单击选中。
- ``editRequested(str)``：双击或菜单"编辑"。
- ``actionRequested(str, str)``：透传 PresetCard 的 actionRequested(preset_id, action)。
- ``orderChanged(list[str])``：拖拽排序后新的 preset_id 顺序。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDrag,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets.liquid_glass import GlassContainer
from ..widgets.preset_card import PresetCard
from ..widgets.squircle import squircle_path
from ...data.preset import Preset


_DRAG_MIME = "application/x-facktyper-preset-id"


class SearchBox(GlassContainer):
    """预设库搜索框：玻璃材质 + 等宽输入。

    信号 ``textChanged(str)``：透传 QLineEdit。
    """

    textChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_BUTTON)
        self.setFixedHeight(32)
        self._edit = QLineEdit(self)
        self._edit.setFrame(False)
        self._edit.setPlaceholderText("搜索预设…")
        self._edit.setClearButtonEnabled(True)
        self._edit.textChanged.connect(self.textChanged.emit)
        # 透明背景融入玻璃容器
        theme.style_palette_text(self._edit, "text", "text_dim")
        font = QFont(theme.FONT_CN, 9)
        self._edit.setFont(font)
        # 内边距
        self._edit.setTextMargins(10, 0, 24, 0)
        self._edit.move(2, 2)
        self._edit.resize(self.width() - 4, self.height() - 4)
        self.setMouseTracking(True)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._edit.resize(self.width() - 4, self.height() - 4)

    def paintEvent(self, e: QPaintEvent) -> None:
        # 先绘制玻璃底
        super().paintEvent(e)
        # 左侧搜索图标（放大镜符号）
        from PySide6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QColor(theme.current_palette().text_dim))
        painter.setFont(QFont(theme.FONT_EN, 9, QFont.Bold))
        painter.drawText(QRectF(self.width() - 22, 0, 18, self.height()), Qt.AlignCenter, "⌕")


class _PresetListContainer(QWidget):
    """容纳 PresetCard 的纵向滚动容器，支持拖拽排序。"""

    orderChanged = Signal(list)  # list[str] of preset_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._cards: list[PresetCard] = []
        self._active_id: Optional[str] = None
        self._drag_index: Optional[int] = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)
        self.setAcceptDrops(True)

    def set_presets(self, presets: list[Preset]) -> None:
        # 清空旧卡片
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        for p in presets:
            self._append_card(p)
        self._refresh_selection()

    def append_preset(self, preset: Preset) -> None:
        self._append_card(preset)
        self._refresh_selection()

    def remove_preset(self, preset_id: str) -> None:
        for i, card in enumerate(self._cards):
            if card.preset_id == preset_id:
                card.setParent(None)
                card.deleteLater()
                self._cards.pop(i)
                if self._active_id == preset_id:
                    self._active_id = None
                self._refresh_selection()
                return

    def update_preset(self, preset: Preset) -> None:
        for card in self._cards:
            if card.preset_id == preset.id:
                self._apply_data(card, preset)
                return

    def set_active(self, preset_id: Optional[str]) -> None:
        self._active_id = preset_id
        self._refresh_selection()

    def _append_card(self, preset: Preset) -> None:
        card = PresetCard(preset.id, self)
        self._apply_data(card, preset)
        # 插入到 stretch 之前
        idx = self._layout.count() - 1  # 最后一项是 stretch
        self._layout.insertWidget(idx, card)
        self._cards.append(card)
        card.clicked.connect(self._on_card_clicked)
        card.doubleClicked.connect(self._on_card_double)
        card.actionRequested.connect(self._on_card_action)
        card.setAcceptDrops(True)

    def _apply_data(self, card: PresetCard, preset: Preset) -> None:
        # 时间文案：优先 last_used_at，其次 created_at
        time_text = preset.last_used_at or preset.created_at or "—"
        # 截短到日期部分
        if " " in time_text:
            time_text = time_text.split(" ", 1)[0]
        card.setData(
            title=preset.title,
            char_count=preset.char_count,
            time_text=time_text,
            pinned=preset.pinned,
            selected=(preset.id == self._active_id),
        )

    def _refresh_selection(self) -> None:
        for card in self._cards:
            card.setSelected(card.preset_id == self._active_id)

    # ---- 信号回调 ----
    def _on_card_clicked(self, preset_id: str) -> None:
        # 由 PresetLibrary 转发；这里只更新选中态
        self.set_active(preset_id)

    def _on_card_double(self, preset_id: str) -> None:
        # 双击进入编辑（由 PresetLibrary 处理）
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, PresetLibrary):
                parent.editRequested.emit(preset_id)
                return
            parent = parent.parent()

    def _on_card_action(self, preset_id: str, action: str) -> None:
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, PresetLibrary):
                parent.actionRequested.emit(preset_id, action)
                return
            parent = parent.parent()

    # ---- 拖拽排序 ----
    def _card_index_at(self, pos) -> Optional[int]:
        for i, card in enumerate(self._cards):
            if card.geometry().contains(pos):
                return i
        return None

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            idx = self._card_index_at(e.position().toPoint())
            if idx is not None:
                # 仅当点中拖拽把手区域（左侧 0-20px）才允许拖拽
                card = self._cards[idx]
                local = e.position().toPoint() - card.geometry().topLeft()
                if local.x() <= 20:
                    self._drag_index = idx
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if e.buttons() & Qt.LeftButton and self._drag_index is not None:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_DRAG_MIME, self._cards[self._drag_index].preset_id.encode("utf-8"))
            mime.setText(self._cards[self._drag_index].preset_id)
            drag.setMimeData(mime)
            drag.exec_(Qt.MoveAction)
            self._drag_index = None
            return
        super().mouseMoveEvent(e)

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasFormat(_DRAG_MIME):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e) -> None:
        if not e.mimeData().hasFormat(_DRAG_MIME):
            e.ignore()
            return
        src_id = bytes(e.mimeData().data(_DRAG_MIME)).decode("utf-8")
        target_idx = self._card_index_at(e.position().toPoint())
        if target_idx is None:
            e.ignore()
            return
        # 重新排序
        src_idx = next((i for i, c in enumerate(self._cards) if c.preset_id == src_id), None)
        if src_idx is None or src_idx == target_idx:
            e.ignore()
            return
        moved = self._cards.pop(src_idx)
        self._cards.insert(target_idx, moved)
        # 重新插入 layout
        # 先全部移除（保留 stretch）
        for card in self._cards:
            self._layout.removeWidget(card)
        for card in self._cards:
            idx = self._layout.count() - 1
            self._layout.insertWidget(idx, card)
        self._layout.update()
        e.acceptProposedAction()
        self.orderChanged.emit([c.preset_id for c in self._cards])


class PresetLibrary(QWidget):
    """预设库视图：标题行 + 搜索 + 滚动列表。"""

    selected = Signal(str)
    editRequested = Signal(str)
    actionRequested = Signal(str, str)
    orderChanged = Signal(list)
    searchChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # 标题行：左 "预设库" + 数量徽标，右 搜索框
        title_row = QWidget(self)
        title_row.setAttribute(Qt.WA_TranslucentBackground, True)
        th = QVBoxLayout(title_row)
        th.setContentsMargins(2, 0, 2, 0)
        th.setSpacing(2)

        # 主标题 + 徽标
        cap = QLabel("预设库", title_row)
        cap.setFont(QFont(theme.FONT_CN, 10, QFont.Bold))
        theme.style_text(cap, "text")
        self._count_label = QLabel("0", title_row)
        self._count_label.setFont(QFont(theme.FONT_EN, 7, QFont.Bold))
        self._count_label.setStyleSheet(
            f"color: #FFFFFF; background: {theme.current_palette().accent};"
            f"border-radius: 8px; padding: 1px 6px;"
        )
        self._count_label.setFixedHeight(16)

        from PySide6.QtWidgets import QHBoxLayout
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(cap)
        top.addWidget(self._count_label)
        top.addStretch(1)
        th.addLayout(top)

        # 搜索框
        self._search = SearchBox(title_row)
        th.addWidget(self._search)
        root.addWidget(title_row)

        # 滚动列表
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setAttribute(Qt.WA_TranslucentBackground, True)
        # 透明 viewport
        viewport = self._scroll.viewport()
        viewport.setAttribute(Qt.WA_TranslucentBackground, True)
        pal = viewport.palette()
        pal.setColor(QPalette.Window, QColor(0, 0, 0, 0))
        viewport.setPalette(pal)
        # 滚动条样式
        self._scroll.setStyleSheet(self._scroll.styleSheet() + self._scrollbar_qss())

        self._list = _PresetListContainer(self._scroll)
        self._scroll.setWidget(self._list)
        root.addWidget(self._list, 1)

        # 信号转发
        self._list.orderChanged.connect(self.orderChanged.emit)

    def set_presets(self, presets: list[Preset], active_id: Optional[str] = None) -> None:
        self._count_label.setText(str(len(presets)))
        self._list.set_active(active_id)
        self._list.set_presets(presets)

    def append_preset(self, preset: Preset) -> None:
        self._count_label.setText(str(len(self._list._cards) + 1))
        self._list.append_preset(preset)

    def remove_preset(self, preset_id: str) -> None:
        before = len(self._list._cards)
        self._list.remove_preset(preset_id)
        self._count_label.setText(str(max(0, before - 1)))

    def update_preset(self, preset: Preset) -> None:
        self._list.update_preset(preset)

    def set_active(self, preset_id: Optional[str]) -> None:
        self._list.set_active(preset_id)

    def search_box(self) -> SearchBox:
        return self._search

    @staticmethod
    def _scrollbar_qss() -> str:
        return (
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }"
            "QScrollBar::handle:vertical {"
            " background: rgba(255,255,255,40); border-radius: 3px; min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(255,255,255,70); }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        )
