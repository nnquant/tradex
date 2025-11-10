from loguru import logger


def setup_log(log_path: str):
    """Setup logging configuration."""
    logger.remove()
    logger.add(log_path, rotation="10 MB", retention="10 days", compression="zip")
