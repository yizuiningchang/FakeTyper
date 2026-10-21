"""视图层：主窗口、预设编辑页、设置中心等顶层视图。

- ``MainWindow``：应用主窗口（顶栏 + 总开关 + 热键面板 2×3 + 预设库 + 底栏），
  内嵌编辑页与设置页，通过通用 push/pop 栈转场切换。
- ``EditorPage``：预设编辑页（标题 + 等宽编辑器 + 字符统计 + 预估时长 +
  导入 .txt / 剪贴板粘贴 + Ctrl+S + 未保存确认条）。
- ``SettingsPage``：设置中心（左分栏导航 + 右内容堆栈，6 个分栏：
  通用 / 快捷键 / 打字 / 外观 / 数据 / 关于）。
"""
from __future__ import annotations

from .editor_page import EditorPage
from .main_window import MainWindow
from .onboarding_page import OnboardingPage
from .settings_page import SettingsPage

__all__ = ["MainWindow", "EditorPage", "SettingsPage", "OnboardingPage"]
