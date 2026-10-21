"""滑块 + 数值标签：玻璃容器包裹 QSlider，右侧实时数值。

用法::

    s = SliderWithLabel(min_=10, max=2000, value=80, unit="ms", step=10)
    s.valueChanged.connect(...)
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSlider, QWidget

from .. import theme
from .liquid_glass import GlassContainer


class SliderWithLabel(QWidget):
    """水平滑块 + 数值标签。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        min_: int,
        max_: int,
        value: int,
        unit: str = "",
        step: int = 1,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._unit = unit

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        self._container = GlassContainer(self, radius=theme.RADIUS_SMALL)
        ch = QHBoxLayout(self._container)
        ch.setContentsMargins(12, 4, 12, 4)
        ch.setSpacing(8)

        self._slider = QSlider(Qt.Horizontal, self._container)
        self._slider.setMinimum(min_)
        self._slider.setMaximum(max_)
        self._slider.setValue(value)
        self._slider.setSingleStep(step)
        self._slider.setPageStep(step * 5)
        self._slider.setStyleSheet(self._slider_qss())

        self._label = QLabel(self._fmt(value), self._container)
        self._label.setFont(QFont(theme.FONT_EN, 8, QFont.DemiBold))
        self._label.setStyleSheet(
            f"color: {theme.current_palette().accent_soft}; background: transparent;"
        )
        self._label.setMinimumWidth(48)
        self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        ch.addWidget(self._slider, 1)
        ch.addWidget(self._label, 0)
        h.addWidget(self._container, 1)

        self._slider.valueChanged.connect(self._on_val)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(36)

    # ---- 接口 ----
    def _fmt(self, v: int) -> str:
        return f"{v}{self._unit}"

    def _on_val(self, v: int) -> None:
        self._label.setText(self._fmt(v))
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self._slider.value()

    def setValue(self, v: int) -> None:
        self._slider.setValue(v)

    def setEnabled(self, on: bool) -> None:  # type: ignore[override]
        self._slider.setEnabled(on)
        self._label.setStyleSheet(
            f"color: {theme.current_palette().accent_soft if on else theme.current_palette().text_dim}; "
            f"background: transparent;"
        )
        self.update()

    def _slider_qss(self) -> str:
        return f"""
        QSlider::groove:horizontal {{
            height: 4px; background: rgba(255,255,255,30); border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {theme.current_palette().accent}; border-radius: 2px;
        }}
        QSlider::add-page:horizontal {{
            background: rgba(255,255,255,30); border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: #FFFFFF; width: 14px; height: 14px; margin: -6px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {theme.current_palette().accent_soft};
        }}
        QSlider::handle:horizontal:disabled {{
            background: rgba(255,255,255,80);
        }}
        """
