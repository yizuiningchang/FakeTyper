"""主题与色板。

深色优先；液态玻璃配色：
- 底色深空感 #1A1A2E 系 / 卡片 #242438 系 / 主色 #7C6FF0 紫或 #2DD4BF 青；
- 玻璃材质参数：基底不透明度、模糊半径、饱和度增益、折射描边色、顶光带色、波纹光色。
按超椭圆圆角层级化方案（窗口14 / 卡片12 / 主按钮10 / 小元素8）。

M3-d 起：``ThemeManager`` 单例支持运行时切换 dark/light/system，
所有控件通过 ``theme.current_palette()`` 取当前生效 Palette（已解析 system），
主题变化时 ``themeChanged`` 信号触发所有控件 ``update()``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class Palette:
    name: str
    bg_top: str           # 窗口背景渐变顶
    bg_bottom: str        # 窗口背景渐变底
    card_tint: str        # 卡片玻璃染色（半透明叠加）
    card_tint_alpha: int  # 染色不透明度 0-255
    text: str
    text_dim: str
    divider: str          # 细分割线
    accent: str           # 主色
    accent_soft: str      # 主色柔光
    on: str               # 激活态绿
    off: str              # 待命灰
    shadow: str           # 阴影色


DARK = Palette(
    name="dark",
    bg_top="#1B1B33",
    bg_bottom="#12121F",
    card_tint="#2A2A44",
    card_tint_alpha=70,
    text="#F2F3FB",
    text_dim="#9AA0C0",
    divider="#FFFFFF",
    accent="#7C6FF0",
    accent_soft="#9D8EFF",
    on="#34D399",
    off="#5B6080",
    shadow="#000000",
)

LIGHT = Palette(
    name="light",
    bg_top="#EAECF6",
    bg_bottom="#DDE1F0",
    card_tint="#FFFFFF",
    card_tint_alpha=90,
    text="#1A1A2E",
    text_dim="#5A6080",
    divider="#000000",
    accent="#6C5CE7",
    accent_soft="#9D8EFF",
    on="#10B981",
    off="#9CA3B8",
    shadow="#000000",
)


def palette_for(theme: str) -> Palette:
    return LIGHT if theme == "light" else DARK


# 超椭圆圆角层级（squircle 半径，px）
RADIUS_WINDOW = 14
RADIUS_CARD = 12
RADIUS_BUTTON = 10
RADIUS_SMALL = 8

# 液态玻璃材质参数
GLASS_BLUR_RADIUS = 36        # 高斯模糊等效半径
GLASS_SATURATION = 0.25       # 饱和度增益
GLASS_BASE_ALPHA = 0.74       # 窗口基底不透明度
GLASS_CARD_ALPHA = 0.42       # 卡片不透明度
GLASS_EDGE_ALPHA = 90         # 折射描边不透明度 0-255
GLASS_TOP_HIGHLIGHT_ALPHA = 110  # 顶光带不透明度
GLASS_SPECULAR_ALPHA = 70     # 动态高光不透明度

# 主窗口尺寸
WINDOW_W = 400
WINDOW_H = 620

# 字体
FONT_CN = "Microsoft YaHei UI"
FONT_EN = "Inter"
FONT_MONO = "JetBrains Mono, Cascadia Code, Consolas, monospace"


def base_font(point=10) -> dict:
    return {"family": FONT_CN, "pointSize": point}


# ============================================================
# M3-d 主题管理器：运行时切换 dark/light/system
# ============================================================

class ThemeManager(QObject):
    """主题管理器（全局单例）。

    - ``raw_name``：用户选择的主题名（dark/light/system）；
    - ``resolved``：生效主题名（system 已按系统当前明暗解析为 dark/light）；
    - 主题变化时发射 ``themeChanged`` 信号（参数：resolved 名），
      全局刷新函数会遍历所有顶层 widget 触发 ``update()``。

    ``ThemeManager`` 是 QObject，需在 ``QApplication`` 实例存在后创建；
    ``manager()`` 延迟到首次调用时初始化。
    """

    themeChanged = Signal(str)  # 参数：resolved 主题名（"dark"/"light"）

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._raw_name: str = "dark"        # 用户选择
        self._system_dark: bool = True      # 系统当前是否深色
        self._resolved: str = "dark"        # 解析后生效

    # ---- 查询 ----
    @property
    def raw_name(self) -> str:
        return self._raw_name

    @property
    def resolved(self) -> str:
        return self._resolved

    def current_palette(self) -> Palette:
        return palette_for(self._resolved)

    # ---- 设置 ----
    def set_theme(self, name: str) -> None:
        """切换主题。name ∈ {dark, light, system}。"""
        if name not in ("dark", "light", "system"):
            return
        if name == self._raw_name:
            return
        self._raw_name = name
        self._recompute()

    def set_system_dark(self, is_dark: bool) -> None:
        """更新系统明暗状态（system 模式下生效）。"""
        changed = (is_dark != self._system_dark)
        self._system_dark = is_dark
        if self._raw_name == "system" and changed:
            self._recompute()

    def _recompute(self) -> None:
        if self._raw_name == "system":
            new = "dark" if self._system_dark else "light"
        else:
            new = self._raw_name
        if new != self._resolved:
            self._resolved = new
            self.themeChanged.emit(self._resolved)


_manager: Optional[ThemeManager] = None


def manager() -> ThemeManager:
    """获取全局 ThemeManager 单例（首次调用时惰性创建）。"""
    global _manager
    if _manager is None:
        _manager = ThemeManager()
        # 默认连接全局刷新：主题变化时遍历所有顶层 widget 触发 update
        _manager.themeChanged.connect(_refresh_all_widgets)
    return _manager


def current_palette() -> Palette:
    """取当前生效 Palette（已解析 system）。"""
    return manager().current_palette()


def set_theme(name: str) -> None:
    """切换主题（dark/light/system）。"""
    manager().set_theme(name)


def set_system_dark(is_dark: bool) -> None:
    """更新系统明暗状态。"""
    manager().set_system_dark(is_dark)


def current_theme_raw() -> str:
    """用户选择的主题名（可能是 system）。"""
    return manager().raw_name


def current_theme_resolved() -> str:
    """生效主题名（已解析 system）。"""
    return manager().resolved


def _refresh_all_widgets(_name: str = "") -> None:
    """主题变化时遍历所有顶层 widget 及其子 widget 触发 update()。

    QWidget.update() 是异步的、合并的，不会造成性能问题。
    GlassContainer 的 paintEvent 会重新读 current_palette()，天然动态。
    同时重新应用所有 ``style_text`` 注册的主题文字颜色（stylesheet 不会随
    update() 刷新，需显式重设）。
    """
    try:
        from PySide6.QtWidgets import QApplication, QWidget
    except Exception:  # noqa: BLE001
        return
    app = QApplication.instance()
    if app is None:
        return

    def _walk(w: QWidget) -> None:
        w.update()
        if w.property("ft_text_role") is not None:
            _restyle_text(w)
        if w.property("ft_palette_role") is not None:
            _restyle_palette(w)
        for child in w.children():
            if isinstance(child, QWidget):
                _walk(child)

    for top in app.topLevelWidgets():
        _walk(top)


# ============================================================
# 主题感知文字着色（解决 stylesheet 不随主题刷新的限制）
# ============================================================

_TEXT_ROLES = ("text", "text_dim", "on", "off", "accent")


def style_text(widget, role: str = "text", extra: str = "") -> None:
    """为 widget 设置主题文字颜色（透明背景）。

    role ∈ {text, text_dim, on, off, accent}；
    extra 为额外 qss 片段（如 ``font-size:12px;font-weight:600;``）。
    主题变化时自动重新应用（通过 ``ft_text_role`` 动态属性标记）。

    替代 ``setStyleSheet(f"color: {theme.current_palette().text}; ...")``
    的写法，使浅色/深色主题切换时 QLabel/QLineEdit 等文字颜色同步刷新。
    """
    widget.setProperty("ft_text_role", role)
    widget.setProperty("ft_text_extra", extra)
    _restyle_text(widget)


def _restyle_text(widget) -> None:
    role = widget.property("ft_text_role")
    if role is None:
        return
    pal = current_palette()
    colors = {
        "text": pal.text,
        "text_dim": pal.text_dim,
        "on": pal.on,
        "off": pal.off,
        "accent": pal.accent,
    }
    color = colors.get(role, pal.text)
    extra = widget.property("ft_text_extra") or ""
    qss = f"color: {color}; background: transparent;"
    if extra:
        qss += extra
    widget.setStyleSheet(qss)


def style_palette_text(widget, role: str = "text", placeholder_role: str = "text_dim") -> None:
    """为 QLineEdit/QPlainTextEdit 等用 QPalette 设置主题文字颜色（透明 Base）。

    主题变化时自动重新应用（通过 ``ft_palette_role`` 动态属性标记）。
    ``placeholder_role`` 设占位符颜色（传空串跳过）。替代手动
    ``pal.setColor(QPalette.Text, ...)`` 写法，使主题切换时输入控件文字
    颜色同步刷新。
    """
    widget.setProperty("ft_palette_role", role)
    widget.setProperty("ft_palette_placeholder", placeholder_role or "")
    _restyle_palette(widget)


def _restyle_palette(widget) -> None:
    role = widget.property("ft_palette_role")
    if role is None:
        return
    try:
        from PySide6.QtGui import QColor, QPalette
    except Exception:  # noqa: BLE001
        return
    pal = current_palette()
    colors = {
        "text": pal.text,
        "text_dim": pal.text_dim,
        "on": pal.on,
        "off": pal.off,
        "accent": pal.accent,
    }
    color = QColor(colors.get(role, pal.text))
    p = widget.palette()
    p.setColor(QPalette.Text, color)
    p.setColor(QPalette.Base, QColor(0, 0, 0, 0))
    ph_role = widget.property("ft_palette_placeholder")
    if ph_role:
        p.setColor(QPalette.PlaceholderText, QColor(colors.get(ph_role, pal.text_dim)))
    widget.setPalette(p)
