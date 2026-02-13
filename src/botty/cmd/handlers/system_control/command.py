from telegram import Update
from telegram.ext import ContextTypes

from botty.cmd.handlers.base import Command
from botty.utils import escape_markdown_code


class ServiceCommand(Command):
    name = "service"
    description = "Manage system services (start/stop/restart/status)"
    sudo = True

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /service <service_name> <action>
        Actions: start, stop, restart, status
        """
        reply_message = self._require_message(update)
        
        if not context.args or len(context.args) < 2:
            await self._reply_markdown(
                reply_message,
                "Usage: `/service <service_name> <action>`\n"
                "Actions: `start`, `stop`, `restart`, `status`"
            )
            return

        service_name = context.args[0]
        action = context.args[1].lower()
        
        allowed_actions = ["start", "stop", "restart", "status"]
        if action not in allowed_actions:
            await self._reply_markdown(
                reply_message,
                f"Invalid action: `{escape_markdown_code(action)}`\n"
                f"Allowed actions: `{', '.join(allowed_actions)}`"
            )
            return

        # Sanitize service name minimally to prevent obvious injection
        if not service_name.replace("-", "").replace(".", "").replace("_", "").isalnum():
             await self._reply_markdown(
                reply_message,
                "Invalid service name."
            )
             return

        cmd = ["systemctl", action, service_name]
        
        # For status, we want to capture output. For others, just success/fail mostly, 
        # but systemctl usually outputs nothing on success (except status).
        
        output = await self._run_command(cmd)
        
        # If output is empty (common for success on start/stop/restart), say "Done".
        if not output.strip() and action != "status":
            output = f"Service {service_name} {action}ed."
            
        await self._reply_markdown(
            reply_message,
            f"*Service {action.capitalize()}*\n```\n{escape_markdown_code(output)}\n```"
        )

    def requires_totp_for(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not context.args or len(context.args) < 2:
            return False
        action = context.args[1].lower()
        return action in {"start", "stop", "restart"}


class RebootCommand(Command):
    name = "reboot"
    description = "Reboot the server"
    sudo = True
    requires_totp = True

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /reboot confirm
        """
        reply_message = self._require_message(update)
        
        if not context.args or (context.args and context.args[0].lower() != "confirm") or not context.args:
             await self._reply_markdown(
                reply_message,
                "⚠️ *Reboot requested*\n"
                "To confirm, run: `/reboot confirm`"
            )
             return
             
        await self._reply_markdown(reply_message, "Rebooting system now...")
        
        # Fire and forget mostly, or wait a bit. 
        # The bot will die shortly after this.
        await self._run_command(["reboot"])
