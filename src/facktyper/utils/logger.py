"""日志模块：滚动日志，保留最近 7 天，全局异常兜底使用。

设计要点：
- 文件日志写入 ``%APPDATA%\\FakeTyperPro\\logs\\``，按天滚动，保留 7 天；
- 同时输出到控制台（开发期）；
- 提供 ``install_excepthook`` 安装全局未捕获异常钩子，避免静默崩溃。
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from ..data.paths import logs_dir

_LOGGER_NAME = "facktyper"
_initialized = False


def get_logger(name: str | None = None) -> logging.Logger:
    """获取 logger，首次调用时完成初始化。"""
    global _initialized
    logger = logging.getLogger(_LOGGER_NAME)
    if not _initialized:
        _setup(logger)
        _initialized = True
    if name and name != _LOGGER_NAME:
        return logger.getChild(name)
    return logger


def _setup(logger: logging.Logger) -> None:
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件日志：按天滚动，保留 7 份
    try:
        file_handler = TimedRotatingFileHandler(
            logs_dir() / "facktyper.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except Exception:
        # 数据目录不可用时不能让软件无法启动
        pass

    # 控制台：打包 --noconsole 时 sys.stderr 为 None，跳过
    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(fmt)
    console.setLevel(logging.INFO)
    logger.addHandler(console)


def install_excepthook(on_crash=None) -> None:
    """安装全局未捕获异常钩子，记录日志并可触发回调（如 toast 提示）。"""

    def _hook(exc_type, exc_value, exc_tb):
        # Ctrl+C 不当崩溃处理
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger = get_logger()
        logger.critical("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        if callable(on_crash):
            try:
                on_crash(exc_type, exc_value, exc_tb)
            except Exception:
                logger.exception("on_crash 回调自身异常")

    sys.excepthook = _hook
