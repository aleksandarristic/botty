import re

from telegram import Update
from telegram.ext import ContextTypes

from botty.cmd.handlers.base import Command
from botty.utils import escape_markdown, escape_markdown_code


class CheckUpdatesCommand(Command):
    name = "check_updates"
    description = "Check for system updates (apt)"

    max_display_updates: int = 25

    @staticmethod
    def _parse_upgradable_packages(raw_output: str) -> list[tuple[str, str, str]]:
        entries: list[tuple[str, str, str]] = []
        pattern = re.compile(
            r"^(?P<pkg>\S+)\s+(?P<new>\S+)\s+\S+\s+\[upgradable from:\s*(?P<old>[^\]]+)\]$"
        )
        for line in raw_output.splitlines():
            line = line.strip()
            if (
                not line
                or line == "Listing..."
                or line.startswith("WARNING:")
                or line.startswith("Use with caution")
            ):
                continue
            match = pattern.match(line)
            if not match:
                continue
            entries.append((match.group("pkg"), match.group("old"), match.group("new")))
        return entries

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /check_updates
        """
        reply_message = self._require_message(update)
        
        # apt list --upgradable
        # apt might complain if not root but usually 'apt list' is fine for users.
        # But 'apt update' requires sudo.
        # We should probably run 'sudo apt update' first to get latest list?
        # That's slow and risky (modifies system state).
        # Let's just list what is currently known.
        
        cmd = ["apt", "list", "--upgradable"]
        output = await self._run_command(cmd)

        if output.strip().lower().startswith("error:"):
            await self._reply_markdown(
                reply_message,
                "*Available Updates*\n"
                "Could not query apt updates on this host.\n"
                f"```\n{escape_markdown_code(output)}\n```",
            )
            return

        entries = self._parse_upgradable_packages(output)
        if not entries:
            await self._reply_markdown(reply_message, "*Available Updates*\nNo updates found\\.")
            return

        shown = entries[: self.max_display_updates]
        message = f"*Available Updates* \\({len(entries)}\\)\n"
        for pkg, old, new in shown:
            message += (
                f"\\- `{escape_markdown_code(pkg)}`: "
                f"`{escape_markdown_code(old)}` → `{escape_markdown_code(new)}`\n"
            )
        if len(entries) > len(shown):
            remaining = len(entries) - len(shown)
            message += f"\\- _and {escape_markdown(str(remaining))} more_"

        await self._reply_markdown(reply_message, message.rstrip())


class UpgradeBotCommand(Command):
    name = "upgrade_bot"
    description = "Pull latest botty code and restart"
    requires_totp = True

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /upgrade_bot confirm
        """
        reply_message = self._require_message(update)
        
        if not context.args or (context.args and context.args[0].lower() != "confirm") or not context.args:
             await self._reply_markdown(
                reply_message,
                "⚠️ *Upgrade requested*\n"
                "This will pull the latest code from git and restart the service.\n"
                "To confirm, run: `/upgrade_bot confirm`"
            )
             return

        await self._reply_markdown(reply_message, "Pulling latest changes...")
        
        pull_output = await self._run_command(["git", "pull"])
        
        if "Already up to date" in pull_output:
             await self._reply_markdown(
                reply_message,
                f"Bot is already up to date.\n```\n{escape_markdown_code(pull_output)}\n```"
            )
             return
             
        await self._reply_markdown(
             reply_message,
             f"Git pull successful. Restarting service...\n```\n{escape_markdown_code(pull_output)}\n```"
        )
        
        # Restart service
        # This will kill the bot process.
        await self._run_command(["systemctl", "restart", "botty"], sudo=True)
