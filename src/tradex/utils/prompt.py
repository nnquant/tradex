from pathlib import Path
from typing import Any, Dict

from jinja2 import Template, TemplateError
from loguru import logger


def get_prompt(prompt_path: Path) -> str:
    """
    读取提示词原始内容。

    :param prompt_path: 提示词文件路径。
    :type prompt_path: pathlib.Path
    :returns: 提示词原始文本。
    :rtype: str
    :raises FileNotFoundError: 当文件不存在时抛出。
    """
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read()


def render_prompt(prompt_path: Path, context: Dict[str, Any] | None = None) -> str:
    """
    使用jinja2渲染提示词模板，渲染失败时返回原始内容。

    :param prompt_path: 提示词文件路径。
    :type prompt_path: pathlib.Path
    :param context: 渲染上下文字典。
    :type context: dict[str, Any] | None
    :returns: 渲染后的提示词文本。
    :rtype: str
    """
    raw_prompt = get_prompt(prompt_path)
    if not context:
        return raw_prompt
    try:
        template = Template(raw_prompt)
        return template.render(**context)
    except TemplateError as error:
        logger.warning(
            "failed to render prompt template path=[{}] error=[{}]",
            prompt_path,
            error,
        )
        return raw_prompt
