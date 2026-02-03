import httpx
from telegram import Update
from telegram.ext import ContextTypes

from botty.gohome import format_network_tests
from botty.http import create_async_client
from ..utils import escape_markdown
from .base import Command


class NetworkTestsCommand(Command):
    name = "network_tests"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Fetches the latest network test results."""
        try:
            async with create_async_client(self.config) as client:
                response = await client.get(self.config.gohome_api_url)
                response.raise_for_status()
                data = response.json()

                message = format_network_tests(data)
                await update.message.reply_text(message, parse_mode="MarkdownV2")

        except httpx.RequestError as e:
            await update.message.reply_text(
                f"Could not connect to the GoHome API: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            await update.message.reply_text(
                f"An error occurred: {escape_markdown(str(e))}", parse_mode="MarkdownV2"
            )


__all__ = ["NetworkTestsCommand"]
