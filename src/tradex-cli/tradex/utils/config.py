from tomlkit import parse


def load_config(config_path: str):
    """使用 tomlkit 读取配置文件，保留注释与格式。"""
    with open(config_path, "r", encoding="utf-8") as file:
        return parse(file.read())
