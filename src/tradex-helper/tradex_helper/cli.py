"""
tradex_helper.cli
=================

Rich 驱动的交互式命令行实现，提供配置向导与日常管理菜单。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import questionary
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.theme import Theme

from .config_manager import ConfigManager
from .extension_discovery import ExtensionCandidate, discover_extensions


class TradexHelperApp:
    """
    负责 orchestrate Rich 交互界面，涵盖初始化向导与日常管理。

    :param project_root: 仓库根目录。
    :type project_root: Path
    :param config_path: 配置文件路径。
    :type config_path: Path
    :param extension_dirs: 扩展扫描目录。
    :type extension_dirs: Sequence[Path]
    """

    def __init__(self, project_root: Path, config_path: Path, extension_dirs: Sequence[Path]):
        self.project_root = project_root
        self.config_manager = ConfigManager(config_path)
        self.extension_dirs = extension_dirs
        theme = Theme({"text": "white", "warning": "white", "error": "white"})
        self.console = Console(theme=theme)
        self._candidates: list[ExtensionCandidate] = []
        self._candidate_index: dict[str, ExtensionCandidate] = {}

    def run(self) -> None:
        """
        CLI 主入口。若配置不存在则触发向导，否则进入管理菜单。
        """

        self.refresh_extensions()
        if not self.config_manager.exists():
            self.console.print(
                Panel.fit(
                    "未检测到 Tradex 配置文件，已启动首次配置向导。"
                )
            )
            self.config_manager.reset()
            self.run_first_time_wizard()
            return
        self.config_manager.load()
        self._print_summary(title="当前配置概览")
        self.run_dashboard()

    def refresh_extensions(self) -> None:
        """
        重新扫描扩展目录，更新缓存。
        """

        self._candidates = discover_extensions(self.project_root, self.extension_dirs)
        self._candidate_index = {item.name: item for item in self._candidates}

    # ------------------------- 向导流程 -------------------------

    def run_first_time_wizard(self) -> None:
        """
        首次安装向导：依次采集环境、模型与扩展设置。
        """

        environment = self._prompt_environment_settings()
        model = self._prompt_model_settings()
        selected_extensions = self._prompt_extension_selection(preselected=[])
        agent = self._prompt_agent_settings(selected_extensions)

        self.config_manager.update_section("environment", environment)
        self.config_manager.update_section("model", model)
        self.config_manager.update_section("agent", agent)
        self.config_manager.apply_extension_selection(selected_extensions, self._candidate_index)
        self.config_manager.save()
        self.console.print(
            Panel.fit(
                f"配置已写入 {self.config_manager.config_path}"
            )
        )

    def _prompt_environment_settings(self) -> dict[str, str]:
        cwd = Prompt.ask("工作目录 (environment.cwd)", default=".")
        return {"cwd": cwd}

    def _prompt_model_settings(self) -> dict[str, str]:
        base_url = Prompt.ask(
            "模型服务 base_url",
            default="https://api.deepseek.com/anthropic",
        )
        api_key = Prompt.ask("模型 API Key (可稍后手动填写)", default="")
        model_name = Prompt.ask("主模型名称", default="deepseek-chat")
        fast_model = Prompt.ask("快捷模型名称 (可留空)", default="")
        return {
            "base_url": base_url,
            "api_key": api_key,
            "model_name": model_name,
            "fast_model_name": fast_model,
        }

    def _prompt_agent_settings(self, selected_extensions: Sequence[str]) -> dict[str, Sequence[str]]:
        permission_mode = Prompt.ask(
            "agent.permission_mode",
            choices=["default", "acceptEdits""bypassPermissions"],
            default="acceptEdits",
        )
        return {
            "permission_mode": permission_mode,
            "extension_enabled": list(selected_extensions),
        }

    # ------------------------- 管理菜单 -------------------------

    def run_dashboard(self) -> None:
        """
        循环展示管理菜单，直到用户退出。
        """

        while True:
            choice = questionary.select(
                "使用方向键选择功能，Enter 确认",
                choices=[
                    questionary.Choice(title="查看配置摘要", value="summary"),
                    questionary.Choice(title="管理扩展", value="extensions"),
                    questionary.Choice(title="编辑模型配置", value="model"),
                    questionary.Choice(title="校验配置", value="validate"),
                    questionary.Choice(title="退出", value="exit"),
                ],
            ).ask()
            if choice is None:
                self.console.print("已退出 Tradex Helper。")
                break
            if choice == "summary":
                self._handle_view_summary()
            elif choice == "extensions":
                self._handle_manage_extensions()
            elif choice == "model":
                self._handle_edit_model()
            elif choice == "validate":
                self._handle_validate()
            elif choice == "exit":
                self.console.print("已退出 Tradex Helper。")
                break

    def _handle_view_summary(self) -> None:
        self._print_summary(title="配置摘要")

    def _format_candidate_label(self, candidate: ExtensionCandidate) -> str:
        """
        构造扩展选择菜单的显示文本。

        :param candidate: 扩展候选信息。
        :type candidate: ExtensionCandidate
        :returns: questionary 使用的多行标签。
        :rtype: str
        """

        label = f"{candidate.name} · {candidate.module_path}"
        if candidate.description:
            label = f"{label} · {candidate.description}"
        return label

    def _print_summary(self, title: str) -> None:
        summary = self.config_manager.summarize()
        table = Table(title=title, show_lines=True, box=box.SIMPLE, title_justify="left")
        table.add_column("字段", style="bold")
        table.add_column("内容")
        for section, values in summary.items():
            pretty = "\n".join(f"{k} = {v}" for k, v in values.items()) or "(空)"
            table.add_row(section, pretty)
        self.console.print(table)

    def _handle_manage_extensions(self) -> None:
        self.refresh_extensions()
        agent = self.config_manager.get_section("agent", {})
        preselected = agent.get("extension_enabled", [])
        self.console.print(
            Panel(
                "根据提示选择需要启用的扩展，已启用的扩展会自动覆盖路径配置。"
            )
        )
        selected = self._prompt_extension_selection(preselected=preselected, allow_skip=True)
        if selected == preselected:
            self.console.print("扩展列表保持不变。")
            return
        self.config_manager.apply_extension_selection(selected, self._candidate_index)
        self.config_manager.save()
        self.console.print("扩展配置已更新。")

    def _handle_edit_model(self) -> None:
        current = self.config_manager.get_section("model", {})
        base_url = Prompt.ask(
            "模型 base_url",
            default=current.get("base_url", "https://api.deepseek.com/anthropic"),
        )
        api_key = Prompt.ask(
            "模型 API Key",
            default=current.get("api_key", ""),
        )
        model_name = Prompt.ask(
            "主模型名称",
            default=current.get("model_name", "deepseek-chat"),
        )
        fast_model = Prompt.ask(
            "快速模型名称",
            default=current.get("fast_model_name", ""),
        )
        data = {
            "base_url": base_url,
            "api_key": api_key,
            "model_name": model_name,
            "fast_model_name": fast_model,
        }
        self.config_manager.update_section("model", data)
        self.config_manager.save()
        self.console.print("模型配置已保存。")

    def _handle_validate(self) -> None:
        issues = self.config_manager.validate()
        if not issues:
            self.console.print(Panel("所有关键检查均通过。", border_style="green"))
            return
        table = Table(title="待处理问题", box=box.SIMPLE_HEAD)
        table.add_column("#")
        table.add_column("描述")
        for idx, issue in enumerate(issues, start=1):
            table.add_row(str(idx), issue)
        self.console.print(table)

    # ------------------------- 通用交互 -------------------------

    def _prompt_extension_selection(
        self, preselected: Sequence[str], allow_skip: bool = False
    ) -> list[str]:
        if not self._candidates:
            self.console.print("未在扩展目录中找到可用扩展。")
            return list(preselected)
        invalid_candidates = [c for c in self._candidates if not c.is_valid()]
        if invalid_candidates:
            warn_table = Table(title="已忽略的扩展", box=box.MINIMAL_DOUBLE_HEAD)
            warn_table.add_column("名称")
            warn_table.add_column("原因")
            for candidate in invalid_candidates:
                warn_table.add_row(candidate.name, "缺少 MCP 定义")
            self.console.print(warn_table)

        selectable = [
            c for c in self._candidates if c.is_valid()
        ]
        if not selectable:
            self.console.print("没有满足要求的扩展，无法更新。")
            return list(preselected)

        choices = [
            questionary.Choice(
                title=self._format_candidate_label(candidate),
                value=candidate.name,
                checked=candidate.name in preselected,
            )
            for candidate in selectable
        ]
        prompt_message = "上下键移动、空格选择、Enter 确认"
        result = questionary.checkbox(prompt_message, choices=choices).ask()
        if result is None:
            return list(preselected)
        if not result and not allow_skip:
            self.console.print("至少需要选择一个扩展。")
            return list(preselected) if preselected else self._prompt_extension_selection(preselected, allow_skip)
        return list(result)


def build_app(args: argparse.Namespace) -> TradexHelperApp:
    """
    根据命令行参数构建应用实例，便于测试。
    """

    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config).resolve()
    if args.extensions_dir:
        extension_dirs = [Path(item) for item in args.extensions_dir]
    else:
        extension_dirs = [project_root / "src" / "extensions", project_root / "src" / "extension"]
    return TradexHelperApp(project_root, config_path, extension_dirs)


def main(argv: Sequence[str] | None = None) -> None:
    """
    tradex-helper CLI 入口。
    """

    parser = argparse.ArgumentParser(description="Tradex 配置助手")
    parser.add_argument("--config", default="tradex.config.toml", help="配置文件路径")
    parser.add_argument("--project-root", default=".", help="Tradex 仓库根目录")
    parser.add_argument(
        "--extensions-dir",
        action="append",
        help="额外的扩展搜索目录，可重复提供多次",
    )
    args = parser.parse_args(argv)
    app = build_app(args)
    app.run()
