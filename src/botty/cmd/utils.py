import os
import re
import subprocess
from functools import wraps
from typing import List

# Parse authorized user IDs from a comma-separated string
auth_env = os.getenv("AUTHORIZED_USER_ID", "")
AUTHORIZED_USER_IDS = [uid.strip() for uid in auth_env.split(",") if uid.strip()]


def is_authorized(update) -> bool:
    return str(update.effective_user.id) in AUTHORIZED_USER_IDS


def _extract_update(args, kwargs):
    if "update" in kwargs:
        return kwargs["update"]
    if not args:
        return None
    if hasattr(args[0], "effective_user"):
        return args[0]
    if len(args) > 1 and hasattr(args[1], "effective_user"):
        return args[1]
    return None


def authorized_only(func):
    """Decorator to restrict access to authorized users only."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Support both functions (update, context) and bound methods (self, update, context).
        update = _extract_update(args, kwargs)
        if update is None:
            raise TypeError("authorized_only could not find Update argument")

        user_id = str(update.effective_user.id)
        if user_id not in AUTHORIZED_USER_IDS:
            await update.message.reply_text(
                "You are not authorized to use this command."
            )
            return
        return await func(*args, **kwargs)

    return wrapper


async def run_command(command: List[str], timeout: float = 10.0) -> str:
    """Runs a subprocess and returns the output, with an optional timeout."""
    if not command:
        return "Error: No command provided"

    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except FileNotFoundError as exc:
        return f"Error: {exc}"

    if result.stderr:
        return f"Error: {result.stderr}"
    return result.stdout


def escape_markdown(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (outside of code blocks)."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    # We need 3 backslashes in the file: r"\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def escape_markdown_code(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (inside inline code/pre blocks)."""
    # Only backslash and backtick need escaping inside code blocks
    return text.replace("\\", "\\\\").replace("`", "\\`")
