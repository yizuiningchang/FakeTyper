"""FakeTyper Pro 入口。

M1 阶段：``python -m facktyper`` 运行命令行自测/交互测试；
M2 起：默认启动 GUI（``python -m facktyper gui``），``cli`` 子命令保留命令行模式。
M3 起：支持 ``--minimized`` 参数（开机自启时静默到托盘）。
"""
from __future__ import annotations

import sys


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "gui"

    if cmd in ("cli", "--cli", "-c"):
        from .cli import run_cli
        return run_cli(args[1:])

    if cmd in ("selftest", "--selftest", "-s"):
        from .selftest import run_selftest
        return run_selftest()

    # GUI 模式：传递全部参数（含 --minimized）
    # 若首参数是 gui 子命令则跳过它
    gui_args = args[1:] if cmd in ("gui",) else args
    try:
        from .ui.app import run_gui
        return run_gui(gui_args)
    except Exception:
        from .cli import run_cli
        return run_cli([])


if __name__ == "__main__":
    raise SystemExit(main())
