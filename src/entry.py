"""FakeTyper Pro PyInstaller 入口脚本。

该脚本仅用于打包单文件 exe，解决 PyInstaller 将包内 ``__main__.py``
作为顶层脚本执行时相对导入失败的问题。开发/命令行仍使用 ``python -m facktyper``。
"""
from __future__ import annotations

import sys

from facktyper.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
