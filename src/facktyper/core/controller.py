"""引擎控制器：桥接热键 → 引擎动作、预设管理与总开关。

职责：
- 总开关开启时：按配置热键映射注册 F1–F6，注入人性化参数到引擎；
- 总开关关闭时：注销全部热键，停止输出，软件完全不影响系统输入；
- 动作映射：F1 按键触发 / F2 急停 / F3 自动 / F4 重置 / F5 重载 / F6 切换下一预设；
- 预设管理：激活、重载、循环切换、持久化 last_used。
"""
from __future__ import annotations

from typing import Callable

from ..data import preset_store
from ..data.config import AppConfig
from ..data.constants import Action
from ..utils.logger import get_logger
from .hotkey_manager import HotkeyManager
from .typing_engine import TypingEngine

_log = get_logger("controller")


class EngineController:
    def __init__(
        self,
        engine: TypingEngine,
        hotkey: HotkeyManager,
        config: AppConfig,
    ) -> None:
        self._engine = engine
        self._hotkey = hotkey
        self._config = config
        self._presets: list = []
        self._active_id: str | None = None
        self._on_preset_changed: Callable[[str | None], None] | None = None
        self._on_action: Callable[[str], None] | None = None

    # ---------------- 钩子 ----------------

    def set_preset_changed_callback(self, cb: Callable[[str | None], None]) -> None:
        self._on_preset_changed = cb

    def set_action_callback(self, cb: Callable[[str], None]) -> None:
        """每次热键动作触发时回调（用于 UI 状态刷新）。"""
        self._on_action = cb

    def _fire_action(self, name: str) -> None:
        if self._on_action:
            try:
                self._on_action(name)
            except Exception as e:  # noqa: BLE001
                _log.exception("action 回调异常: %s", e)

    # ---------------- 预设 ----------------

    def reload_presets(self) -> list:
        self._presets = preset_store.list_presets()
        return self._presets

    @property
    def presets(self) -> list:
        if not self._presets:
            self.reload_presets()
        return self._presets

    def set_active_preset(self, preset_id: str) -> bool:
        p = preset_store.get_preset(preset_id)
        if p is None:
            _log.warning("预设不存在: %s", preset_id)
            return False
        self._active_id = preset_id
        self._engine.set_content(p.content, p.title)
        preset_store.mark_used(preset_id)
        self._config.last_active_preset_id = preset_id
        if self._on_preset_changed:
            self._on_preset_changed(preset_id)
        return True

    def _ensure_active(self) -> None:
        if self._active_id is None or not any(p.id == self._active_id for p in self.presets):
            if self.presets:
                self.set_active_preset(self.presets[0].id)
            else:
                sample = preset_store.ensure_default_preset()
                if sample:
                    self.reload_presets()
                    self.set_active_preset(sample.id)

    # ---------------- 动作 ----------------

    def action_toggle_key(self) -> None:
        self._engine.toggle_key_mode()
        self._fire_action(Action.KEY_TRIGGER.value)

    def action_toggle_auto(self) -> None:
        self._engine.toggle_auto_mode()
        self._fire_action(Action.AUTO.value)

    def action_stop(self) -> None:
        self._engine.stop_all()
        self._fire_action(Action.STOP.value)

    def action_reset(self) -> None:
        self._engine.reset()
        self._fire_action(Action.RESET.value)

    def action_reload(self) -> None:
        if self._active_id:
            p = preset_store.get_preset(self._active_id)
            if p:
                self._engine.set_content(p.content, p.title)
                _log.info("已重新加载预设: %s", p.title)
        self._fire_action(Action.RELOAD.value)

    def action_next_preset(self) -> None:
        if not self.presets:
            self._ensure_active()
            return
        ids = [p.id for p in self.presets]
        if not ids:
            return
        if self._active_id in ids:
            i = ids.index(self._active_id)
            nxt = ids[(i + 1) % len(ids)]
        else:
            nxt = ids[0]
        self.set_active_preset(nxt)
        self._fire_action(Action.NEXT_PRESET.value)

    # ---------------- 总开关 ----------------

    def master_on(self) -> bool:
        """开启待命：注册全部功能热键。"""
        try:
            self._engine.apply_params(
                auto_speed_ms=self._config.auto_speed_ms,
                humanize_jitter=self._config.humanize_jitter,
                jitter_amount=self._config.jitter_amount,
                punctuation_pause=self._config.punctuation_pause,
                chars_per_keypress=self._config.chars_per_keypress,
                chars_per_keypress_random=self._config.chars_per_keypress_random,
                humanize_thinking_pause=self._config.humanize_thinking_pause,
            )
            self._ensure_active()
            self._register_hotkeys()
            self._config.master_switch = True
            return True
        except Exception as e:  # noqa: BLE001
            _log.exception("开启总开关失败: %s", e)
            return False

    def master_off(self) -> None:
        """关闭待命：停止输出、注销热键，系统输入完全不受影响。"""
        self._engine.stop_all()
        self._hotkey.unregister_all_functions()
        self._config.master_switch = False

    def _register_hotkeys(self) -> None:
        self._hotkey.unregister_all_functions()
        mapping = {
            Action.KEY_TRIGGER.value: self.action_toggle_key,
            Action.STOP.value: self.action_stop,
            Action.AUTO.value: self.action_toggle_auto,
            Action.RESET.value: self.action_reset,
            Action.RELOAD.value: self.action_reload,
            Action.NEXT_PRESET.value: self.action_next_preset,
        }
        for action_value, cb in mapping.items():
            key = self._config.key_for(action_value)
            if key:
                self._hotkey.register_function(key, cb)

    # ---------------- 运行时设置接入（M3） ----------------

    def rebind_hotkeys(self) -> None:
        """运行时热键重绑：总开关开启时按当前 ``config.hotkey_map`` 重注册；
        关闭时仅保证 config 已更新（不注册）。"""
        if self._config.master_switch:
            self._register_hotkeys()

    def suspend_hotkeys(self) -> None:
        """临时注销功能热键（快捷键录制期间用，不停止输出、不改 master_switch）。"""
        self._hotkey.unregister_all_functions()

    def resume_hotkeys(self) -> None:
        """从 suspend 恢复：仅总开关开启时重新注册。"""
        if self._config.master_switch:
            self._register_hotkeys()

    def apply_engine_params(self) -> None:
        """从 config 灌入引擎参数（设置页改打字参数后实时生效）。"""
        self._engine.apply_params(
            auto_speed_ms=self._config.auto_speed_ms,
            humanize_jitter=self._config.humanize_jitter,
            jitter_amount=self._config.jitter_amount,
            punctuation_pause=self._config.punctuation_pause,
            chars_per_keypress=self._config.chars_per_keypress,
            chars_per_keypress_random=self._config.chars_per_keypress_random,
            humanize_thinking_pause=self._config.humanize_thinking_pause,
        )

    def shutdown(self) -> None:
        self._hotkey.unhook_all()
        self._engine.shutdown()
