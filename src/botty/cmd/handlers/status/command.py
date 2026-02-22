import html

from telegram import Update
from telegram.ext import ContextTypes

from botty.config import BottyConfig
from botty.utils import escape_markdown, escape_markdown_code
from botty.cmd.handlers.base import Command
from .checks import get_status_checks


class StartCommand(Command):
    name = "start"
    description = "Shows this message"
    _section_order = [
        ("Core", {"start", "status"}),
        ("Control", {"service", "reboot", "restartbot", "logs"}),
        ("Monitoring", {"top", "temp", "check_updates", "upgrade_bot"}),
        ("Containers", {"docker_status", "docker_list", "docker_restart"}),
        ("Network", {"network_tests", "ping", "wol"}),
        ("Media", {"emby_status", "adguard_status"}),
    ]

    def __init__(self, config: BottyConfig, commands: list[Command]) -> None:
        super().__init__(config)
        self.commands = commands

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a message when the command /start is issued."""
        message = self._require_message(update)
        user = update.effective_user
        greeting = user.mention_html() if user is not None else "there"

        # Build grouped command list for better readability on mobile Telegram UI.
        grouped: dict[str, list[str]] = {section: [] for section, _ in self._section_order}
        grouped["Other"] = []
        for cmd in self.commands:
            cmd_name = str(cmd.name)
            cmd_desc = str(cmd.description)
            line = (
                f"• /{html.escape(cmd_name, quote=True)} "
                f"— {html.escape(cmd_desc, quote=True)}"
            )

            section_name = "Other"
            for candidate_section, names in self._section_order:
                if cmd_name in names:
                    section_name = candidate_section
                    break
            grouped[section_name].append(line)

        sections: list[str] = []
        for section_name, _ in self._section_order:
            items = grouped.get(section_name, [])
            if not items:
                continue
            sections.append(f"<b>{section_name}</b>\n" + "\n".join(items))
        if grouped["Other"]:
            sections.append("<b>Other</b>\n" + "\n".join(grouped["Other"]))

        await message.reply_html(
            rf"Hi {greeting}!\n\n"
            f"<b>Available Commands</b>\n\n"
            + "\n\n".join(sections)
        )


class StatusCommand(Command):
    name = "status"
    description = "General server health"

    @staticmethod
    def _parse_uptime(raw: str) -> str | None:
        text = raw.strip()
        if not text or text.lower().startswith("error:"):
            return None
        if text.startswith("up "):
            return text[3:].strip()
        return text

    @staticmethod
    def _parse_memory(raw: str) -> str | None:
        text = raw.strip()
        if not text or text.lower().startswith("error:"):
            return None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("Mem:"):
                parts = line.split()
                # free -h: Mem: total used free shared buff/cache available
                if len(parts) >= 4:
                    total, used, free = parts[1], parts[2], parts[3]
                    return f"used {used}/{total}, free {free}"
        return None

    @staticmethod
    def _parse_disk(raw: str) -> str | None:
        text = raw.strip()
        if not text or text.lower().startswith("error:"):
            return None
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None
        data_line = lines[1] if lines[0].lower().startswith("filesystem") and len(lines) > 1 else lines[0]
        parts = data_line.split()
        # df -h /: filesystem size used avail use% mount
        if len(parts) >= 6:
            filesystem, size, used, avail, usep, mount = parts[:6]
            return (
                f"{filesystem} {used}/{size} \\({usep}\\), "
                f"avail {avail}, mount {escape_markdown(mount)}"
            )
        return None

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Provides a general server health check."""
        reply_message = self._require_message(update)
        uptime, disk_usage, memory_usage = await get_status_checks()

        uptime_line = self._parse_uptime(uptime)
        memory_line = self._parse_memory(memory_usage)
        disk_line = self._parse_disk(disk_usage)

        message = "*Server Status*\n"
        if uptime_line:
            message += f"\\- *Uptime:* `{escape_markdown_code(uptime_line)}`\n"
        else:
            message += f"\\- *Uptime:*\n```\n{escape_markdown_code(uptime)}\n```\n"

        if memory_line:
            message += f"\\- *Memory:* `{escape_markdown_code(memory_line)}`\n"
        else:
            message += f"\\- *Memory:*\n```\n{escape_markdown_code(memory_usage)}\n```\n"

        if disk_line:
            message += f"\\- *Disk \\(/\\):* `{escape_markdown_code(disk_line)}`"
        else:
            message += f"\\- *Disk \\(/\\):*\n```\n{escape_markdown_code(disk_usage)}\n```"

        await self._reply_markdown(reply_message, message)


__all__ = ["StartCommand", "StatusCommand"]
