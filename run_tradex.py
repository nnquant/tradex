import argparse

from src.tradex import TradexApp
from src.tradex.utils.config import load_config



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the Tradex application.")
    parser.add_argument("--config", type=str, default="tradex.config.toml", help="Path to the configuration file.")
    args = parser.parse_args()

    config = load_config(args.config)
    app = TradexApp(config)
    app.run()
