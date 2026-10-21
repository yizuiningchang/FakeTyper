"""超椭圆（squircle）路径工具。

普通圆角矩形在"直边↔圆角"接点处曲率突变，视觉生硬；超椭圆（squircle）
让角部沿 |cos|^(2/n)、|sin|^(2/n) 连续过渡，边缘更顺滑，是 iOS 液态玻璃
视觉的关键。本模块用"超椭圆角 + 直边"方案：四角各走一段超椭圆曲线，
边段保持直线，``radius`` 真正控制圆角大小，``n`` 控制圆润度（默认 4）。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath


def _super_point(cx: float, cy: float, r: float, t: float, n: float) -> QPointF:
    """超椭圆角上角度 t 处的坐标（相对角中心 cx,cy）。"""
    ct, st = math.cos(t), math.sin(t)
    x = cx + r * math.copysign(abs(ct) ** (2.0 / n), ct)
    y = cy + r * math.copysign(abs(st) ** (2.0 / n), st)
    return QPointF(x, y)


def squircle_path(rect: QRectF, radius: float, n: float = 4.0) -> QPainterPath:
    """构造覆盖 rect 的超椭圆路径。

    radius 控制圆角大小（≤ min(w,h)/2）；n 控制角部圆润度
    （n=2 为椭圆，n≈4 典型 squircle，n→∞ 趋近矩形）。
    """
    rect = QRectF(rect)
    w, h = rect.width(), rect.height()
    path = QPainterPath()
    if w <= 0 or h <= 0:
        return path
    r = max(0.0, min(radius, min(w, h) / 2.0))
    if r < 0.5:
        path.addRect(rect)
        return path

    x0, y0 = rect.left(), rect.top()
    samples = 14  # 每角采样数

    def arc(cx, cy, t_start, t_end) -> list[QPointF]:
        pts = []
        for i in range(1, samples + 1):
            t = t_start + (t_end - t_start) * (i / samples)
            pts.append(_super_point(cx, cy, r, t, n))
        return pts

    # 起点：顶边左端
    path.moveTo(x0 + r, y0)
    # 顶边
    path.lineTo(x0 + w - r, y0)
    # 右上角：角中心 (x0+w-r, y0+r)，从 -π/2（上）到 0（右）
    for p in arc(x0 + w - r, y0 + r, -math.pi / 2, 0.0):
        path.lineTo(p)
    # 右边
    path.lineTo(x0 + w, y0 + h - r)
    # 右下角：角中心 (x0+w-r, y0+h-r)，从 0 到 π/2
    for p in arc(x0 + w - r, y0 + h - r, 0.0, math.pi / 2):
        path.lineTo(p)
    # 底边
    path.lineTo(x0 + r, y0 + h)
    # 左下角：角中心 (x0+r, y0+h-r)，从 π/2 到 π
    for p in arc(x0 + r, y0 + h - r, math.pi / 2, math.pi):
        path.lineTo(p)
    # 左边
    path.lineTo(x0, y0 + r)
    # 左上角：角中心 (x0+r, y0+r)，从 π 到 3π/2
    for p in arc(x0 + r, y0 + r, math.pi, 3 * math.pi / 2):
        path.lineTo(p)
    path.closeSubpath()
    return path


def rounded_rect_path(rect: QRectF, radius: float) -> QPainterPath:
    """普通圆角矩形（降级备用）。"""
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path
