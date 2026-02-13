from telegram import Update
from telegram.ext import ContextTypes

from botty.utils import escape_markdown, escape_markdown_code
from botty.cmd.handlers.base import Command
from .checks import get_emby_checks


class EmbyStatusCommand(Command):
    name = "emby_status"
    description = "Emby media server status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Checks the status of Emby media server."""
        reply_message = self._require_message(update)
        service_status, db_drive_status, media_drive_status = await get_emby_checks(
            self.config
        )

        message = "*Emby Media Server Status*\n\n"
        message += (
            f"*Service Status:*\n```\n{escape_markdown_code(service_status)}\n```\n"
        )
        message += (
            f"*Database Drive \\({escape_markdown(self.config.emby_data_path)}\\):*\n"
            f"```\n{escape_markdown_code(db_drive_status)}\n```\n"
        )
        message += (
            f"*Media Drive \\({escape_markdown(self.config.media_path)}\\):*\n"
            f"```\n{escape_markdown_code(media_drive_status)}\n```"
        )

        await self._reply_markdown(reply_message, message)




__all__ = ["EmbyStatusCommand"]
