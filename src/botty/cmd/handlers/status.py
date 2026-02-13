import html

from telegram import Update
from telegram.ext import ContextTypes

from botty.config import BottyConfig
from botty.services.system_checks import get_status_checks
from botty.utils import escape_markdown_code
from .base import Command


class StartCommand(Command):
    name = "start"
    description = "Shows this message"
    auth_required = False

    def __init__(self, config: BottyConfig, commands: list[Command]) -> None:
        super().__init__(config)
        self.commands = commands

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a message when the command /start is issued."""
        user = update.effective_user
        commands_list = "\n".join(
            [
                f"/{html.escape(str(cmd.name), quote=True)} - "
                f"{html.escape(str(cmd.description), quote=True)}"
                for cmd in self.commands
            ]
        )
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! Here are the available commands:"
            f"\n{commands_list}"
        )


class StatusCommand(Command):
    name = "status"
    description = "General server health"

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
