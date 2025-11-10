"""
tradex_helper.extension_discovery
================================

用于扫描 `src/extensions`（或向后兼容的 `src/extension`）目录，解析扩展模块是否满足
Tradex 约定的 `MCP_NAME`、`__mcp__` 与 `__mcp_allowed_tools__` 要求。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


@dataclass(slots=True)
class ExtensionCandidate:
    """
    表示一个可供 Tradex 加载的扩展模块。

    :param name: 扩展在配置文件中的键名，通常与文件名一致。
    :type name: str
    :param file_path: 扩展源文件的绝对路径。
    :type file_path: Path
    :param module_path: 可供 `importlib.import_module` 使用的模块路径。
    :type module_path: str
    :param has_mcp_name: 是否声明了 `MCP_NAME`。
    :type has_mcp_name: bool
    :param has_mcp_server: 是否声明了 `__mcp__`。
    :type has_mcp_server: bool
    :param has_allowed_tools: 是否声明了 `__mcp_allowed_tools__`。
    :type has_allowed_tools: bool
    """

    name: str
    file_path: Path
    module_path: str
    has_mcp_name: bool
    has_mcp_server: bool
    has_allowed_tools: bool

    def is_valid(self) -> bool:
        """
        判断扩展是否满足最低加载要求。

        :returns: 当 `MCP_NAME`、`__mcp__` 与 `__mcp_allowed_tools__` 均存在时返回 ``True``。
        :rtype: bool
        """

        return self.has_mcp_name and self.has_mcp_server and self.has_allowed_tools


def discover_extensions(
    project_root: Path, candidate_dirs: Sequence[Path | str]
) -> List[ExtensionCandidate]:
    """
    扫描给定目录，发现符合 Tradex 约定的扩展模块。

    :param project_root: 代码仓库根目录，用于计算相对模块路径。
    :type project_root: Path
    :param candidate_dirs: 可能存在扩展的目录列表，既可为 ``Path`` 也可为相对路径字符串。
    :type candidate_dirs: Sequence[Path | str]
    :returns: 发现到的扩展候选列表，按文件名排序。
    :rtype: List[ExtensionCandidate]
    """

    discovered: dict[str, ExtensionCandidate] = {}
    for raw_dir in candidate_dirs:
        dir_path = _normalize_dir(project_root, raw_dir)
        if dir_path is None or not dir_path.exists():
            continue
        for file_path in dir_path.glob("*.py"):
            candidate = _parse_extension_file(project_root, file_path)
            if candidate:
                discovered[candidate.name] = candidate
    return sorted(discovered.values(), key=lambda item: item.name)


def _normalize_dir(project_root: Path, raw_dir: Path | str) -> Path | None:
    if isinstance(raw_dir, Path):
        return raw_dir
    candidate = Path(raw_dir).expanduser()
    if candidate.is_absolute():
        return candidate
    return (project_root / candidate).resolve()


def _parse_extension_file(project_root: Path, file_path: Path) -> ExtensionCandidate | None:
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    flags = {
        "MCP_NAME": False,
        "__mcp__": False,
        "__mcp_allowed_tools__": False,
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in flags:
                    flags[target.id] = True

    rel_module = _build_module_path(project_root, file_path)
    name = file_path.stem
    return ExtensionCandidate(
        name=name,
        file_path=file_path,
        module_path=rel_module,
        has_mcp_name=flags["MCP_NAME"],
        has_mcp_server=flags["__mcp__"],
        has_allowed_tools=flags["__mcp_allowed_tools__"],
    )


def _build_module_path(project_root: Path, file_path: Path) -> str:
    try:
        relative = file_path.with_suffix("").resolve().relative_to(project_root.resolve())
    except ValueError:
        relative = file_path.with_suffix("").resolve()
    return ".".join(relative.parts)
