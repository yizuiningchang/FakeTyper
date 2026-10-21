"""主窗口：FakeTyper Pro 主界面（spec 5.2）。

布局自上而下：
1. 顶栏：图标 + 名称"FakeTyper Pro"，右侧最小化/关闭按钮（无边框窗口自实现）
2. 总开关区：大尺寸 MasterToggle + 状态文案 + 当前预设名
3. 热键面板：2×3 卡片栅格（HotkeyPanel）
4. 预设库：标题 + 数量徽标 + 搜索框 + 滚动列表（PresetLibrary）
5. 底栏：左「＋ 新建预设」主按钮，右齿轮设置按钮

主窗口为无边框 ``GlassWindow`` 子类，由顶栏拖动整体窗口。
通过 ``EngineBridge`` 接收引擎事件刷新 UI，通过 ``EngineController`` 派发动作。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets.engine_bridge import EngineBridge
from ..widgets.glass_button import GlassButton, GlassIconButton
from ..widgets.liquid_glass import GlassWindow
from ..widgets.squircle import squircle_path
from ..widgets.toast import show_toast
from .editor_page import EditorPage
from .hotkey_panel import HotkeyPanel
from .preset_library import PresetLibrary
from ...core.controller import EngineController
from ...core.typing_engine import TypingEngine
from ...data import preset_store
from ...data.config import AppConfig
from ...data.constants import Action
from ...data.paths import data_root
from ...data.preset import Preset


def _paint_icon_close(painter: QPainter, w: int, h: int) -> None:
    painter.setPen(QPen(QColor(242, 243, 251, 230), 1.4, Qt.SolidLine, Qt.RoundCap))
    m = 8
    painter.drawLine(QPointF(m, m), QPointF(w - m, h - m))
    painter.drawLine(QPointF(w - m, m), QPointF(m, h - m))


def _paint_icon_min(painter: QPainter, w: int, h: int) -> None:
    painter.setPen(QPen(QColor(242, 243, 251, 230), 1.4, Qt.SolidLine, Qt.RoundCap))
    m = 8
    painter.drawLine(QPointF(m, h / 2), QPointF(w - m, h / 2))


def _paint_icon_settings(painter: QPainter, w: int, h: int) -> None:
    """极简齿轮：圆 + 8 个齿尖。"""
    cx, cy = w / 2, h / 2
    r_outer = min(w, h) * 0.42
    r_inner = r_outer * 0.62
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(242, 243, 251, 230))
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    import math
    teeth = 8
    for i in range(teeth * 2):
        ang = i * math.pi / teeth
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + math.cos(ang) * r
        y = cy + math.sin(ang) * r
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    painter.drawPath(path)
    painter.setBrush(QColor(20, 20, 38, 230))
    painter.drawEllipse(QPointF(cx, cy), r_inner * 0.55, r_inner * 0.55)


def _paint_icon_plus(painter: QPainter, w: int, h: int) -> None:
    painter.setPen(QPen(QColor(255, 255, 255, 245), 1.6, Qt.SolidLine, Qt.RoundCap))
    m = 9
    painter.drawLine(QPointF(w / 2, m), QPointF(w / 2, h - m))
    painter.drawLine(QPointF(m, h / 2), QPointF(w - m, h / 2))


def _paint_app_logo(painter: QPainter, x: float, y: float, d: float) -> None:
    """应用图标：紫色玻璃圆 + 内嵌键盘符号。"""
    from PySide6.QtGui import QPainterPath
    rect = QRectF(x, y, d, d)
    path = squircle_path(rect, d * 0.28)
    # 主色渐变
    grad = QLinearGradient(QPointF(x, y), QPointF(x + d, y + d))
    grad.setColorAt(0.0, QColor(theme.current_palette().accent_soft))
    grad.setColorAt(1.0, QColor(theme.current_palette().accent))
    painter.setBrush(grad)
    painter.setPen(Qt.NoPen)
    painter.drawPath(path)
    # 顶光
    tg = QLinearGradient(QPointF(x, y), QPointF(x, y + d * 0.5))
    tg.setColorAt(0.0, QColor(255, 255, 255, 110))
    tg.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(x, y, d, d * 0.5), tg)
    # 键盘符号：小方块矩阵
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


class TopBar(QWidget):
    """顶栏：拖动区 + 图标/名称 + 最小化/关闭按钮。"""

    minimizeRequested = Signal()
    closeRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(48)
        self.setMouseTracking(True)
        self._drag_pos: Optional[QPoint] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 8, 8)
        layout.setSpacing(8)

        # 名称
        self._title = QLabel("FakeTyper Pro", self)
        self._title.setFont(QFont(theme.FONT_CN, 10, QFont.Bold))
        theme.style_text(self._title, "text")
        layout.addWidget(self._title)
        layout.addStretch(1)

        # 最小化
        self._min_btn = GlassIconButton(self, radius=theme.RADIUS_SMALL)
        self._min_btn.setFixedSize(30, 30)
        self._min_btn.setIconPainter(_paint_icon_min)
        self._min_btn.clicked.connect(self.minimizeRequested.emit)
        layout.addWidget(self._min_btn)

        # 关闭
        self._close_btn = GlassIconButton(self, radius=theme.RADIUS_SMALL)
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setIconPainter(_paint_icon_close)
        self._close_btn.clicked.connect(self.closeRequested.emit)
        layout.addWidget(self._close_btn)

    def paintEvent(self, e: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        # 应用图标（自绘）
        _paint_app_logo(painter, 14.0, 8.0, 32.0)
        # 标题区下方一条极细分割线
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawLine(QPointF(0, self.height() - 1), QPointF(self.width(), self.height() - 1))

    # ---- 窗口拖动 ----
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            # 仅在非按钮区开始拖动
            target = self.childAt(e.position().toPoint())
            if not isinstance(target, (GlassIconButton, QLabel)):
                win = self.window()
                if win is not None:
                    self._drag_pos = e.globalPosition().toPoint() - win.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            win = self.window()
            if win is not None:
                win.move(e.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(e)


class MasterSwitchArea(QWidget):
    """总开关区：Toggle + 状态文案 + 当前预设名。"""

    toggled = Signal(bool)
    presetDoubleClicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(92)
        self._build_ui()

    def _build_ui(self) -> None:
        from ..widgets.toggle import MasterToggle
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # 左：状态文案
        left = QVBoxLayout()
        left.setSpacing(2)
        self._status_label = QLabel("已关闭", self)
        self._status_label.setFont(QFont(theme.FONT_CN, 11, QFont.Bold))
        theme.style_text(self._status_label, "text_dim")
        self._preset_label = QLabel("未选择预设", self)
        self._preset_label.setFont(QFont(theme.FONT_CN, 9))
        theme.style_text(self._preset_label, "text_dim")
        left.addWidget(self._status_label)
        left.addWidget(self._preset_label)
        layout.addLayout(left)
        layout.addStretch(1)

        # 右：Toggle
        self._toggle = MasterToggle(self)
        self._toggle.toggled.connect(self._on_toggle)
        layout.addWidget(self._toggle, 0, Qt.AlignRight | Qt.AlignVCenter)

    def _on_toggle(self, on: bool) -> None:
        if on:
            self._status_label.setText("已激活")
            theme.style_text(self._status_label, "on")
        else:
            self._status_label.setText("已关闭")
            theme.style_text(self._status_label, "text_dim")
        self.toggled.emit(on)

    def setChecked(self, on: bool) -> None:
        self._toggle.setChecked(on)

    def isChecked(self) -> bool:
        return self._toggle.isChecked()

    def set_active_preset_name(self, name: str) -> None:
        self._preset_label.setText(name or "未选择预设")

    def toggle_widget(self):
        return self._toggle


class MainWindow(GlassWindow):
    """应用主窗口。"""

    # 对外信号
    newPresetRequested = Signal()
    settingsRequested = Signal()
    closeToTrayRequested = Signal()  # 关闭按钮 → 由 app 决定托盘/退出

    def __init__(
        self,
        engine: TypingEngine,
        controller: EngineController,
        config: AppConfig,
        bridge: EngineBridge,
    ) -> None:
        super().__init__(radius=theme.RADIUS_WINDOW)
        self._engine = engine
        self._controller = controller
        self._config = config
        self._bridge = bridge

        self.resize(theme.WINDOW_W, theme.WINDOW_H)
        self.setMinimumSize(theme.WINDOW_W - 40, theme.WINDOW_H - 80)
        self.setMaximumWidth(theme.WINDOW_W + 80)
        self.setWindowTitle("FakeTyper Pro")
        # 窗口出现淡入（先透明，启动后 220ms 内淡入到 1.0）
        self.setWindowOpacity(0.0)

        self._build_ui()
        self._wire_signals()
        self._initial_load()

        # 出现动画（窗口淡入）
        QTimer.singleShot(20, self._fade_in)

    # ---------------- UI 构建 ----------------
    def _build_ui(self) -> None:
        # 内容容器：承载 push 栈中的各页面
        self._content = QWidget(self)
        self._content.setAttribute(Qt.WA_TranslucentBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._content, 1)

        # 主页（栈底）
        self._main_page = QWidget(self._content)
        self._main_page.setAttribute(Qt.WA_TranslucentBackground, True)
        self._build_main_page()

        # 编辑页（懒 push，但提前构造以复用 M2 的引用）
        self._editor_page = EditorPage(self._content)
        self._editor_page.hide()

        # 透明度效果缓存：page -> QGraphicsOpacityEffect（push/pop 淡入淡出）
        self._effects: dict[QWidget, QGraphicsOpacityEffect] = {}
        self._main_opacity = self._ensure_opacity(self._main_page)
        self._main_opacity.setOpacity(1.0)
        self._editor_opacity = self._ensure_opacity(self._editor_page)
        self._editor_opacity.setOpacity(0.0)

        # push 栈：[page, ...]，栈底为主页
        self._page_stack: list[QWidget] = [self._main_page]
        self._settings_page = None  # 懒构造（首次进入设置页时创建）
        self._onboarding = None     # 懒构造（首启引导覆盖层）

        # 动画引用持有（防 GC）
        self._push_anim: Optional[QVariantAnimation] = None
        self._pop_anim: Optional[QVariantAnimation] = None
        self._animating = False
        self._layout_pages()

    def _ensure_opacity(self, page: QWidget) -> QGraphicsOpacityEffect:
        """为页面懒创建并挂载 QGraphicsOpacityEffect（幂等）。"""
        eff = self._effects.get(page)
        if eff is None:
            eff = QGraphicsOpacityEffect(page)
            eff.setOpacity(1.0)
            page.setGraphicsEffect(eff)
            self._effects[page] = eff
        return eff

    def _build_main_page(self) -> None:
        root = QVBoxLayout(self._main_page)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # 1. 顶栏
        self._topbar = TopBar(self._main_page)
        root.addWidget(self._topbar)

        # 2. 总开关区
        self._switch_area = MasterSwitchArea(self._main_page)
        root.addWidget(self._switch_area)

        # 3. 热键面板
        self._hotkey_panel = HotkeyPanel(self._main_page)
        root.addWidget(self._hotkey_panel)

        # 4. 预设库（伸缩）
        self._library = PresetLibrary(self._main_page)
        root.addWidget(self._library, 1)

        # 5. 底栏
        self._build_bottom_bar(root)

    def _build_bottom_bar(self, root_layout: QVBoxLayout) -> None:
        bar = QWidget(self._main_page)
        bar.setAttribute(Qt.WA_TranslucentBackground, True)
        bar.setFixedHeight(56)
        h = QHBoxLayout(bar)
        h.setContentsMargins(4, 6, 4, 6)
        h.setSpacing(8)

        # 新建预设主按钮
        self._new_btn = GlassButton(bar, text="＋  新建预设", radius=theme.RADIUS_BUTTON, accent=True)
        self._new_btn.setMinimumWidth(180)
        self._new_btn.setFixedHeight(44)
        self._new_btn.clicked.connect(self._on_new_preset)
        h.addWidget(self._new_btn, 1)

        # 设置按钮（_wire_signals 中绑定 _on_settings_requested）
        self._settings_btn = GlassIconButton(bar, radius=theme.RADIUS_BUTTON)
        self._settings_btn.setFixedSize(44, 44)
        self._settings_btn.setIconPainter(_paint_icon_settings)
        h.addWidget(self._settings_btn)

        root_layout.addWidget(bar)

    def _layout_pages(self) -> None:
        """栈内所有页面都填满 content 区（动画进行中除外，由动画驱动几何）。"""
        if not hasattr(self, "_content"):
            return
        r = self._content.rect()
        if r.isEmpty():
            return
        for page in self._page_stack:
            page.setGeometry(r)
        # 未入栈但已构造的页（编辑页/设置页）也保持尺寸，避免首次 push 时尺寸为 0
        for page in (self._editor_page, self._settings_page):
            if page is not None and page not in self._page_stack:
                page.setGeometry(r)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._layout_pages()
        if self._onboarding is not None:
            self._onboarding.setGeometry(self._content.rect())

    # ---------------- 信号绑定 ----------------
    def _wire_signals(self) -> None:
        # 顶栏
        self._topbar.minimizeRequested.connect(self.showMinimized)
        self._topbar.closeRequested.connect(self._on_close_button)
        # 总开关
        self._switch_area.toggled.connect(self._on_master_toggle)
        # 热键面板
        self._hotkey_panel.actionTriggered.connect(self._on_hotkey_action)
        # 预设库
        self._library.selected.connect(self._on_preset_selected)
        self._library.editRequested.connect(self._on_preset_edit)
        self._library.actionRequested.connect(self._on_preset_action)
        self._library.orderChanged.connect(self._on_preset_reorder)
        self._library.searchChanged.connect(self._on_search)
        # 引擎桥接
        self._bridge.mode_changed.connect(self._on_engine_mode)
        self._bridge.progress_changed.connect(self._on_engine_progress)
        self._bridge.finished.connect(self._on_engine_finished)
        self._bridge.error_occurred.connect(self._on_engine_error)
        self._bridge.preset_changed.connect(self._on_engine_preset_changed)
        # 编辑页
        self._editor_page.saveRequested.connect(self._on_editor_save)
        self._editor_page.cancelRequested.connect(self._on_editor_cancel)
        # 设置按钮（内部处理 push，对外不再 emit）
        self._settings_btn.clicked.connect(self._on_settings_requested)

    # ---------------- 初始加载 ----------------
    def _initial_load(self) -> None:
        # 热键映射
        self._hotkey_panel.set_hotkey_map(self._config.hotkey_map)
        # 总开关状态（仅 UI 反映，不真正注册热键——避免启动时偷偷激活）
        self._switch_area.setChecked(self._config.master_switch)
        # 预设列表
        self._refresh_presets()
        self._switch_area.set_active_preset_name(self._current_preset_title())
        # 控制器回调
        self._controller.set_preset_changed_callback(self._on_controller_preset_changed)
        self._controller.set_action_callback(self._on_controller_action)

    def _current_preset_title(self) -> str:
        pid = self._controller._active_id  # noqa: SLF001
        if not pid:
            return "未选择预设"
        p = preset_store.get_preset(pid)
        return p.title if p else "未选择预设"

    def _refresh_presets(self, query: str = "") -> None:
        presets = self._controller.presets
        if query:
            presets = preset_store.search(query, presets)
        self._library.set_presets(presets, active_id=self._controller._active_id)  # noqa: SLF001

    # ---------------- 用户操作 → 控制器 ----------------
    def _on_master_toggle(self, on: bool) -> None:
        if on:
            ok = self._controller.master_on()
            if ok:
                show_toast(self, "已激活，热键就绪", kind="success")
                self._hotkey_panel.set_hotkey_map(self._config.hotkey_map)
            else:
                show_toast(self, "激活失败，请查看日志", kind="error")
                self._switch_area.setChecked(False)
        else:
            self._controller.master_off()
            show_toast(self, "已关闭，热键已释放", kind="info")
            self._hotkey_panel.set_active_mode("idle")
        self._config.save()

    def _on_hotkey_action(self, action_value: str) -> None:
        # 等同于按下物理热键
        if not self._config.master_switch:
            show_toast(self, "请先开启总开关", kind="warning")
            return
        try:
            action = Action(action_value)
        except ValueError:
            return
        mapping = {
            Action.KEY_TRIGGER: self._controller.action_toggle_key,
            Action.STOP: self._controller.action_stop,
            Action.AUTO: self._controller.action_toggle_auto,
            Action.RESET: self._controller.action_reset,
            Action.RELOAD: self._controller.action_reload,
            Action.NEXT_PRESET: self._controller.action_next_preset,
        }
        cb = mapping.get(action)
        if cb:
            cb()

    def _on_preset_selected(self, preset_id: str) -> None:
        if self._controller.set_active_preset(preset_id):
            self._switch_area.set_active_preset_name(self._current_preset_title())
            self._library.set_active(preset_id)
            self._config.save()
            show_toast(self, "已切换预设", kind="info")

    def _on_preset_edit(self, preset_id: str) -> None:
        if self._animating:
            return
        p = preset_store.get_preset(preset_id)
        if p is None:
            show_toast(self, "预设不存在或已损坏", kind="error")
            return
        self._editor_page.load_preset(p, self._config.auto_speed_ms)
        self._push_page(self._editor_page)

    def _on_new_preset(self) -> None:
        if self._animating:
            return
        self._editor_page.load_new(self._config.auto_speed_ms)
        self._push_page(self._editor_page)

    # ---------------- 通用 push/pop 转场 ----------------
    def _push_page(self, page: QWidget) -> None:
        """通用 push：当前栈顶页左移淡出，新页从右滑入淡入。"""
        if self._animating:
            return
        if page in self._page_stack:
            return  # 已在栈中
        prev_page = self._page_stack[-1]
        prev_eff = self._ensure_opacity(prev_page)
        eff = self._ensure_opacity(page)
        eff.setOpacity(0.0)
        page.show()
        page.raise_()
        w = self._content.width()
        h = self._content.height()
        page.setGeometry(w, 0, w, h)
        self._animating = True
        offset = max(60, int(w * 0.3))
        a = QVariantAnimation(self)
        a.setDuration(260)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)

        def _on_val(t: float) -> None:
            prev_page.setGeometry(-int(offset * t), 0, w, h)
            prev_eff.setOpacity(max(0.0, 1.0 - t * 0.6))
            page.setGeometry(int(offset * (1 - t)), 0, w, h)
            eff.setOpacity(t)

        a.valueChanged.connect(_on_val)

        def _on_done() -> None:
            prev_page.hide()
            prev_page.setGeometry(0, 0, w, h)
            page.setGeometry(0, 0, w, h)
            prev_eff.setOpacity(1.0)
            self._page_stack.append(page)
            self._animating = False
            # 焦点交给新页（接收 Esc 等）
            page.setFocus(Qt.OtherFocusReason)

        a.finished.connect(_on_done)
        a.start()
        self._push_anim = a

    def _pop_page(self) -> None:
        """通用 pop：栈顶页右滑出淡出，前一页左滑回淡入。"""
        if self._animating:
            return
        if len(self._page_stack) <= 1:
            return  # 栈底主页不可 pop
        page = self._page_stack[-1]
        prev_page = self._page_stack[-2]
        prev_eff = self._ensure_opacity(prev_page)
        eff = self._ensure_opacity(page)
        prev_page.show()
        prev_page.raise_()
        w = self._content.width()
        h = self._content.height()
        self._animating = True
        offset = max(60, int(w * 0.3))
        a = QVariantAnimation(self)
        a.setDuration(260)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)

        def _on_val(t: float) -> None:
            prev_page.setGeometry(-int(offset * (1 - t)), 0, w, h)
            prev_eff.setOpacity(0.4 + t * 0.6)
            page.setGeometry(int(offset * t), 0, w, h)
            eff.setOpacity(1.0 - t)

        a.valueChanged.connect(_on_val)

        def _on_done() -> None:
            page.hide()
            page.setGeometry(0, 0, w, h)
            eff.setOpacity(0.0)
            self._page_stack.pop()
            self._animating = False
            prev_page.setFocus(Qt.OtherFocusReason)

        a.finished.connect(_on_done)
        a.start()
        self._pop_anim = a

    def _on_editor_save(self, preset: Preset) -> None:
        preset_store.save_preset(preset)
        self._controller.reload_presets()
        # 若当前激活预设正是被编辑的，刷新引擎内容
        if self._controller._active_id == preset.id:  # noqa: SLF001
            self._controller.action_reload()
        self._refresh_presets()
        self._library.set_active(preset.id)
        self._switch_area.set_active_preset_name(self._current_preset_title())
        self._pop_page()

    def _on_editor_cancel(self) -> None:
        self._pop_page()

    # ---------------- 设置页 ----------------
    def _on_settings_requested(self) -> None:
        """打开设置中心：懒构造 SettingsPage 并 push。"""
        if self._animating:
            return
        self._ensure_settings_page()
        # 进入设置时临时挂起功能热键，避免 F1–F6 录制时被全局钩子拦截
        try:
            self._controller.suspend_hotkeys()
        except Exception:
            pass
        self.settingsRequested.emit()
        self._push_page(self._settings_page)

    def _on_settings_close(self) -> None:
        """关闭设置中心：把改动写回 config + 重绑热键 + 引擎参数 + pop。"""
        if self._settings_page is not None:
            self._settings_page.apply_to_config()
        self._config.save()
        # 应用热键映射 + 引擎参数
        try:
            self._controller.rebind_hotkeys()
            self._controller.apply_engine_params()
        except Exception:
            pass
        # 恢复功能热键（设置页期间已 suspend）
        try:
            self._controller.resume_hotkeys()
        except Exception:
            pass
        # 主界面热键面板刷新键位
        self._hotkey_panel.set_hotkey_map(self._config.hotkey_map)
        self._pop_page()

    def _on_settings_changed(self) -> None:
        """设置页中任意项变更：实时保存 + 应用（不 pop）。
        对于打字参数立即灌入引擎；对于热键映射先不重绑（等关闭时统一重绑，
        避免录制中频繁注册）。"""
        if self._settings_page is not None:
            self._settings_page.apply_to_config()
        self._config.save()
        # 引擎参数实时生效
        try:
            self._controller.apply_engine_params()
        except Exception:
            pass

    # ---------------- 数据分栏动作（占位实现，M3-f 完善） ----------------
    def _on_open_data_dir(self) -> None:
        import os
        import subprocess
        try:
            path = str(data_root())
            if os.path.isdir(path):
                subprocess.Popen(["explorer", path])
                show_toast(self, "已打开数据目录", kind="info")
            else:
                show_toast(self, "数据目录不存在", kind="warning")
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"打开失败: {e}", kind="error")

    def _on_export_presets(self) -> None:
        # M3-f 完整实装：QFileDialog 选目录 → 打包 JSON
        show_toast(self, "导出功能即将上线（M3-f）", kind="info")

    def _on_import_presets(self) -> None:
        show_toast(self, "导入功能即将上线（M3-f）", kind="info")

    def _on_clear_presets(self) -> None:
        show_toast(self, "清空功能即将上线（M3-f）", kind="info")

    def _on_check_update(self) -> None:
        show_toast(self, "当前为开发版本", kind="info")

    def _on_preset_action(self, preset_id: str, action: str) -> None:
        if action == "pin":
            p = preset_store.get_preset(preset_id)
            if p:
                preset_store.set_pinned(preset_id, not p.pinned)
                self._refresh_presets()
                show_toast(self, "已置顶" if not p.pinned else "已取消置顶", kind="info")
        elif action == "edit":
            self._on_preset_edit(preset_id)
        elif action == "rename":
            show_toast(self, "重命名功能即将开放", kind="info")
        elif action == "copy":
            p = preset_store.get_preset(preset_id)
            if p:
                dup = Preset.create(title=f"{p.title} 副本", content=p.content)
                preset_store.save_preset(dup)
                self._refresh_presets()
                show_toast(self, "已创建副本", kind="success")
        elif action == "delete":
            # 删除需二次确认：用 QMessageBox 风格的玻璃确认框（M3）；此处先 toast + 直接删除
            preset_store.delete_preset(preset_id)
            if self._controller._active_id == preset_id:  # noqa: SLF001
                self._controller._active_id = None  # noqa: SLF001
            self._refresh_presets()
            self._switch_area.set_active_preset_name(self._current_preset_title())
            show_toast(self, "已删除（已备份）", kind="warning")

    def _on_preset_reorder(self, ordered_ids: list[str]) -> None:
        preset_store.reorder(ordered_ids)
        # 不刷新（避免抖动）；仅持久化顺序

    def _on_search(self, text: str) -> None:
        self._refresh_presets(query=text)

    def _on_close_button(self) -> None:
        # M2 阶段：直接隐藏到托盘由 app 决定；这里发信号
        self.closeToTrayRequested.emit()

    # ---------------- 控制器回调 → UI 刷新 ----------------
    def _on_controller_preset_changed(self, preset_id: Optional[str]) -> None:
        # 在 UI 线程触发刷新
        QTimer.singleShot(0, lambda: self._after_preset_changed(preset_id))

    def _after_preset_changed(self, preset_id: Optional[str]) -> None:
        self._library.set_active(preset_id)
        self._switch_area.set_active_preset_name(self._current_preset_title())

    def _on_controller_action(self, name: str) -> None:
        # 引擎模式变化后由 bridge.mode_changed 统一处理
        pass

    # ---------------- 引擎事件 → UI 刷新 ----------------
    def _on_engine_mode(self, mode: str) -> None:
        self._hotkey_panel.set_active_mode(mode)

    def _on_engine_progress(self, percent: float, current: int, total: int) -> None:
        # M3 加入细进度条；M2 暂用 toast 在 0%/50%/100% 节点提示
        pass

    def _on_engine_finished(self, reason: str) -> None:
        if reason == "completed":
            show_toast(self, "输出完毕", kind="success")
        elif reason == "stopped":
            show_toast(self, "已停止", kind="info")

    def _on_engine_error(self, message: str) -> None:
        show_toast(self, message, kind="error")

    def _on_engine_preset_changed(self, title: str, total: int) -> None:
        self._switch_area.set_active_preset_name(title)

    # ---------------- 出现动画 ----------------
    def _fade_in(self) -> None:
        from PySide6.QtCore import QVariantAnimation
        a = QVariantAnimation(self)
        a.setDuration(220)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.valueChanged.connect(self.setWindowOpacity)
        a.start()
        # 保留引用
        self._fade_anim = a  # type: ignore[attr-defined]

    # ---------------- 关闭事件 ----------------
    def closeEvent(self, e) -> None:
        # 真正退出时关闭控制器
        try:
            self._bridge.detach()
        except Exception:
            pass
        super().closeEvent(e)

    # ---------------- 对外接口 ----------------
    def hotkey_panel(self) -> HotkeyPanel:
        return self._hotkey_panel

    def library(self) -> PresetLibrary:
        return self._library

    def switch_area(self) -> MasterSwitchArea:
        return self._switch_area

    # ---------------- 首启引导 ----------------
    def show_onboarding(self) -> None:
        """显示首启引导覆盖层（懒构造）。"""
        if self._onboarding is None:
            from .onboarding_page import OnboardingPage
            self._onboarding = OnboardingPage(self._content)
            self._onboarding.finished.connect(self._on_onboarding_finished)
        self._onboarding.setGeometry(self._content.rect())
        self._onboarding.start()

    def _on_onboarding_finished(self) -> None:
        if self._onboarding is None:
            return
        self._onboarding.hide()
        self._config.onboarding_shown = True
        self._config.save()
        self._main_page.setFocus(Qt.OtherFocusReason)

    def _ensure_settings_page(self):
        """懒构造设置页（不触发 push 动画），返回构造好的实例。"""
        if self._settings_page is None:
            from .settings_page import SettingsPage
            self._settings_page = SettingsPage(self._config, self._controller, self._content)
            self._settings_page.hide()
            self._settings_page.load_from_config()
            self._settings_page.closeRequested.connect(self._on_settings_close)
            self._settings_page.configChanged.connect(self._on_settings_changed)
            self._settings_page.openDataDirRequested.connect(self._on_open_data_dir)
            self._settings_page.exportRequested.connect(self._on_export_presets)
            self._settings_page.importRequested.connect(self._on_import_presets)
            self._settings_page.clearRequested.connect(self._on_clear_presets)
            self._settings_page.checkUpdateRequested.connect(self._on_check_update)
            r = self._content.rect()
            if not r.isEmpty():
                self._settings_page.setGeometry(r)
        return self._settings_page

    def set_active_preset_name(self, name: str) -> None:
        self._switch_area.set_active_preset_name(name)
