"""原子化文件读写：先写临时文件再替换，防止写入中途崩溃导致数据损坏。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_bytes(path: str | os.PathLike, data: bytes) -> None:
    """原子写入字节：写入同名 .tmp 临时文件后 os.replace 覆盖。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 临时文件与目标同目录，保证 os.replace 在同一卷上原子完成
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_text(path: str | os.PathLike, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path: str | os.PathLike, obj: Any, *, indent: int = 2) -> None:
    """原子写入 JSON（UTF-8、ensure_ascii=False、缩进 2）。"""
    text = json.dumps(obj, ensure_ascii=False, indent=indent, default=str)
    atomic_write_text(path, text)


def safe_read_json(path: str | os.PathLike, default: Any = None) -> Any:
    """安全读取 JSON：文件缺失或损坏时返回 default，不抛异常。"""
    path = Path(path)
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default
