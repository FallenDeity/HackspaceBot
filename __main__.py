import logging

from src.core.bot import HackspaceBot
from src.utils.logger import setup_logging

if __name__ == "__main__":
    debug = True
    setup_logging(
        log_level=logging.DEBUG if debug else logging.INFO,
        file_logging=True,
        filename="hackspace-bot",
        log_dir="logs",
    )
    bot = HackspaceBot(
        prefix="!",
        ext_dir="src/ext",
    )
    bot.run()
