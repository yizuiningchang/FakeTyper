# -*- mode: python ; coding: utf-8 -*-
"""FakeTyper Pro PyInstaller 打包配置（单文件 exe）。

构建：``pyinstaller FakeTyperPro.spec`` 或 ``build.bat``
产出：``dist/FakeTyperPro.exe``

要点：
- onefile + noconsole（窗口应用）
- 内嵌应用图标与 Windows 版本资源
- 包含 resources（图标）、keyboard/PySide6/numpy/pyperclip 依赖
- 数据落 %APPDATA%（与 exe 路径解耦），快捷方式可放任意位置
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# 项目根目录（spec 文件所在目录）
ROOT = Path(SPECPATH).resolve()

# collect_submodules 在 spec 求值阶段运行（早于 Analysis 的 pathex 生效），
# 必须先把 src 加入 sys.path，否则找不到 facktyper 包、返回空列表。
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# __main__.py 的业务导入全在 main() 函数的条件分支内（懒加载），
# PyInstaller 静态分析不会跟进；必须显式收集 facktyper 全部子模块，
# 否则 PySide6 / core / ui 等都不会进包（产物仅 ~6MB，运行即静默崩溃）。
_facktyper_submodules = collect_submodules("facktyper")

a = Analysis(
    # 使用独立入口脚本，避免 PyInstaller 将包内 __main__.py 当顶层脚本执行
    # 导致的 "attempted relative import with no known parent package" 错误。
    [str(ROOT / "src" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        # 应用图标资源
        (str(ROOT / "src" / "facktyper" / "resources" / "app.ico"), "facktyper/resources"),
    ],
    hiddenimports=[
        "keyboard._winkeyboard",
        "keyboard._nixkeyboard",
        "pyperclip",
        # facktyper 全部子模块（含 ui.app / cli / selftest / core.* / ui.views.* 等）
        *_facktyper_submodules,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不必要的大模块，减小体积
        # 注意：不可排除 argparse —— PySide6/shiboken6 签名系统依赖它，
        # 否则冻结 exe 启动即崩（STATUS_STACK_BUFFER_OVERRUN 0xC0000409）。
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FakeTyperPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 窗口应用，无控制台
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "src" / "facktyper" / "resources" / "app.ico"),
    version=str(ROOT / "version_info.txt"),
)
