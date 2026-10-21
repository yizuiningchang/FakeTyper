"""液态玻璃 UI 组件包。

组件清单：
- ``GlassContainer`` / ``GlassWindow``：液态玻璃容器/根窗口（模糊+饱和+折射+顶光+动态高光）
- ``squircle_path``：超椭圆路径工具
- ``GlassButton`` / ``GlassIconButton`` / ``KeyCap``：主按钮/图标按钮/键位胶囊
- ``KeyCapButton``：可录制键帽（点击→录制→F1–F6 完成绑定）
- ``MasterToggle``：总开关（iOS 风格大 Toggle）
- ``PresetCard``：预设库列表项（玻璃卡片 + 拖拽把手 + 操作菜单）
- ``Toast`` / ``show_toast``：顶部下拉通知胶囊
- ``StatusCapsule``：浮动状态胶囊（灵动岛风格）
- ``EngineBridge``：引擎事件 → Qt 信号桥接（线程安全）
- ``RippleHostMixin``：波纹动效混入
- ``SettingRow`` / ``SegmentedControl`` / ``SliderWithLabel`` / ``ConflictDialog``：设置中心控件
"""
from __future__ import annotations

from .liquid_glass import GlassContainer, GlassWindow, make_synthetic_backdrop
from .squircle import squircle_path
from .ripple import Ripple, RippleHostMixin
from .glass_button import GlassButton, GlassIconButton, KeyCap
from .key_cap_button import KeyCapButton
from .toggle import MasterToggle
from .preset_card import PresetCard
from .toast import Toast, show_toast
from .capsule import StatusCapsule
from .engine_bridge import EngineBridge
from .setting_row import SettingRow
from .segmented_control import SegmentedControl
from .slider_with_label import SliderWithLabel
from .conflict_dialog import ConflictDialog

__all__ = [
    "GlassContainer",
    "GlassWindow",
    "make_synthetic_backdrop",
    "squircle_path",
    "Ripple",
    "RippleHostMixin",
    "GlassButton",
    "GlassIconButton",
    "KeyCap",
    "KeyCapButton",
    "MasterToggle",
    "PresetCard",
    "Toast",
    "show_toast",
    "StatusCapsule",
    "EngineBridge",
    "SettingRow",
    "SegmentedControl",
    "SliderWithLabel",
    "ConflictDialog",
]
