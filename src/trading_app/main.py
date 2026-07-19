"""
main.py

Application entry point.
"""

from trading_app.engines import Engine
import logging
import sys


def configure_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )


if __name__ == "__main__":
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("ENGINE: starting backend")
    Engine().run()