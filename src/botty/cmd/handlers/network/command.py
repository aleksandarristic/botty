import logging
import time

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from botty.utils import escape_markdown
from botty.cmd.handlers.base import Command
from .gohome import GoHomeParseError, format_network_tests
from .http import create_async_client


class NetworkTestsCommand(Command):
    name = "network_tests"
    description = "Latest network test results"

    _cache_ttl_seconds = 30.0
    _cache_timestamp: float | None = None
    _cache_message: str | None = None
    _logger = logging.getLogger(__name__)

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Fetches the latest network test results."""
        reply_message = self._require_message(update)
        try:
            now = time.monotonic()
            if (
                self._cache_timestamp is not None
                and self._cache_message is not None
                and now - self._cache_timestamp < self._cache_ttl_seconds
            ):
                await reply_message.reply_text(self._cache_message, parse_mode="MarkdownV2")
                return

            async with create_async_client(self.config) as client:
                response = await client.get(self.config.gohome_api_url)
                response.raise_for_status()
                data = response.json()

                message = format_network_tests(data)
                self._cache_message = message
                self._cache_timestamp = now
                await reply_message.reply_text(message, parse_mode="MarkdownV2")

        except httpx.RequestError as e:
            self._logger.warning(
                "gohome.request_failed", extra={"url": self.config.gohome_api_url}
            )
            await reply_message.reply_text(
                f"Could not connect to the GoHome API: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2",
            )
        except GoHomeParseError as e:
            self._logger.warning("gohome.parse_failed", exc_info=e)
            await reply_message.reply_text(
                f"GoHome parsing error: {escape_markdown(str(e))}",
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            self._logger.exception("gohome.unexpected_error")
            await reply_message.reply_text(
                f"An error occurred: {escape_markdown(str(e))}", parse_mode="MarkdownV2"
            )


__all__ = ["NetworkTestsCommand"]
