"""预设编辑页（spec 4.5 / 5.4）。

iOS push/pop 式内嵌页：
- 顶栏：返回箭头 + 标题（"编辑预设"/"新建预设"）+ 保存按钮
- 标题输入框（玻璃容器，单行）
- 统计行：字符数（不含换行）/ 行数 / 预估输出时长（按当前 auto_speed 换算）
- 工具行：导入 .txt 文件 / 从剪贴板一键粘贴
- 等宽多行编辑器（JetBrains Mono，保留缩进与代码格式，Tab 插入缩进）
- 底部：取消 / 保存 主按钮
- Ctrl+S 快捷保存
- dirty 检测：点返回时若有未保存修改，滑入内嵌确认条（继续编辑 / 放弃）

对外信号：
- ``saveRequested(Preset)``：用户点击保存或 Ctrl+S，携带最终 Preset（新建时已生成 id）
- ``cancelRequested()``：用户确认放弃后请求返回主页

对外接口：
- ``load_preset(preset, auto_speed_ms)``：进入编辑现有预设
- ``load_new(auto_speed_ms)``：进入新建预设
- ``get_preset()``：当前编辑的 Preset
- ``is_dirty()``：标题或内容相对载入时是否变化
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPalette,
    QPainter,
    QPaintEvent,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..widgets.glass_button import GlassButton, GlassIconButton
from ..widgets.liquid_glass import GlassContainer
from ..widgets.squircle import squircle_path
from ..widgets.toast import show_toast
from ...data.preset import Preset


# ---------------- 图标自绘 ----------------

def _paint_icon_back(painter: QPainter, w: int, h: int) -> None:
    painter.setPen(QPen(QColor(242, 243, 251, 230), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    cx, cy = w / 2.0, h / 2.0
    s = min(w, h) * 0.30
    # 左箭头 "<"
    painter.drawLine(QPointF(cx + s * 0.5, cy - s), QPointF(cx - s * 0.5, cy))
    painter.drawLine(QPointF(cx - s * 0.5, cy), QPointF(cx + s * 0.5, cy + s))


def _paint_icon_check(painter: QPainter, w: int, h: int) -> None:
    painter.setPen(QPen(QColor(255, 255, 255, 245), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    cx, cy = w / 2.0, h / 2.0
    s = min(w, h) * 0.30
    painter.drawLine(QPointF(cx - s, cy + s * 0.1), QPointF(cx - s * 0.25, cy + s * 0.7))
    painter.drawLine(QPointF(cx - s * 0.25, cy + s * 0.7), QPointF(cx + s, cy - s * 0.6))


def _paint_icon_import(painter: QPainter, w: int, h: int) -> None:
    """向下箭头（导入）。"""
    painter.setPen(QPen(QColor(242, 243, 251, 220), 1.5, Qt.SolidLine, Qt.RoundCap))
    cx, cy = w / 2.0, h / 2.0
    s = min(w, h) * 0.26
    painter.drawLine(QPointF(cx, cy - s), QPointF(cx, cy + s * 0.6))
    painter.drawLine(QPointF(cx, cy + s * 0.6), QPointF(cx - s * 0.6, cy))
    painter.drawLine(QPointF(cx, cy + s * 0.6), QPointF(cx + s * 0.6, cy))


def _paint_icon_clip(painter: QPainter, w: int, h: int) -> None:
    """剪贴板小图标。"""
    painter.setPen(QPen(QColor(242, 243, 251, 220), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    cx, cy = w / 2.0, h / 2.0
    s = min(w, h) * 0.28
    # 板身
    from PySide6.QtCore import QRectF
    painter.setBrush(QColor(242, 243, 251, 30))
    painter.drawRoundedRect(QRectF(cx - s, cy - s * 0.7, s * 2, s * 1.6), 3, 3)
    # 顶部夹子
    painter.setBrush(QColor(242, 243, 251, 90))
    painter.drawRoundedRect(QRectF(cx - s * 0.4, cy - s * 0.9, s * 0.8, s * 0.45), 2, 2)


# ---------------- 时长格式化 ----------------

def _format_duration(ms: int) -> str:
    s = max(0, ms // 1000)
    if s < 1:
        return "< 1 秒"
    if s < 60:
        return f"约 {s} 秒"
    m, s = divmod(s, 60)
    if m < 60:
        return f"约 {m} 分 {s:02d} 秒"
    h, m = divmod(m, 60)
    return f"约 {h} 时 {m:02d} 分"


# ---------------- 子组件 ----------------

class _TitleField(GlassContainer):
    """标题输入框：玻璃容器 + 单行 QLineEdit。"""

    textChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_BUTTON)
        self.setFixedHeight(38)
        self._edit = QLineEdit(self)
        self._edit.setFrame(False)
        self._edit.setPlaceholderText("预设标题…")
        self._edit.setClearButtonEnabled(True)
        self._edit.textChanged.connect(self.textChanged.emit)
        theme.style_palette_text(self._edit, "text", "text_dim")
        self._edit.setFont(QFont(theme.FONT_CN, 10, QFont.DemiBold))
        self._edit.setTextMargins(12, 0, 24, 0)
        self._edit.move(2, 2)
        self._edit.resize(self.width() - 4, self.height() - 4)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._edit.resize(self.width() - 4, self.height() - 4)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, t: str) -> None:
        self._edit.setText(t)

    def setFocus(self) -> None:  # type: ignore[override]
        self._edit.setFocus()


class _CodeEditor(GlassContainer):
    """等宽多行编辑器：玻璃容器 + QPlainTextEdit。"""

    textChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, radius=theme.RADIUS_CARD)
        self._edit = QPlainTextEdit(self)
        self._edit.setFrameStyle(QPlainTextEdit.NoFrame)
        # 透明背景融入玻璃
        self._edit.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
        theme.style_palette_text(self._edit, "text", "text_dim")
        # 等宽字体
        font = QFont(theme.FONT_MONO, 10)
        font.setStyleHint(QFont.Monospace)
        self._edit.setFont(font)
        # Tab 插入缩进而非切焦点；4 空格宽
        self._edit.setTabChangesFocus(False)
        self._edit.setTabStopDistance(40)
        self._edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        # 占位提示
        self._edit.setPlaceholderText('在此粘贴或输入要"假敲"输出的内容…支持代码、中文、标点、换行')
        self._edit.textChanged.connect(self.textChanged.emit)
        # 内边距
        self._edit.setContentsMargins(8, 8, 8, 8)
        # 用 layout 让 QPlainTextEdit 填满容器
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self._edit)

    def toPlainText(self) -> str:
        return self._edit.toPlainText()

    def setPlainText(self, t: str) -> None:
        self._edit.setPlainText(t)

    def setFocus(self) -> None:  # type: ignore[override]
        self._edit.setFocus()

    def insert_text(self, t: str) -> None:
        """在光标处插入（用于粘贴/导入追加）。"""
        cursor = self._edit.textCursor()
        cursor.insertText(t)
        self._edit.setTextCursor(cursor)

    def replace_all(self, t: str) -> None:
        """整体替换内容（导入语义）。"""
        self._edit.setPlainText(t)


class _DirtyBar(QWidget):
    """未保存修改确认条：滑入显示，提供"继续编辑 / 放弃"。"""

    continueEditing = Signal()
    discardRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(0)  # 初始折叠
        self._target_h = 40

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 4, 8, 4)
        h.setSpacing(8)

        self._label = QLabel("⚠ 有未保存的修改", self)
        self._label.setFont(QFont(theme.FONT_CN, 9, QFont.DemiBold))
        self._label.setStyleSheet(
            f"color: {theme.current_palette().text}; background: transparent;"
        )
        h.addWidget(self._label)
        h.addStretch(1)

        self._continue_btn = GlassButton(self, text="继续编辑", radius=theme.RADIUS_SMALL, accent=False)
        self._continue_btn.setFixedHeight(30)
        self._continue_btn.clicked.connect(self.continueEditing.emit)
        h.addWidget(self._continue_btn)

        self._discard_btn = GlassButton(self, text="放弃", radius=theme.RADIUS_SMALL, accent=True)
        self._discard_btn.setFixedHeight(30)
        self._discard_btn.clicked.connect(self.discardRequested.emit)
        h.addWidget(self._discard_btn)

        self._anim: Optional[QVariantAnimation] = None
        self._op_anim: Optional[QPropertyAnimation] = None
        # 透明度（配合高度滑入）
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

    def slide_in(self) -> None:
        if self._anim is not None:
            self._anim.stop()
        # 决策#6：setFixedSize 系列用 QVariantAnimation + valueChanged 更可靠
        a = QVariantAnimation(self)
        a.setDuration(220)
        a.setStartValue(float(self.height()))
        a.setEndValue(float(self._target_h))
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.valueChanged.connect(lambda v: self.setFixedHeight(int(v)))
        a.start()
        self._anim = a
        # 透明度
        op = QPropertyAnimation(self._opacity, b"opacity", self)
        op.setDuration(220)
        op.setStartValue(0.0)
        op.setEndValue(1.0)
        op.setEasingCurve(QEasingCurve.OutCubic)
        op.start()
        self._op_anim = op

    def slide_out(self) -> None:
        if self._anim is not None:
            self._anim.stop()
        a = QVariantAnimation(self)
        a.setDuration(180)
        a.setStartValue(float(self.height()))
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.InCubic)
        a.valueChanged.connect(lambda v: self.setFixedHeight(int(v)))
        a.start()
        self._anim = a
        op = QPropertyAnimation(self._opacity, b"opacity", self)
        op.setDuration(180)
        op.setStartValue(self._opacity.opacity())
        op.setEndValue(0.0)
        op.setEasingCurve(QEasingCurve.InCubic)
        op.start()
        self._op_anim = op


# ---------------- 主页面 ----------------

class EditorPage(QWidget):
    """预设编辑页。"""

    saveRequested = Signal(object)  # Preset
    cancelRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._preset: Optional[Preset] = None
        self._is_new: bool = False
        self._auto_speed_ms: int = 80
        self._init_title: str = ""
        self._init_content: str = ""

        self._build_ui()
        self._wire_signals()

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # 1. 顶栏
        topbar = QWidget(self)
        topbar.setAttribute(Qt.WA_TranslucentBackground, True)
        topbar.setFixedHeight(44)
        th = QHBoxLayout(topbar)
        th.setContentsMargins(4, 4, 4, 4)
        th.setSpacing(8)

        self._back_btn = GlassIconButton(topbar, radius=theme.RADIUS_SMALL)
        self._back_btn.setFixedSize(34, 34)
        self._back_btn.setIconPainter(_paint_icon_back)
        th.addWidget(self._back_btn)

        self._title_label = QLabel("编辑预设", topbar)
        self._title_label.setFont(QFont(theme.FONT_CN, 11, QFont.Bold))
        theme.style_text(self._title_label, "text")
        th.addWidget(self._title_label)
        th.addStretch(1)

        self._save_top_btn = GlassIconButton(topbar, radius=theme.RADIUS_SMALL)
        self._save_top_btn.setFixedSize(34, 34)
        self._save_top_btn.setIconPainter(_paint_icon_check)
        th.addWidget(self._save_top_btn)
        root.addWidget(topbar)

        # 2. 标题输入框
        self._title_field = _TitleField(self)
        root.addWidget(self._title_field)

        # 3. 统计行 + 工具行（合并到一张玻璃卡片）
        toolbox = GlassContainer(self, radius=theme.RADIUS_CARD)
        tb = QVBoxLayout(toolbox)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(6)

        # 统计行
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self._stat_chars = QLabel("字符 0")
        self._stat_lines = QLabel("行 0")
        self._stat_duration = QLabel("约 0 秒")
        for lbl in (self._stat_chars, self._stat_lines, self._stat_duration):
            lbl.setFont(QFont(theme.FONT_EN, 8, QFont.DemiBold))
            theme.style_text(lbl, "text_dim")
        # 用主色高亮数字部分：简化为整段着色
        theme.style_text(self._stat_duration, "accent")
        stats.addWidget(self._stat_chars)
        stats.addWidget(self._stat_lines)
        stats.addWidget(self._stat_duration)
        stats.addStretch(1)
        tb.addLayout(stats)

        # 工具按钮行
        tools = QHBoxLayout()
        tools.setSpacing(6)
        self._import_btn = GlassButton(toolbox, text="导入 .txt", radius=theme.RADIUS_SMALL, accent=False)
        self._import_btn.setFixedHeight(30)
        self._paste_btn = GlassButton(toolbox, text="从剪贴板粘贴", radius=theme.RADIUS_SMALL, accent=False)
        self._paste_btn.setFixedHeight(30)
        tools.addWidget(self._import_btn)
        tools.addWidget(self._paste_btn)
        tools.addStretch(1)
        tb.addLayout(tools)
        root.addWidget(toolbox)

        # 4. 编辑器（伸缩）
        self._editor = _CodeEditor(self)
        root.addWidget(self._editor, 1)

        # 5. dirty 确认条（默认折叠）
        self._dirty_bar = _DirtyBar(self)
        root.addWidget(self._dirty_bar)

        # 6. 底栏
        bottom = QWidget(self)
        bottom.setAttribute(Qt.WA_TranslucentBackground, True)
        bottom.setFixedHeight(56)
        bh = QHBoxLayout(bottom)
        bh.setContentsMargins(4, 6, 4, 6)
        bh.setSpacing(8)

        self._cancel_btn = GlassButton(bottom, text="取消", radius=theme.RADIUS_BUTTON, accent=False)
        self._cancel_btn.setFixedHeight(44)
        bh.addWidget(self._cancel_btn, 1)

        self._save_btn = GlassButton(bottom, text="保存预设", radius=theme.RADIUS_BUTTON, accent=True)
        self._save_btn.setFixedHeight(44)
        bh.addWidget(self._save_btn, 1)
        root.addWidget(bottom)

    def _wire_signals(self) -> None:
        # 返回 / 取消
        self._back_btn.clicked.connect(self._on_back)
        self._cancel_btn.clicked.connect(self._on_back)
        # 保存
        self._save_btn.clicked.connect(self._on_save)
        self._save_top_btn.clicked.connect(self._on_save)
        # Ctrl+S
        sc = QShortcut(QKeySequence("Ctrl+S"), self)
        sc.activated.connect(self._on_save)
        # 实时统计
        self._title_field.textChanged.connect(self._update_stats)
        self._editor.textChanged.connect(self._update_stats)
        # 导入 / 粘贴
        self._import_btn.clicked.connect(self.on_import_file)
        self._paste_btn.clicked.connect(self.on_paste_clipboard)
        # dirty 确认条
        self._dirty_bar.continueEditing.connect(self._dirty_bar.slide_out)
        self._dirty_bar.discardRequested.connect(self._do_cancel)

    # ---------------- 对外接口 ----------------
    def load_preset(self, preset: Preset, auto_speed_ms: int) -> None:
        self._preset = preset
        self._is_new = False
        self._auto_speed_ms = auto_speed_ms
        self._init_title = preset.title
        self._init_content = preset.content
        self._title_label.setText("编辑预设")
        self._title_field.setText(preset.title)
        self._editor.setPlainText(preset.content)
        self._hide_dirty_silent()
        self._update_stats()
        # 焦点落到编辑器
        QTimer.singleShot(60, self._editor.setFocus)

    def load_new(self, auto_speed_ms: int) -> None:
        self._preset = Preset.create("", "")
        self._is_new = True
        self._auto_speed_ms = auto_speed_ms
        self._init_title = ""
        self._init_content = ""
        self._title_label.setText("新建预设")
        self._title_field.setText("")
        self._editor.setPlainText("")
        self._hide_dirty_silent()
        self._update_stats()
        QTimer.singleShot(60, self._title_field.setFocus)

    def get_preset(self) -> Preset:
        assert self._preset is not None
        self._preset.title = self._title_field.text().strip() or "未命名预设"
        self._preset.content = self._editor.toPlainText()
        return self._preset

    def is_dirty(self) -> bool:
        if self._preset is None:
            return False
        return (
            self._title_field.text() != self._init_title
            or self._editor.toPlainText() != self._init_content
        )

    # ---------------- 内部逻辑 ----------------
    def _hide_dirty_silent(self) -> None:
        """重置时静默隐藏确认条（无动画）。"""
        self._dirty_bar.setFixedHeight(0)
        self._dirty_bar._opacity.setOpacity(0.0)  # type: ignore[attr-defined]

    def _on_back(self) -> None:
        if self.is_dirty():
            # 显示确认条
            self._dirty_bar.slide_in()
        else:
            self._do_cancel()

    def _do_cancel(self) -> None:
        self._hide_dirty_silent()
        self.cancelRequested.emit()

    def _on_save(self) -> None:
        if self._preset is None:
            return
        preset = self.get_preset()
        # 标题校验：空标题用"未命名预设"
        if not preset.title.strip():
            preset.title = "未命名预设"
        # 内容为空提示但允许保存（可能用户只想先建标题）
        self._init_title = preset.title
        self._init_content = preset.content
        self._hide_dirty_silent()
        if self._is_new:
            self._is_new = False
            self._title_label.setText("编辑预设")
        self.saveRequested.emit(preset)
        show_toast(self, "已保存预设", kind="success")

    def _update_stats(self) -> None:
        text = self._editor.toPlainText()
        chars = len(text.replace("\n", "").replace("\r", ""))
        lines = text.count("\n") + (1 if text else 0)
        total = len(text)
        # 预估时长：用 total_chars（含换行，因为换行也要输出 Enter）
        ms = max(total, 1) * self._auto_speed_ms
        self._stat_chars.setText(f"字符 {chars}")
        self._stat_lines.setText(f"行 {lines}")
        self._stat_duration.setText(_format_duration(ms))

    # ---------------- 导入 / 粘贴 ----------------
    def on_import_file(self) -> None:
        """弹出文件选择，导入 .txt 内容到编辑器（整体替换）。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择要导入的文本文件", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if not path:
            return
        try:
            # 尝试 utf-8，失败回退 gbk
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(path, "r", encoding="gbk", errors="replace") as f:
                    content = f.read()
        except OSError as e:
            show_toast(self, f"导入失败：{e}", kind="error")
            return
        self._editor.replace_all(content)
        show_toast(self, "已导入文件内容", kind="success")

    def on_paste_clipboard(self) -> None:
        """从剪贴板粘贴到编辑器光标处。"""
        text = QApplication.clipboard().text()
        if not text:
            show_toast(self, "剪贴板为空", kind="warning")
            return
        self._editor.insert_text(text)
        show_toast(self, "已粘贴剪贴板内容", kind="success")

    # ---------------- 事件 ----------------
    def keyPressEvent(self, e) -> None:
        # Esc → 触发返回（与点返回按钮一致）
        if e.key() == Qt.Key_Escape:
            self._on_back()
            return
        super().keyPressEvent(e)
