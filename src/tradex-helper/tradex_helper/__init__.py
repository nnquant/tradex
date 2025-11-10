"""
tradex_helper
================

:mod:`tradex_helper` 提供 Tradex 配置向导与扩展管理 CLI，
帮助首次使用者快速创建配置文件，并在后续维护阶段管理配置内容。
"""

from .cli import main

__all__ = ["main"]
