"""玻璃风格确认对话框（非模态：遮罩 + 居中弹窗）。

用于快捷键冲突、清空预设二次确认等。不使用 ``QDialog.exec``（嵌套事件循环），
改用遮罩 ``QWidget`` 覆盖父区域 + 居中弹窗 + ``accepted``/``rejected`` 信号回调，
便于在离屏渲染测试中 ``processEvents`` 驱动。

用法::

    dlg = ConflictDialog(parent, title="键位冲突",
            desc="F1 已被「按键触发模式」占用，是否交换？",
            primary="交换键位", secondary="取消")
    dlg.accepted.connect(on_accept)
    dlg.rejected.connect(on_reject)
    dlg.exec_modal()
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import theme
from .glass_button import GlassButton
from .liquid_glass import GlassContainer


class ConflictDialog(GlassContainer):
    """玻璃确认框。"""

    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        desc: str = "",
        primary: str = "确定",
        secondary: str = "取消",
    ) -> None:
        super().__init__(parent, radius=theme.RADIUS_CARD)
        self._parent_widget = parent
        self.setFixedWidth(300)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._mask: Optional[QWidget] = None

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)

        self._title_lbl = QLabel(title, self)
        self._title_lbl.setFont(QFont(theme.FONT_CN, 11, QFont.Bold))
        self._title_lbl.setStyleSheet(
            f"color: {theme.current_palette().text}; background: transparent;"
        )
        self._title_lbl.setWordWrap(True)
        v.addWidget(self._title_lbl)

        if desc:
            self._desc_lbl = QLabel(desc, self)
            self._desc_lbl.setFont(QFont(theme.FONT_CN, 9))
            self._desc_lbl.setStyleSheet(
                f"color: {theme.current_palette().text_dim}; background: transparent;"
            )
            self._desc_lbl.setWordWrap(True)
            v.addWidget(self._desc_lbl)

        h = QHBoxLayout()
        h.setSpacing(8)
        self._secondary_btn = GlassButton(
            self, text=secondary, radius=theme.RADIUS_BUTTON, accent=False
        )
        self._secondary_btn.setFixedHeight(36)
        self._primary_btn = GlassButton(
            self, text=primary, radius=theme.RADIUS_BUTTON, accent=True
        )
        self._primary_btn.setFixedHeight(36)
        h.addWidget(self._secondary_btn, 1)
        h.addWidget(self._primary_btn, 1)
        v.addLayout(h)

        self._primary_btn.clicked.connect(self._accept)
        self._secondary_btn.clicked.connect(self._reject)

    def _accept(self) -> None:
        self.accepted.emit()
        self._close()

    def _reject(self) -> None:
        self.rejected.emit()
        self._close()

    def _close(self) -> None:
        if self._mask is not None:
            self._mask.setParent(None)
            self._mask.deleteLater()
            self._mask = None
        self.hide()
        self.setParent(None)

    def exec_modal(self) -> None:
        """显示遮罩 + 居中弹窗（非阻塞）。"""
        root = self._parent_widget or self.parentWidget()
        if root is None:
            self.show()
            return

        # 遮罩：覆盖父区域，半透明黑，拦截背景交互
        self._mask = QWidget(root)
        self._mask.setStyleSheet("background: rgba(0,0,0,120);")
        self._mask.setGeometry(root.rect())
        self._mask.show()
        self._mask.lower()

        # 把对话框挂到 root 并居中
        self.setParent(root)
        self.adjustSize()
        cx = root.rect().center().x() - self.width() // 2
        cy = root.rect().center().y() - self.height() // 2
        self.move(max(0, cx), max(0, cy))
        self.show()
        self.raise_()
