"""液态玻璃核心容器。

实现要点（spec 5.1）：
- 材质：半透明基底 + 强高斯模糊（半径 ~36）+ 饱和度增益（+25%）；
- 边缘折射：1–2px 内描边，颜色随背景轻微偏色；
- 顶光带：2–3px 顶白→透明渐变；
- 动态高光：光源随鼠标实时移动，基于缓存的模糊层叠加（不重算模糊）；
- 超椭圆裁剪；
- 模糊结果缓存，仅在窗口移动/背景变化时重算（防抖）；
- 抓取背景时用 Win32 ``SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)``
  临时排除自身，避免抓到自己的玻璃造成反馈累积。

``GlassWindow``（根）抓桌面背景；子 ``GlassContainer``（卡片）从根取已模糊
背景的对应子区，再叠加自身染色/高光，形成层级化玻璃。
"""
from __future__ import annotations

import ctypes
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from .. import theme
from .squircle import squircle_path

# Win32 显示亲和性（用于抓背景时排除自身窗口）
try:
    _user32 = ctypes.windll.user32
    _WDA_NONE = 0x00000000
    _WDA_EXCLUDEFROMCAPTURE = 0x00000011
    _user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _user32.SetWindowDisplayAffinity.restype = ctypes.c_bool
    _HAS_AFFINITY = True
except Exception:  # noqa: BLE001
    _HAS_AFFINITY = False


def _blur_pixmap(src: QPixmap, radius: float) -> QPixmap:
    """用 QGraphicsBlurEffect 离屏渲染高斯模糊（Qt SIMD 优化）。"""
    if src.isNull() or radius <= 0:
        return src
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(src)
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(radius)
    blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(blur)
    scene.addItem(item)
    dst = QPixmap(src.size())
    dst.fill(Qt.transparent)
    painter = QPainter(dst)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scene.render(painter, QRectF(src.rect()), QRectF(src.rect()))
    painter.end()
    return dst


def _saturate_pixmap(src: QPixmap, amount: float) -> QPixmap:
    """饱和度增益（numpy 向量化：放大 RGB 相对明度 V 的偏移）。"""
    if src.isNull() or amount == 0:
        return src
    img = src.toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    if w == 0 or h == 0:
        return src
    bpl = img.bytesPerLine()
    mv = img.bits()  # memoryview（可写）
    n = h * bpl
    arr = np.frombuffer(mv, dtype=np.uint8, count=n).astype(np.float32)
    if bpl == w * 4:
        arr = arr.reshape(h, w, 4)
    else:
        arr = arr.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    delta = mx - mn
    has = delta > 0
    # 对有色像素放大相对明度的偏移（等效提饱和），灰度像素保持
    k = 1.0 + amount
    r2 = np.where(has, np.clip(mx + (r - mx) * k, 0, 255), r)
    g2 = np.where(has, np.clip(mx + (g - mx) * k, 0, 255), g)
    b2 = np.where(has, np.clip(mx + (b - mx) * k, 0, 255), b)
    arr[:, :, 0] = r2
    arr[:, :, 1] = g2
    arr[:, :, 2] = b2
    out = arr.clip(0, 255).astype(np.uint8)
    if bpl == w * 4:
        mv[:] = out.tobytes()
    else:
        full = np.zeros((h, bpl), dtype=np.uint8)
        full[:, : w * 4] = out.reshape(h, w * 4)
        mv[:] = full.tobytes()
    return QPixmap.fromImage(img)


class GlassContainer(QWidget):
    """液态玻璃容器（可作为根窗口或子卡片）。

    子类设置 ``radius``/``tint``/``blur_radius`` 等材质参数，
    paint 时自动从最近的 ``GlassWindow`` 祖先取已模糊背景的子区并叠加玻璃质感。
    """

    def __init__(self, parent: Optional[QWidget] = None, *, radius: float = theme.RADIUS_CARD) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        # 材质参数
        self._radius = radius
        # M3-d：tint/tint_alpha 默认 None → paintEvent 读 current_palette() 动态跟随主题
        self._tint: Optional[QColor] = None
        self._tint_alpha: Optional[int] = None
        self._blur_radius = theme.GLASS_BLUR_RADIUS
        self._saturation = theme.GLASS_SATURATION
        self._base_alpha = theme.GLASS_CARD_ALPHA
        self._edge = True
        self._top_hl = True
        self._specular = True
        self._mouse_pos: Optional[QPointF] = None
        self._test_backdrop: Optional[QPixmap] = None  # 离屏测试注入

    # ---- 材质配置 ----
    def set_radius(self, r: float) -> None:
        self._radius = r
        self.update()

    def set_tint(self, color: QColor, alpha: int) -> None:
        """显式设置染色（测试注入用）；传 None color 恢复跟随主题。"""
        self._tint = QColor(color) if color is not None else None
        self._tint_alpha = alpha
        self.update()

    def set_glass_params(self, *, base_alpha: Optional[float] = None,
                        blur_radius: Optional[float] = None,
                        saturation: Optional[float] = None) -> None:
        if base_alpha is not None:
            self._base_alpha = base_alpha
        if blur_radius is not None:
            self._blur_radius = blur_radius
        if saturation is not None:
            self._saturation = saturation
        self.update()

    def set_test_backdrop(self, pm: QPixmap) -> None:
        """注入合成背景（离屏渲染验证用）。"""
        self._test_backdrop = pm
        self.update()

    # ---- 背景解析 ----
    def _root_glass(self) -> Optional["GlassWindow"]:
        p = self
        while p is not None:
            if isinstance(p, GlassWindow):
                return p
            p = p.parentWidget()
        return None

    def _resolve_backdrop(self) -> Optional[QPixmap]:
        """取本 widget 在根窗口坐标系下对应子区的已模糊背景。"""
        if self._test_backdrop is not None:
            return self._test_backdrop
        root = self._root_glass()
        if root is None:
            return None
        bd = root.backdrop()
        if bd is None or bd.isNull():
            return None
        # 映射到根窗口坐标
        top_left = self.mapTo(root, QPoint(0, 0))
        sub = QRect(top_left, self.size())
        # 裁剪到背景范围
        sub = sub.intersected(QRect(0, 0, bd.width(), bd.height()))
        if sub.isEmpty():
            return None
        return bd.copy(sub)

    # ---- 鼠标 → 动态高光 ----
    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        self._mouse_pos = e.position()
        if self._specular:
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e: QEvent) -> None:
        self._mouse_pos = None
        self.update()
        super().leaveEvent(e)

    # ---- 绘制 ----
    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)
        clip = squircle_path(rect, self._radius)
        painter.setClipPath(clip)

        # 1) 模糊背景子区
        bd = self._resolve_backdrop()
        if bd is not None and not bd.isNull():
            painter.drawPixmap(QPointF(0, 0), bd)

        # 2) 染色层（半透明主色叠加，渗入前景）
        # M3-d：未显式 set_tint 时跟随 current_palette() 动态主题
        pal = theme.current_palette()
        tint_color = self._tint if self._tint is not None else QColor(pal.card_tint)
        tint_alpha = self._tint_alpha if self._tint_alpha is not None else pal.card_tint_alpha
        tint = QColor(tint_color)
        tint.setAlpha(int(tint_alpha * self._base_alpha / 1.0))
        painter.fillRect(rect, tint)

        # 3) 动态高光（鼠标光源）
        if self._specular:
            self._paint_specular(painter, rect)

        # 4) 顶光带
        if self._top_hl:
            self._paint_top_highlight(painter, rect)

        painter.setClipping(False)

        # 5) 边缘折射描边（在裁剪外画，避免被切）
        if self._edge:
            self._paint_edge(painter, rect)

    def _paint_top_highlight(self, painter: QPainter, rect: QRectF) -> None:
        top = QPointF(rect.left(), rect.top())
        grad = QLinearGradient(top, QPointF(rect.left(), rect.top() + max(rect.height() * 0.5, 3)))
        c = QColor(255, 255, 255, theme.GLASS_TOP_HIGHLIGHT_ALPHA)
        grad.setColorAt(0.0, c)
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(
            QRectF(rect.left(), rect.top(), rect.width(), min(rect.height() * 0.18, 14)),
            grad,
        )

    def _paint_specular(self, painter: QPainter, rect: QRectF) -> None:
        if self._mouse_pos is None:
            # 居中柔和光
            cx, cy = rect.center().x(), rect.center().y()
        else:
            cx, cy = self._mouse_pos.x(), self._mouse_pos.y()
        r = max(rect.width(), rect.height()) * 0.9
        grad = QRadialGradient(QPointF(cx, cy), r)
        grad.setColorAt(0.0, QColor(255, 255, 255, theme.GLASS_SPECULAR_ALPHA))
        grad.setColorAt(0.4, QColor(255, 255, 255, int(theme.GLASS_SPECULAR_ALPHA * 0.25)))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(rect, grad)

    def _paint_edge(self, painter: QPainter, rect: QRectF) -> None:
        # 内描边：顶部偏白、底部偏主色，模拟折射
        path = squircle_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), max(self._radius - 0.5, 1))
        grad = QLinearGradient(QPointF(rect.left(), rect.top()), QPointF(rect.left(), rect.bottom()))
        grad.setColorAt(0.0, QColor(255, 255, 255, theme.GLASS_EDGE_ALPHA))
        grad.setColorAt(0.5, QColor(255, 255, 255, int(theme.GLASS_EDGE_ALPHA * 0.35)))
        grad.setColorAt(1.0, QColor(180, 180, 220, int(theme.GLASS_EDGE_ALPHA * 0.5)))
        pen = QPen(grad, 1.2)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPath(path)


class GlassWindow(GlassContainer):
    """根玻璃窗口：抓桌面背景、模糊、饱和、缓存（移动/缩放防抖重算）。

    作为无框半透明顶层窗口；子玻璃容器从它取已模糊背景子区。
    """

    def __init__(self, *, radius: float = theme.RADIUS_WINDOW) -> None:
        super().__init__(None, radius=radius)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setAutoFillBackground(False)
        # 让背景角色透明，避免 grab()/render() 的 DrawWindowBackground 填充四角
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(0, 0, 0, 0))
        self.setPalette(pal)
        # 背景
        self._base_alpha = theme.GLASS_BASE_ALPHA
        self._backdrop: Optional[QPixmap] = None
        self._recompute_timer = QTimer(self)
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(160)
        self._recompute_timer.timeout.connect(self._recompute_backdrop)
        self._synthetic: Optional[QPixmap] = None  # 测试用合成背景
        self._grabbing = False

    # ---- 背景抓取与缓存 ----
    def set_synthetic_backdrop(self, pm: Optional[QPixmap]) -> None:
        """注入合成背景（离屏渲染/无屏环境验证用）。None 恢复真实抓取。"""
        self._synthetic = pm
        self._recompute_backdrop()

    def backdrop(self) -> Optional[QPixmap]:
        return self._backdrop

    def request_recompute(self) -> None:
        """移动/缩放/背景变化时调用（防抖）。"""
        self._recompute_timer.start()

    def moveEvent(self, e) -> None:
        super().moveEvent(e)
        self.request_recompute()
        # 通知子玻璃容器重绘
        self._invalidate_children()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.request_recompute()
        self._invalidate_children()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        QTimer.singleShot(30, self._recompute_backdrop)

    def _invalidate_children(self) -> None:
        for child in self.findChildren(GlassContainer):
            child.update()

    def _recompute_backdrop(self) -> None:
        if self._grabbing:
            return
        if self._synthetic is not None:
            self._backdrop = _saturate_pixmap(_blur_pixmap(self._synthetic, self._blur_radius), self._saturation)
            self.update()
            self._invalidate_children()
            return

        screen = self.screen()
        if screen is None:
            return
        geo = self.geometry()  # 屏幕坐标
        if geo.width() <= 0 or geo.height() <= 0:
            return
        self._grabbing = True
        # 排除自身：临时设置 WDA_EXCLUDEFROMCAPTURE，刷新一帧后抓取
        hwnd = int(self.winId()) if self.winId() else 0
        if _HAS_AFFINITY and hwnd:
            _user32.SetWindowDisplayAffinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)
            # 等待一帧让合成器应用亲和性
            QTimer.singleShot(20, lambda: self._do_grab(screen, geo, hwnd))
        else:
            self._do_grab(screen, geo, hwnd)

    def _do_grab(self, screen, geo: QRect, hwnd: int) -> None:
        try:
            pm = screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
            blurred = _blur_pixmap(pm, self._blur_radius)
            self._backdrop = _saturate_pixmap(blurred, self._saturation)
        except Exception as e:  # noqa: BLE001
            from ...utils.logger import get_logger
            get_logger("glass").warning("抓取背景失败: %s", e)
            self._backdrop = None
        finally:
            if _HAS_AFFINITY and hwnd:
                _user32.SetWindowDisplayAffinity(hwnd, _WDA_NONE)
            self._grabbing = False
            self.update()
            self._invalidate_children()


def make_synthetic_backdrop(size: QSize) -> QPixmap:
    """生成一张壁纸状合成背景，用于离屏渲染验证玻璃效果。"""
    pm = QPixmap(size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    # 双色渐变 + 流动光斑
    from PySide6.QtGui import QLinearGradient, QRadialGradient
    grad = QLinearGradient(QPointF(0, 0), QPointF(size.width(), size.height()))
    grad.setColorAt(0.0, QColor("#3a2c6e"))
    grad.setColorAt(0.5, QColor("#1f2347"))
    grad.setColorAt(1.0, QColor("#0f111f"))
    painter.fillRect(pm.rect(), grad)
    for _ in range(6):
        import random
        cx = random.randint(0, size.width())
        cy = random.randint(0, size.height())
        r = random.randint(80, 200)
        g = QRadialGradient(QPointF(cx, cy), r)
        col = QColor(*random.choice([(124, 111, 240), (45, 212, 191), (236, 72, 153), (250, 204, 21)]))
        col.setAlpha(90)
        g.setColorAt(0, col)
        col2 = QColor(col)
        col2.setAlpha(0)
        g.setColorAt(1, col2)
        painter.fillRect(pm.rect(), g)
    # 网格纹理
    painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
    for x in range(0, size.width(), 28):
        painter.drawLine(x, 0, x, size.height())
    for y in range(0, size.height(), 28):
        painter.drawLine(0, y, size.width(), y)
    painter.end()
    return pm
