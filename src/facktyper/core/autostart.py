"""开机自启：读写注册表 ``HKCU\\...\\Run``。

- ``enable_autostart()``：写 ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\FakeTyperPro``
  值为当前可执行路径 + `` --minimized``；
- ``disable_autostart()``：删除该值；
- ``is_autostart_enabled()``：查询是否存在且指向当前 exe。

打包后（frozen）写 exe 路径；开发期（非 frozen）写
``"<python.exe>" "<__main__.py 路径>"``——若 python.exe 不可用则拒绝并日志警告。
非 Windows 平台降级为 no-op（返回 False/True 但不写注册表）。
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from ..utils.logger import get_logger

_log = get_logger("autostart")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "FakeTyperPro"

# 启动参数：最小化到托盘
_MINIMIZED_ARG = "--minimized"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _command_line() -> Optional[str]:
    """构造开机自启的命令行字符串。返回 None 表示当前环境不支持。"""
    if getattr(sys, "frozen", False):
        # 打包后：直接 exe 路径
        exe = sys.executable
        if not exe:
            return None
        return f'"{exe}" {_MINIMIZED_ARG}'
    # 开发期：python.exe + 脚本入口
    # 入口定位：项目根的 src/facktyper/__main__.py 通过 ``python -m facktyper`` 启动，
    # 注册表需写完整命令；用 sys.executable(pythonw.exe 更合适，无控制台) + -m facktyper
    py = sys.executable
    if not py or not os.path.exists(py):
        _log.warning("开发模式下无法定位 python 解释器，开机自启将不可用")
        return None
    # 优先用 pythonw.exe（无控制台窗口）
    pyw = py
    dirname, basename = os.path.split(py)
    if basename.lower() == "python.exe":
        cand = os.path.join(dirname, "pythonw.exe")
        if os.path.exists(cand):
            pyw = cand
    return f'"{pyw}" -m facktyper {_MINIMIZED_ARG}'


def is_autostart_enabled() -> bool:
    """查询注册表是否存在 FakeTyperPro 自启项。"""
    if not _is_windows():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, APP_NAME)
        return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable_autostart() -> bool:
    """写入自启项。返回是否成功。"""
    if not _is_windows():
        _log.warning("非 Windows 平台，开机自启不可用")
        return False
    cmd = _command_line()
    if not cmd:
        return False
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        _log.info("已启用开机自启: %s", cmd)
        return True
    except OSError as e:  # noqa: BLE001
        _log.warning("启用开机自启失败: %s", e)
        return False


def disable_autostart() -> bool:
    """删除自启项。返回是否成功（不存在也算成功）。"""
    if not _is_windows():
        return True
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
        _log.info("已禁用开机自启")
        return True
    except FileNotFoundError:
        return True  # 不存在视为成功
    except OSError as e:  # noqa: BLE001
        _log.warning("禁用开机自启失败: %s", e)
        return False


def sync_to_registry(enabled: bool) -> bool:
    """根据布尔值同步注册表（True→enable，False→disable）。返回是否成功。"""
    if enabled:
        return enable_autostart()
    return disable_autostart()
