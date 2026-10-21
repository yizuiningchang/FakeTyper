"""M1 交互式命令行测试入口。

用法：
    python -m facktyper cli        # 进入交互式
    python -m facktyper cli --demo  # 用内置示例文本，直接开启总开关

进入后总开关默认开启（注册 F1–F6），在任意文本编辑器中测试：
    F1 按键触发模式（随便敲键盘逐字出预设）
    F2 急停          F3 自动匀速      F4 重置
    F5 重载预设      F6 切换下一预设
命令：
    on / off       总开关
    list           列出预设
    set <id前缀>   激活某预设
    speed <ms>     调整自动速度
    status         查看状态
    q / quit       退出
"""
from __future__ import annotations

import sys
import time

from .data import preset_store
from .data.config import AppConfig
from .data.constants import Action
from .utils.logger import get_logger, install_excepthook
from .core.controller import EngineController
from .core.hotkey_manager import HotkeyManager
from .core.typing_engine import EngineListener, TypingEngine

_log = get_logger("cli")


class _CliListener(EngineListener):
    def __init__(self):
        self.last_mode = "idle"

    def on_mode_changed(self, mode):
        self.last_mode = mode
        print(f"  >> 模式切换: {mode}")

    def on_progress(self, percent, current, total):
        sys.stdout.write(f"\r  >> 进度 {percent:5.1f}% ({current}/{total})   ")
        sys.stdout.flush()

    def on_finished(self, reason):
        print(f"\n  >> 输出结束: {reason}")

    def on_error(self, message):
        print(f"\n  >> 错误: {message}")

    def on_char(self, char):
        pass

    def on_preset_changed(self, title, total):
        print(f"  >> 当前预设: {title!r}（{total} 字符）")


def _print_help(config: AppConfig) -> None:
    print("=" * 56)
    print("FakeTyper Pro —— M1 命令行测试")
    print("=" * 56)
    print("热键映射：")
    for a in Action:
        print(f"  {config.key_for(a.value):>3}  {a.label}")
    print("-" * 56)
    print("请在任意文本编辑器中按 F1/F3 测试输出；F2 急停。")
    print("命令：on off list set <id> speed <ms> status quit")
    print("-" * 56)


def run_cli(argv: list[str]) -> int:
    install_excepthook()
    config = AppConfig.load()
    config.save()

    # 准备数据：确保至少有一套预设
    if not preset_store.list_presets():
        preset_store.ensure_default_preset()

    hm = HotkeyManager()
    engine = TypingEngine(hm)
    ctrl = EngineController(engine, hm, config)

    listener = _CliListener()
    engine.add_listener(listener)
    ctrl.reload_presets()
    if config.last_active_preset_id and preset_store.get_preset(config.last_active_preset_id):
        ctrl.set_active_preset(config.last_active_preset_id)
    else:
        ctrl._ensure_active()

    _print_help(config)

    ctrl.master_on()
    print("总开关已开启。")

    def _cmd_loop() -> int:
        while True:
            try:
                line = input("facktyper> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            if cmd in ("q", "quit", "exit"):
                break
            elif cmd == "on":
                ctrl.master_on()
                print("总开关已开启。")
            elif cmd == "off":
                ctrl.master_off()
                print("总开关已关闭，系统输入恢复正常。")
            elif cmd == "list":
                for p in ctrl.presets:
                    mark = " *" if p.id == ctrl._active_id else ""
                    pin = " 📌" if p.pinned else ""
                    print(f"  {p.id}  {p.title}{mark}{pin}  ({p.total_chars} 字)")
            elif cmd == "set" and len(parts) >= 2:
                key = parts[1]
                match = [p for p in ctrl.presets if p.id.startswith(key)]
                if match:
                    ctrl.set_active_preset(match[0].id)
                    print(f"已激活: {match[0].title}")
                else:
                    print("未找到匹配预设。")
            elif cmd == "speed" and len(parts) >= 2:
                try:
                    config.auto_speed_ms = int(parts[1])
                    config.save()
                    engine.auto_speed_ms = config.auto_speed_ms
                    print(f"自动速度已设为 {config.auto_speed_ms} ms/字")
                except ValueError:
                    print("用法: speed <毫秒整数>")
            elif cmd == "status":
                idx, total = engine.progress
                print(f"  模式={engine.mode} 进度={idx}/{total} 总开关={config.master_switch}")
                print(f"  自动速度={config.auto_speed_ms}ms 抖动={config.humanize_jitter}({config.jitter_amount})")
            elif cmd == "help":
                _print_help(config)
            else:
                print(f"未知命令: {cmd}（on/off/list/set/speed/status/quit）")

        ctrl.shutdown()
        print("已退出。")
        return 0

    return _cmd_loop()


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
