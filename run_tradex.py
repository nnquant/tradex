import argparse

from src.tradex import TradexApp

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the Tradex application.")
    parser.add_argument("--config", type=str, default="tradex.config.toml", help="Path to the configuration file.")
    args = parser.parse_args()

    app = TradexApp(args.config)
    app.run()
