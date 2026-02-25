import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler

from botty.cmd import get_command_registry
from botty.config import BottyConfig
from botty.sudo_policy import build_startup_sudoers_guidance

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

config = BottyConfig.from_env()


def main() -> None:
    """Start the bot."""
    for line in build_startup_sudoers_guidance(config):
        logging.info(line)

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(config.telegram_bot_token).build()

    # Register all commands from the command registry
    command_registry = get_command_registry(config)
    for command_name, handler in command_registry:
        application.add_handler(CommandHandler(command_name, handler))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(
        timeout=config.telegram_poll_timeout_seconds,
        allowed_updates=["message"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    if not config.telegram_bot_token or not config.authorized_user_ids:
        print(
            "Please set the TELEGRAM_BOT_TOKEN and AUTHORIZED_USER_ID environment variables."
        )
    else:
        main()
