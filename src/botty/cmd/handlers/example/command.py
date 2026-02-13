from telegram import Update
from telegram.ext import ContextTypes

from botty.utils import run_command, escape_markdown_code
from botty.cmd.handlers.base import Command


class ExampleCommand(Command):
    """
    ExampleCommand serves as a blueprint for creating new bot commands.
    
    To implement a new command:
    1. Define the 'name' (used as the /command).
    2. Define the 'description' (shown in /start).
    3. (Optional) Set 'auth_required = False' if the command should be public.
    4. Implement the 'run' method with your logic.
    5. Add the class to ALL_COMMAND_CLASSES in src/botty/cmd/handlers/__init__.py.
    """

    # The command string the user types (e.g., /example)
    name = "example"
    
    # Description shown in the /start help menu
    description = "Example command with args and command execution"
    
    # Whether only authorized users (AUTHORIZED_USER_ID) can run this
    auth_required = True

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Executes the command logic.
        """
        reply_message = self._require_message(update)
        # --- EXAMPLE 1: Using run_command for shell execution ---
        # run_command takes a list of strings and returns the combined stdout/stderr.
        # It has a default timeout of 10 seconds.
        uptime_raw = await run_command(["uptime", "-p"])
        
        # Always escape text from the shell if it goes into a code block
        uptime_escaped = escape_markdown_code(uptime_raw.strip())

        # --- EXAMPLE 2: Accessing Config ---
        # You can access any value defined in BottyConfig via self.config
        media_path = self.config.media_path
        
        # --- EXAMPLE 3: Command arguments ---
        # Telegram arguments are available via context.args
        echo_arg = " ".join(context.args).strip() if context.args else "(no args)"

        # --- EXAMPLE 4: Complex Formatting ---
        message = (
            "*Command Example*\n\n"
            f"*Media Path:* `{escape_markdown_code(media_path)}`\n"
            f"*Uptime:* `{uptime_escaped}`\n"
            f"*Echo args:* `{escape_markdown_code(echo_arg)}`\n\n"
            "*Next Steps:*\n"
            "1\\. Edit `src/botty/cmd/handlers/example/command.py`\n"
            "2\\. Use `await run_command(['ls', '-la'])` to check files\n"
            "3\\. Use `self.config.gohome_api_url` for API calls\n"
            "4\\. Try `/example hello world` to see `context.args`"
        )

        await self._reply_markdown(reply_message, message)


__all__ = ["ExampleCommand"]
