"""Tradex 统一 CLI 入口，整合主应用与配置助手。"""

from __future__ import annotations

from typing import Sequence

import click, sys, os

from tradex import TradexApp
from tradex_helper import main as helper_main

DEFAULT_CONFIG_PATH = "tradex.config.toml"
sys.path.append(os.getcwd())


def _run_tradex(config_path: str) -> None:
    """
    启动 Tradex 主应用。

    :param config_path: 配置文件路径。
    :type config_path: str
    :returns: ``None``。
    :rtype: None
    """

    app = TradexApp(config_path)
    app.run()


def _build_helper_args(config_path: str, project_root: str, extensions_dir: Sequence[str]) -> list[str]:
    """
    构造传递给配置助手的参数列表。

    :param config_path: 配置文件路径。
    :type config_path: str
    :param project_root: 仓库根目录。
    :type project_root: str
    :param extensions_dir: 额外扩展目录列表。
    :type extensions_dir: Sequence[str]
    :returns: 适配 ``tradex_helper`` 的参数序列。
    :rtype: list[str]
    """

    helper_args = ["--config", config_path, "--project-root", project_root]
    for directory in extensions_dir:
        helper_args.extend(["--extensions-dir", directory])
    return helper_args


@click.group(invoke_without_command=True)
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG_PATH,
    show_default=True,
    help="配置文件路径",
)
@click.pass_context
def cli(ctx: click.Context, config_path: str) -> None:
    """
    运行 Tradex

    """

    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    if ctx.invoked_subcommand is None:
        _run_tradex(config_path)


@cli.command()
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Tradex 仓库根目录",
)
@click.option(
    "--extensions-dir",
    multiple=True,
    help="额外扩展目录，可多次传入",
)
@click.pass_context
def config(ctx: click.Context, project_root: str, extensions_dir: Sequence[str]) -> None:
    """
    配置 Tradex
    """

    helper_args = _build_helper_args(
        config_path=ctx.obj["config_path"],
        project_root=project_root,
        extensions_dir=extensions_dir,
    )
    helper_main(helper_args)


if __name__ == "__main__":
    cli()
