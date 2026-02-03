from telegram import Update
from telegram.ext import ContextTypes

from botty.system_checks import get_adguard_checks, get_emby_checks
from ..utils import escape_markdown, escape_markdown_code
from .base import Command


class EmbyStatusCommand(Command):
    name = "emby_status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Checks the status of Emby media server."""
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

        await update.message.reply_text(message, parse_mode="MarkdownV2")


class AdguardStatusCommand(Command):
    name = "adguard_status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Checks the status of AdGuard Home."""
        service_status = await get_adguard_checks()

        message = (
            f"*AdGuard Home Status*\n\n```\n{escape_markdown_code(service_status)}\n```"
        )

        await update.message.reply_text(message, parse_mode="MarkdownV2")


__all__ = ["EmbyStatusCommand", "AdguardStatusCommand"]
