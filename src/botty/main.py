import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler

from botty.cmd import command_registry

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Get configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID")


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register all commands from the command registry
    for command_name, handler in command_registry:
        application.add_handler(CommandHandler(command_name, handler))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(
        timeout=60, allowed_updates=["message"], drop_pending_updates=True
    )


if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_USER_ID:
        print(
            "Please set the TELEGRAM_BOT_TOKEN and AUTHORIZED_USER_ID environment variables."
        )
    else:
        main()
