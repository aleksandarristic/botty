import asyncio
import re


async def run_command(command: str, timeout: float = 10.0) -> str:
    """Runs a shell command and returns the output, with an optional timeout."""
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if stderr:
            return f"Error: {stderr.decode(errors='replace')}"
        return stdout.decode(errors="replace")
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return f"Error: Command timed out after {timeout} seconds"


def escape_markdown(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (outside of code blocks)."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def escape_markdown_code(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (inside inline code/pre blocks)."""
    # Only backslash and backtick need escaping inside code blocks
    return text.replace("\\", "\\\\").replace("`", "\\`")
