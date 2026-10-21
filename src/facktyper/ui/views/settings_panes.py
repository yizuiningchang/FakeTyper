"""设置中心分栏面板（spec 4.6）。

6 个分栏：
- ``GeneralPane``：启动状态 / 开机自启 / 关闭行为
- ``HotkeysPane``：F1–F6 录制式绑定（M3-b 占位只读，M3-c 实装录制）
- ``TypingPane``：自动速度 / 每按键字符数 / 人性化抖动 / 抖动幅度 / 随机字符 / 标点停顿
- ``AppearancePane``：主题深色/浅色/跟随系统（M3-b 仅存值，M3-d 实装运行时切换）
- ``DataPane``：打开数据目录 / 导出 / 导入 / 清空（M3-b 仅打开目录，M3-f 实装其余）
- ``AboutPane``：版本号 / 检查更新占位 / 开源许可占位

各 Pane 通过 ``changed`` 信号通知设置变更（由 SettingsPage 转发为 configChanged）。
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...core import autostart
from ...core.controller import EngineController
from ...data.config import AppConfig
from ...data.constants import Action, default_hotkey_map
from ...data.paths import data_root
from .. import theme
from ..widgets.glass_button import GlassButton
from ..widgets.segmented_control import SegmentedControl
from ..widgets.setting_row import SettingRow
from ..widgets.slider_with_label import SliderWithLabel
from ..widgets.toggle import MasterToggle

# 主题映射
_THEME_LABELS = ["深色", "浅色", "跟随系统"]
_THEME_VALUES = ["dark", "light", "system"]


class _MiniToggle(MasterToggle):
    """设置项用的小尺寸 Toggle（缩放 MasterToggle 几何）。"""

    TRACK_W = 52.0
    TRACK_H = 28.0
    KNOB_D = 22.0
    PADDING = 3.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(52, 28)


class _BasePane(QWidget):
    """分栏基类：标题 + 内容区。"""

    changed = Signal()

    def __init__(self, config: AppConfig, controller: EngineController, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._config = config
        self._controller = controller
        self._loading = False

        v = QVBoxLayout(self)
        v.setContentsMargins(2, 6, 2, 6)
        v.setSpacing(8)
        self._title_lbl = QLabel(self._pane_title(), self)
        self._title_lbl.setFont(QFont(theme.FONT_CN, 11, QFont.Bold))
        theme.style_text(self._title_lbl, "text")
        v.addWidget(self._title_lbl)

        self._host = QWidget(self)
        self._host.setAttribute(Qt.WA_TranslucentBackground, True)
        self._lay = QVBoxLayout(self._host)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(8)
        v.addWidget(self._host, 1)

        self._build()
        self.load()

    # 子类覆盖
    def _pane_title(self) -> str:
        return ""

    def _build(self) -> None:
        pass

    def load(self) -> None:
        pass

    def apply(self) -> None:
        pass

    # ---- 辅助 ----
    def _emit_changed(self) -> None:
        if not self._loading:
            self.changed.emit()


# ---------------- 通用 ----------------
class GeneralPane(_BasePane):
    def _pane_title(self) -> str:
        return "通用"

    def _build(self) -> None:
        # 启动时主窗口状态
        self._startup_seg = SegmentedControl(["最小化", "正常", "最大化"], self._host)
        self._startup_seg.currentChanged.connect(lambda i: self._emit_changed())
        self._startup_row = SettingRow(
            "启动时显示", "软件启动时主窗口状态", self._startup_seg, self._host
        )
        self._lay.addWidget(self._startup_row)

        # 开机自启
        self._autostart_tg = _MiniToggle(self._host)
        self._autostart_tg.toggled.connect(self._on_autostart)
        self._autostart_row = SettingRow(
            "开机自启", "登录 Windows 时自动启动", self._autostart_tg, self._host
        )
        self._lay.addWidget(self._autostart_row)

        # 关闭按钮行为
        self._close_seg = SegmentedControl(["最小化到托盘", "直接退出"], self._host)
        self._close_seg.currentChanged.connect(lambda i: self._emit_changed())
        self._close_row = SettingRow(
            "关闭按钮行为", "点击关闭按钮时的行为", self._close_seg, self._host
        )
        self._lay.addWidget(self._close_row)
        self._lay.addStretch(1)

    def load(self) -> None:
        self._loading = True
        s_map = {"minimized": 0, "normal": 1, "maximized": 2}
        self._startup_seg.setCurrentIndex(s_map.get(self._config.startup_window_state, 0), animate=False)
        c_map = {"tray": 0, "quit": 1}
        self._close_seg.setCurrentIndex(c_map.get(self._config.close_behavior, 0), animate=False)
        self._autostart_tg.setChecked(self._config.auto_start, animate=False)
        self._loading = False

    def apply(self) -> None:
        s_vals = ["minimized", "normal", "maximized"]
        self._config.startup_window_state = s_vals[self._startup_seg.currentIndex()]
        c_vals = ["tray", "quit"]
        self._config.close_behavior = c_vals[self._close_seg.currentIndex()]
        # auto_start 由 toggle 回调即时同步

    def _on_autostart(self, on: bool) -> None:
        if self._loading:
            return
        self._config.auto_start = on
        autostart.sync_to_registry(on)
        self._emit_changed()


# ---------------- 打字 ----------------
class TypingPane(_BasePane):
    def _pane_title(self) -> str:
        return "打字"

    def _build(self) -> None:
        # 自动速度
        self._speed_sld = SliderWithLabel(10, 2000, 80, unit="ms", step=10, parent=self._host)
        self._speed_sld.valueChanged.connect(lambda v: self._emit_changed())
        self._lay.addWidget(SettingRow("自动模式速度", "自动匀速输出每字间隔", self._speed_sld, self._host))

        # 每按键字符数
        self._cpk_seg = SegmentedControl(["1", "2", "3", "4", "5"], self._host)
        self._cpk_seg.currentChanged.connect(lambda i: self._emit_changed())
        self._lay.addWidget(SettingRow("每按键字符数", "按键触发模式每次输出字符数", self._cpk_seg, self._host))

        # 人性化抖动
        self._jitter_tg = _MiniToggle(self._host)
        self._jitter_tg.toggled.connect(self._on_jitter_toggled)
        self._lay.addWidget(SettingRow("人性化抖动", "自动模式随机抖动间隔", self._jitter_tg, self._host))

        # 抖动幅度
        self._jamount_sld = SliderWithLabel(0, 100, 30, unit="%", step=5, parent=self._host)
        self._jamount_sld.valueChanged.connect(lambda v: self._emit_changed())
        self._jamount_row = SettingRow("抖动幅度", "抖动相对基准的百分比", self._jamount_sld, self._host)
        self._lay.addWidget(self._jamount_row)

        # 随机字符数
        self._rand_tg = _MiniToggle(self._host)
        self._rand_tg.toggled.connect(lambda on: self._emit_changed())
        self._lay.addWidget(SettingRow("随机字符数", "按键模式每次输出 1–3 个字符", self._rand_tg, self._host))

        # 标点停顿
        self._punc_tg = _MiniToggle(self._host)
        self._punc_tg.toggled.connect(lambda on: self._emit_changed())
        self._lay.addWidget(SettingRow("标点停顿", "遇逗号/句号/换行额外停顿", self._punc_tg, self._host))

        # 思考停顿
        self._think_tg = _MiniToggle(self._host)
        self._think_tg.toggled.connect(lambda on: self._emit_changed())
        self._lay.addWidget(SettingRow("思考停顿", "低概率插入长停顿模拟真人思考", self._think_tg, self._host))
        self._lay.addStretch(1)

    def load(self) -> None:
        self._loading = True
        self._speed_sld.setValue(self._config.auto_speed_ms)
        self._cpk_seg.setCurrentIndex(self._config.chars_per_keypress - 1, animate=False)
        self._jitter_tg.setChecked(self._config.humanize_jitter, animate=False)
        self._jamount_sld.setValue(int(round(self._config.jitter_amount * 100)))
        self._rand_tg.setChecked(self._config.chars_per_keypress_random, animate=False)
        self._punc_tg.setChecked(self._config.punctuation_pause, animate=False)
        self._think_tg.setChecked(self._config.humanize_thinking_pause, animate=False)
        self._jamount_sld.setEnabled(self._config.humanize_jitter)
        self._loading = False

    def apply(self) -> None:
        self._config.auto_speed_ms = self._speed_sld.value()
        self._config.chars_per_keypress = self._cpk_seg.currentIndex() + 1
        self._config.humanize_jitter = self._jitter_tg.isChecked()
        self._config.jitter_amount = self._jamount_sld.value() / 100.0
        self._config.chars_per_keypress_random = self._rand_tg.isChecked()
        self._config.punctuation_pause = self._punc_tg.isChecked()
        self._config.humanize_thinking_pause = self._think_tg.isChecked()

    def _on_jitter_toggled(self, on: bool) -> None:
        self._jamount_sld.setEnabled(on)
        self._emit_changed()


# ---------------- 外观 ----------------
class AppearancePane(_BasePane):
    def _pane_title(self) -> str:
        return "外观"

    def _build(self) -> None:
        self._theme_seg = SegmentedControl(_THEME_LABELS, self._host)
        self._theme_seg.currentChanged.connect(self._on_theme_seg_changed)
        self._lay.addWidget(SettingRow("主题", "深色 / 浅色 / 跟随系统", self._theme_seg, self._host))
        self._lay.addStretch(1)

    def _on_theme_seg_changed(self, idx: int) -> None:
        if self._loading:
            return
        # M3-d：实时应用主题（写 config + 通知 ThemeManager 刷新所有控件）
        name = _THEME_VALUES[idx]
        self._config.theme = name
        theme.set_theme(name)
        self._emit_changed()

    def load(self) -> None:
        self._loading = True
        idx = _THEME_VALUES.index(self._config.theme) if self._config.theme in _THEME_VALUES else 0
        self._theme_seg.setCurrentIndex(idx, animate=False)
        self._loading = False

    def apply(self) -> None:
        self._config.theme = _THEME_VALUES[self._theme_seg.currentIndex()]
        # 确保主题已应用（load 时若用户未点过分段，set_theme 也幂等）
        theme.set_theme(self._config.theme)


# ---------------- 快捷键（M3-c 实装录制式绑定） ----------------
class HotkeysPane(_BasePane):
    """F1–F6 录制式绑定 + 冲突交换处理。

    每个 KeyCapButton 点击后进入录制态，按 F1–F6 完成绑定。
    若按下的键已被其他功能占用，用 ``config.set_hotkey`` 自动交换
    （交换在底层完成，本面板只需刷新全部按钮显示）。
    """

    def _pane_title(self) -> str:
        return "快捷键"

    def _build(self) -> None:
        from ..widgets.key_cap_button import KeyCapButton

        self._cap_buttons: list[KeyCapButton] = []
        for action in Action:
            btn = KeyCapButton(
                action_value=action.value,
                current_key=self._config.key_for(action.value),
                parent=self._host,
            )
            btn.keyRecorded.connect(self._on_key_recorded)
            self._cap_buttons.append(btn)
            self._lay.addWidget(SettingRow(action.label, "点击键帽后按 F1–F6 重新绑定", btn, self._host))

        self._reset_btn = GlassButton(self._host, text="恢复默认", radius=theme.RADIUS_BUTTON, accent=False)
        self._reset_btn.setFixedHeight(36)
        self._reset_btn.clicked.connect(self._on_reset)
        self._lay.addWidget(self._reset_btn)
        self._lay.addStretch(1)

    def load(self) -> None:
        self._loading = True
        for action, btn in zip(Action, self._cap_buttons):
            btn.setKey(self._config.key_for(action.value))
        self._loading = False

    def apply(self) -> None:
        # 键位变更已由 _on_key_recorded 即时写入 config，apply 无需再处理
        pass

    def _on_key_recorded(self, action_value: str, key: str) -> None:
        """KeyCapButton 录制到合法键：写入 config（自动交换冲突） + 刷新全部按钮。"""
        if self._loading:
            return
        # 检查是否发生交换
        conflict_action = None
        for a, k in self._config.hotkey_map.items():
            if k == key and a != action_value:
                conflict_action = a
                break
        # set_hotkey 自动交换
        self._config.set_hotkey(action_value, key)
        # 刷新全部按钮（交换后另一个按钮的键也变了）
        self.load()
        self._emit_changed()
        # 如果发生交换，提示用户
        if conflict_action:
            from ..widgets.toast import show_toast
            # 找到被交换的功能名
            try:
                conflict_label = Action(conflict_action).label
                current_label = Action(action_value).label
                show_toast(
                    self.window() or self,
                    f"「{current_label}」与「{conflict_label}」键位已交换",
                    kind="info",
                )
            except ValueError:
                pass

    def _on_reset(self) -> None:
        if self._loading:
            return
        # 一键恢复默认映射
        self._config.hotkey_map = default_hotkey_map()
        self.load()
        self._emit_changed()


# ---------------- 数据（M3-b 部分实装，M3-f 完整） ----------------
class DataPane(_BasePane):
    openDataDirRequested = Signal()
    exportRequested = Signal()
    importRequested = Signal()
    clearRequested = Signal()

    def _pane_title(self) -> str:
        return "数据"

    def _build(self) -> None:
        self._open_dir_btn = GlassButton(self._host, text="打开数据目录", radius=theme.RADIUS_BUTTON, accent=False)
        self._open_dir_btn.setFixedHeight(36)
        self._open_dir_btn.clicked.connect(self.openDataDirRequested.emit)
        self._lay.addWidget(self._open_dir_btn)

        self._export_btn = GlassButton(self._host, text="导出全部预设", radius=theme.RADIUS_BUTTON, accent=False)
        self._export_btn.setFixedHeight(36)
        self._export_btn.clicked.connect(self.exportRequested.emit)
        self._lay.addWidget(self._export_btn)

        self._import_btn = GlassButton(self._host, text="导入预设", radius=theme.RADIUS_BUTTON, accent=False)
        self._import_btn.setFixedHeight(36)
        self._import_btn.clicked.connect(self.importRequested.emit)
        self._lay.addWidget(self._import_btn)

        self._clear_btn = GlassButton(self._host, text="清空全部预设", radius=theme.RADIUS_BUTTON, accent=False)
        self._clear_btn.setFixedHeight(36)
        self._clear_btn.clicked.connect(self.clearRequested.emit)
        self._lay.addWidget(self._clear_btn)
        self._lay.addStretch(1)

    def load(self) -> None:
        pass

    def apply(self) -> None:
        pass


# ---------------- 关于（M3-b 部分实装，M3-f 完整） ----------------
class AboutPane(_BasePane):
    checkUpdateRequested = Signal()

    def _pane_title(self) -> str:
        return "关于"

    def _build(self) -> None:
        try:
            from ...__init__ import __version__ as ver  # type: ignore
        except Exception:  # noqa: BLE001
            ver = "1.0.0"
        self._name_lbl = QLabel("FakeTyper Pro", self._host)
        self._name_lbl.setFont(QFont(theme.FONT_CN, 14, QFont.Bold))
        theme.style_text(self._name_lbl, "text")
        self._name_lbl.setAlignment(Qt.AlignCenter)
        self._lay.addWidget(self._name_lbl)

        self._ver_lbl = QLabel(f"版本 {ver}", self._host)
        self._ver_lbl.setFont(QFont(theme.FONT_EN, 9))
        theme.style_text(self._ver_lbl, "text_dim")
        self._ver_lbl.setAlignment(Qt.AlignCenter)
        self._lay.addWidget(self._ver_lbl)

        self._check_btn = GlassButton(self._host, text="检查更新", radius=theme.RADIUS_BUTTON, accent=False)
        self._check_btn.setFixedHeight(36)
        self._check_btn.clicked.connect(self.checkUpdateRequested.emit)
        self._lay.addWidget(self._check_btn)

        self._note = QLabel("数据目录：" + str(data_root()), self._host)
        self._note.setFont(QFont(theme.FONT_CN, 8))
        theme.style_text(self._note, "text_dim")
        self._note.setWordWrap(True)
        self._lay.addWidget(self._note)
        self._lay.addStretch(1)

    def load(self) -> None:
        pass

    def apply(self) -> None:
        pass
