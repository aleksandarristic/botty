import os
import re
import subprocess
from typing import List


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
