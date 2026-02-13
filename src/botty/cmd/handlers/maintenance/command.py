from telegram import Update
from telegram.ext import ContextTypes

from botty.cmd.handlers.base import Command
from botty.utils import escape_markdown_code


class CheckUpdatesCommand(Command):
    name = "check_updates"
    description = "Check for system updates (apt)"

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
        
        if "Listing..." in output:
             lines = output.splitlines()
             # Filter out "Listing..."
             lines = [line for line in lines if line != "Listing..."]
             output = "\n".join(lines)

        if not output.strip():
             output = "No updates found."
             
        await self._reply_markdown(
            reply_message,
            f"*Available Updates*\n```\n{escape_markdown_code(output)}\n```"
        )


class UpgradeBotCommand(Command):
    name = "upgrade_bot"
    description = "Pull latest botty code and restart"

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
