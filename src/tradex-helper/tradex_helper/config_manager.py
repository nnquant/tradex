"""
tradex_helper.config_manager
===========================

封装 TOML 读写、扩展 Section 管理与轻量级校验逻辑，供 CLI 调度。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping, MutableMapping

from tomlkit import document, dumps, parse, table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

from .extension_discovery import ExtensionCandidate


class ConfigManager:
    """
    负责读取、更新与写入 ``tradex.config.toml``。

    :param config_path: 配置文件路径。
    :type config_path: Path
    """

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._document: TOMLDocument | None = None

    @property
    def document(self) -> TOMLDocument:
        """
        返回内存中的配置文档，若尚未加载则立即加载。

        :returns: TOML 文档对象。
        :rtype: TOMLDocument
        """

        if self._document is None:
            self.load()
        assert self._document is not None
        return self._document

    def exists(self) -> bool:
        """
        检查配置文件是否已经存在。

        :returns: 当文件存在时为 ``True``。
        :rtype: bool
        """

        return self.config_path.exists()

    def load(self) -> TOMLDocument:
        """
        读取配置文件，若不存在则返回全新的文档。

        :returns: TOML 文档。
        :rtype: TOMLDocument
        """

        if self.exists():
            content = self.config_path.read_text(encoding="utf-8")
            self._document = parse(content)
        else:
            self._document = document()
        return self._document

    def reset(self) -> TOMLDocument:
        """
        丢弃当前文档并新建空文档，用于初始化向导。

        :returns: 新建的 TOML 文档。
        :rtype: TOMLDocument
        """

        self._document = document()
        return self._document

    def save(self) -> None:
        """
        将内存中的配置写回磁盘，必要时自动创建父目录。
        """

        doc = self.document
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(dumps(doc), encoding="utf-8")

    def update_section(self, key: str, value: Mapping[str, Any]) -> None:
        """
        用给定内容覆盖指定一级节点。

        :param key: Section 名称，例如 ``environment``。
        :type key: str
        :param value: 需要写入的键值对。
        :type value: Mapping[str, Any]
        """

        doc = self.document
        doc[key] = value

    def get_section(self, key: str, default: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """
        读取一级节点内容。

        :param key: Section 名称。
        :type key: str
        :param default: 当节点不存在时返回的默认值。
        :type default: Mapping[str, Any] | None
        :returns: Section 内容。
        :rtype: Mapping[str, Any]
        """

        doc = self.document
        return doc.get(key, default or {})

    def apply_extension_selection(
        self, selected: List[str], candidates: Mapping[str, ExtensionCandidate]
    ) -> None:
        """
        根据用户选择更新 ``[extensions]`` 与 ``[agent]`` 节点。

        :param selected: 需要启用的扩展名称列表，保持调用顺序。
        :type selected: List[str]
        :param candidates: 发现到的扩展候选集合。
        :type candidates: Mapping[str, ExtensionCandidate]
        """

        doc = self.document
        extensions = _ensure_table(doc, "extensions")
        agent = _ensure_table(doc, "agent")

        agent["extension_enabled"] = selected

        for name in selected:
            candidate = candidates.get(name)
            if not candidate:
                continue
            extensions[name] = {"path": candidate.module_path}

        removable: list[str] = []
        for name, candidate in candidates.items():
            if name in selected:
                continue
            existing = extensions.get(name)
            if isinstance(existing, MutableMapping) and existing.get("path") == candidate.module_path:
                removable.append(name)
        for name in removable:
            del extensions[name]

    def summarize(self) -> dict[str, Any]:
        """
        提取核心字段，供 Rich 表格展示。

        :returns: 包含 environment、model、agent 子集的摘要字典。
        :rtype: dict[str, Any]
        """

        doc = self.document
        return {
            "environment": doc.get("environment", {}),
            "model": doc.get("model", {}),
            "agent": doc.get("agent", {}),
        }

    def validate(self) -> list[str]:
        """
        针对关键节点执行轻量级校验。

        :returns: 发现的问题列表，若为空表示通过。
        :rtype: list[str]
        """

        issues: list[str] = []
        summary = self.summarize()
        env = summary.get("environment", {})
        if not env or "cwd" not in env:
            issues.append("environment.cwd 未设置")

        model = summary.get("model", {})
        if not model.get("api_key"):
            issues.append("model.api_key 为空，无法调用远程模型")
        if not model.get("model_name"):
            issues.append("model.model_name 为空")

        agent = summary.get("agent", {})
        extensions_enabled = agent.get("extension_enabled", [])
        if extensions_enabled and not self.document.get("extensions"):
            issues.append("存在启用的扩展，但 [extensions] 节点缺失")

        return issues


def _ensure_table(doc: TOMLDocument, key: str) -> Table:
    value = doc.get(key)
    if isinstance(value, Table):
        return value
    new_table = table()
    if isinstance(value, MutableMapping):
        new_table.update(value)  # type: ignore[arg-type]
    doc[key] = new_table
    return new_table
