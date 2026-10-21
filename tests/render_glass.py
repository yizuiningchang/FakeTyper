"""液态玻璃离屏渲染验证（无需真实屏幕）。

用合成背景注入 GlassWindow，渲染窗口 + 一张子卡片到 PNG，
校验输出非空白、有像素方差（玻璃质感已绘制），并保存预览图供人工查看。

运行：python tests\render_glass.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtCore import QPoint, QRect, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from facktyper.ui import theme  # noqa: E402
from facktyper.ui.widgets.liquid_glass import GlassContainer, GlassWindow, make_synthetic_backdrop  # noqa: E402
from facktyper.ui.widgets.squircle import squircle_path  # noqa: E402


def render() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = GlassWindow()
    win.resize(theme.WINDOW_W, theme.WINDOW_H)
    bd = make_synthetic_backdrop(QSize(theme.WINDOW_W, theme.WINDOW_H))
    win.set_synthetic_backdrop(bd)

    # 一张子玻璃卡片
    card = GlassContainer(win, radius=theme.RADIUS_CARD)
    card.setGeometry(60, 120, 280, 120)
    card.set_tint(QColor(theme.DARK.card_tint), theme.DARK.card_tint_alpha)

    # 另一张更小的
    card2 = GlassContainer(win, radius=theme.RADIUS_BUTTON)
    card2.setGeometry(60, 280, 130, 80)
    card2.set_tint(QColor("#2DD4BF"), 60)

    win.show()
    app.processEvents()

    out = os.path.join(os.path.dirname(__file__), "..", "_glass_preview.png")
    pix = win.grab()
    pix.save(out)
    print(f"已保存预览: {os.path.abspath(out)}  尺寸={pix.size().width()}x{pix.size().height()}")

    # 校验非空白 + 像素方差
    img = pix.toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    import numpy as np

    mv = img.bits()
    arr = np.frombuffer(mv, dtype=np.uint8, count=h * bpl)
    if bpl == w * 4:
        arr = arr.reshape(h, w, 4)
    else:
        arr = arr.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4)
    non_transparent = (arr[:, :, 3] > 10).sum()
    var = float(arr[:, :, :3].std())
    print(f"非透明像素={non_transparent}  RGB 标准差={var:.2f}")
    assert non_transparent > 1000, "渲染几乎全透明"
    assert var > 5.0, f"像素方差过低，可能未绘制内容: {var}"
    print("[OK] 玻璃已渲染、有质感方差")
    return 0


if __name__ == "__main__":
    raise SystemExit(render())
