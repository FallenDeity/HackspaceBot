import logging

from src.utils.logger import setup_logging

if __name__ == "__main__":
    setup_logging(
        log_level=logging.DEBUG,
        file_logging=True,
        filename="hackspace-bot",
        log_dir="logs",
    )

    from src.core.bot import HackspaceBot

    bot = HackspaceBot(
        prefix="!",
        ext_dir="src/ext",
    )
    bot.run()
