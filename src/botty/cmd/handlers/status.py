from telegram import Update
from telegram.ext import ContextTypes

from botty.services.system_checks import get_status_checks
from ..utils import escape_markdown_code
from .base import Command


class StartCommand(Command):
    name = "start"
    auth_required = False

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a message when the command /start is issued."""
        user = update.effective_user
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! Here are the available commands:"
            "\n/start - Shows this message"
            "\n/status - General server health"
            "\n/emby_status - Emby media server status"
            "\n/adguard_status - AdGuard Home status"
            "\n/network_tests - Latest network test results"
        )


class StatusCommand(Command):
    name = "status"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Provides a general server health check."""
        uptime, disk_usage, memory_usage = await get_status_checks()

        message = "*Server Status*\n\n"
        message += f"*Uptime:*\n```\n{escape_markdown_code(uptime)}\n```\n"
        message += f"*Memory Usage:*\n```\n{escape_markdown_code(memory_usage)}\n```\n"
        message += (
            f"*Disk Usage \\(/\\):*\n```\n{escape_markdown_code(disk_usage)}\n```"
        )

        await update.message.reply_text(message, parse_mode="MarkdownV2")


__all__ = ["StartCommand", "StatusCommand"]
