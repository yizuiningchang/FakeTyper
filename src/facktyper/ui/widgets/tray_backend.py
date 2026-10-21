"""托盘图标后端：状态数据 + 运行时自绘 QIcon。

不依赖资源文件，运行时用 QPainter 绘制 32×32 QPixmap：
- 超椭圆主色渐变底（与 logo 同风格）；
- 中心状态圆点：激活态绿（palette.on）/ 关闭态灰（palette.off）；
- 输出模式角标：右下角小方块，auto=绿 ▶ / key=紫 K。

用 ``theme.current_palette()`` 取色（M3-d 引入后天然跟随主题；M3-a 阶段
``current_palette`` 未引入时回退到 ``theme.DARK``）。
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRadialGradient,
)

from .. import theme
from .squircle import squircle_path


@dataclass(frozen=True)
class TrayIconState:
    """托盘图标状态快照。"""

    master_on: bool           # 总开关
    engine_mode: str          # "idle" / "key" / "auto"
    preset_title: str = ""    # 当前预设名（空=未选择）


def _palette():
    """取当前调色板。M3-d 引入 current_palette 后自动跟随主题，否则回退 DARK。"""
    if hasattr(theme, "current_palette"):
        return theme.current_palette()
    return theme.DARK


class TrayIconPainter:
    """运行时绘制托盘 QIcon QPixmap。"""

    @staticmethod
    def render(state: TrayIconState, size: int = 32) -> QPixmap:
        """绘制指定尺寸的托盘图标。"""
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)

            pal = _palette()
            pad = max(1, size // 16)
            rect = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
            radius = rect.width() * 0.32  # 圆角约为宽度的 1/3

            # 1. 超椭圆底：主色渐变
            path = squircle_path(rect, radius, n=4.0)
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(pal.accent_soft))
            grad.setColorAt(1.0, QColor(pal.accent))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawPath(path)

            # 2. 顶光带（上半部白色渐变高光，用同一超椭圆路径裁剪）
            top_rect = QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.5)
            tg = QLinearGradient(top_rect.topLeft(), top_rect.bottomLeft())
            tg.setColorAt(0.0, QColor(255, 255, 255, 95))
            tg.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.save()
            p.setClipPath(path)
            p.setBrush(tg)
            p.setPen(Qt.NoPen)
            p.drawRect(top_rect)
            p.restore()

            # 3. 中心状态圆点（激活=绿 / 关闭=灰）+ 柔光
            cx, cy = rect.center().x(), rect.center().y()
            dot_r = rect.width() * 0.11
            if state.master_on:
                glow_r = dot_r * 2.2
                glow = QRadialGradient(cx, cy, glow_r)
                on_color = QColor(pal.on)
                glow.setColorAt(0.0, QColor(on_color.red(), on_color.green(), on_color.blue(), 120))
                glow.setColorAt(1.0, QColor(on_color.red(), on_color.green(), on_color.blue(), 0))
                p.setBrush(glow)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))
                dot_color = on_color
            else:
                dot_color = QColor(pal.off)
            p.setBrush(dot_color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2))

            # 4. 输出模式角标（右下角小方块 + 符号）
            if state.engine_mode in ("key", "auto"):
                badge = rect.width() * 0.26
                bx = rect.right() - badge
                by = rect.bottom() - badge
                br = QRectF(bx, by, badge, badge)
                badge_color = QColor(pal.on) if state.engine_mode == "auto" else QColor(pal.accent_soft)
                p.setBrush(badge_color)
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(br, badge * 0.25, badge * 0.25)
                p.setPen(QColor(255, 255, 255, 245))
                fs = max(5, int(size * 0.18))
                p.setFont(QFont(theme.FONT_EN, fs, QFont.Bold))
                glyph = "▶" if state.engine_mode == "auto" else "K"
                p.drawText(br, Qt.AlignCenter, glyph)
        finally:
            p.end()
        return pm
