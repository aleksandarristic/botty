import os

from telegram import Update
from telegram.ext import ContextTypes

from ..utils import escape_markdown, escape_markdown_code, run_command
from .base import Command

EMBY_DATA_PATH = os.getenv("EMBY_DATA_PATH", "/mnt/embydata")
MEDIA_PATH = os.getenv("MEDIA_PATH", "/mnt/media")


class EmbyStatusCommand(Command):
    name = "emby_status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Checks the status of Emby media server."""
        # -n 0 suppresses logs to avoid "Message too long" and parsing issues with special chars in logs
        service_status = await run_command(
            ["systemctl", "status", "emby-server.service", "--no-pager", "-n", "0"]
        )
        db_drive_status = await run_command(["df", "-h", EMBY_DATA_PATH])
        media_drive_status = await run_command(["df", "-h", MEDIA_PATH])

        message = "*Emby Media Server Status*\n\n"
        message += (
            f"*Service Status:*\n```\n{escape_markdown_code(service_status)}\n```\n"
        )
        message += (
            f"*Database Drive \\({escape_markdown(EMBY_DATA_PATH)}\\):*\n"
            f"```\n{escape_markdown_code(db_drive_status)}\n```\n"
        )
        message += (
            f"*Media Drive \\({escape_markdown(MEDIA_PATH)}\\):*\n"
            f"```\n{escape_markdown_code(media_drive_status)}\n```"
        )

        await update.message.reply_text(message, parse_mode="MarkdownV2")


class AdguardStatusCommand(Command):
    name = "adguard_status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Checks the status of AdGuard Home."""
        # -n 0 suppresses logs
        service_status = await run_command(
            ["systemctl", "status", "AdGuardHome.service", "--no-pager", "-n", "0"]
        )

        message = (
            f"*AdGuard Home Status*\n\n```\n{escape_markdown_code(service_status)}\n```"
        )

        await update.message.reply_text(message, parse_mode="MarkdownV2")


__all__ = ["EMBY_DATA_PATH", "MEDIA_PATH", "EmbyStatusCommand", "AdguardStatusCommand"]
