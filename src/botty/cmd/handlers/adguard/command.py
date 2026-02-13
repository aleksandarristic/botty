from telegram import Update
from telegram.ext import ContextTypes

from botty.cmd.handlers.base import Command
from botty.utils import escape_markdown_code
from .checks import get_adguard_checks


class AdguardStatusCommand(Command):
    name = "adguard_status"
    description = "AdGuard Home status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Checks the status of AdGuard Home."""
        reply_message = self._require_message(update)
        service_status = await get_adguard_checks()

        message = (
            f"*AdGuard Home Status*\n\n```\n{escape_markdown_code(service_status)}\n```"
        )

        await self._reply_markdown(reply_message, message)

__all__ = ["AdguardStatusCommand"]
