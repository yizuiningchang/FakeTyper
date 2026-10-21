"""通用设置行：左标题 + 描述，右控件，独立玻璃卡片。

用法::

    row = SettingRow(title="开机自启", desc="登录 Windows 时自动启动",
                     widget=toggle)
    toggle.toggled.connect(...)
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .. import theme
from .liquid_glass import GlassContainer


class SettingRow(GlassContainer):
    """一行设置项：左标题/描述，右控件，独立玻璃卡片。"""

    def __init__(
        self,
        title: str,
        desc: str = "",
        widget: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, radius=theme.RADIUS_CARD)
        self._title_text = title
        self._desc_text = desc

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 10, 12, 10)
        h.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)
        self._title_lbl = QLabel(title, self)
        self._title_lbl.setFont(QFont(theme.FONT_CN, 9, QFont.DemiBold))
        self._title_lbl.setStyleSheet(
            f"color: {theme.current_palette().text}; background: transparent;"
        )
        left.addWidget(self._title_lbl)
        if desc:
            self._desc_lbl = QLabel(desc, self)
            self._desc_lbl.setFont(QFont(theme.FONT_CN, 8))
            self._desc_lbl.setStyleSheet(
                f"color: {theme.current_palette().text_dim}; background: transparent;"
            )
            left.addWidget(self._desc_lbl)
        h.addLayout(left, 1)

        self._widget: Optional[QWidget] = None
        if widget is not None:
            self._widget = widget
            h.addWidget(widget, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_widget(self, w: QWidget) -> None:
        """替换右侧控件。"""
        if self._widget is not None:
            self._widget.setParent(None)
        self._widget = w
        if w is not None:
            self.layout().addWidget(w, 0, Qt.AlignRight | Qt.AlignVCenter)

    def widget(self) -> Optional[QWidget]:
        return self._widget

    def title_label(self) -> QLabel:
        return self._title_lbl
