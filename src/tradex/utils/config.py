import tomllib


def load_config(config_path: str) -> dict:
    """Load configuration from a TOML file."""
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config

