import asyncio
import os
import re
import shutil
import subprocess
import time
from typing import List

import pyotp


async def run_command(
    command: List[str],
    timeout: float = 10.0,
    sudo: bool = False,
    sudo_password_env: str = "BOTTY_SUDO_PASSWORD",
) -> str:
    """Runs a subprocess and returns the output, with an optional timeout."""
    if not command:
        return "Error: No command provided"

    sudo_password = os.getenv(sudo_password_env, "")
    if sudo and command[0] != "sudo":
        if sudo_password:
            command = ["sudo", "-S", "-k", "-p", "", *command]
        else:
            # Fail fast when sudo needs a password and no TTY is available.
            command = ["sudo", "-n", *command]

    executable = command[0]
    if not os.path.isabs(executable):
        resolved = shutil.which(executable)
        if resolved:
            command = [resolved, *command[1:]]

    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

    use_sudo_stdin = sudo and bool(sudo_password) and "-S" in command
    stdin = asyncio.subprocess.PIPE if use_sudo_stdin else asyncio.subprocess.DEVNULL
    sudo_input = f"{sudo_password}\n".encode() if use_sudo_stdin else None

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=stdin,
            env=env,
        )
    except FileNotFoundError as exc:
        return f"Error: {exc}"
    timed_out = False
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=sudo_input),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        timed_out = True
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=1.0)
        except asyncio.TimeoutError:
            stdout, stderr = b"", b""

    if timed_out:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=min(timeout, 2.0),
                env=env,
                input=f"{sudo_password}\n" if use_sudo_stdin else None,
            )
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds"
        except FileNotFoundError as exc:
            return f"Error: {exc}"

        stderr_text = result.stderr
        stdout_text = result.stdout
        combined = f"{stdout_text}{stderr_text}"
        if result.returncode != 0:
            return f"Error: (code {result.returncode}) {combined}".rstrip()
        return combined

    stdout_text = stdout.decode(errors="replace")
    stderr_text = stderr.decode(errors="replace")
    combined = f"{stdout_text}{stderr_text}"
    if process.returncode != 0:
        return f"Error: (code {process.returncode}) {combined}".rstrip()
    return combined


def escape_markdown(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (outside of code blocks)."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    # We need 3 backslashes in the file: r"\\\u0001"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def escape_markdown_code(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2 (inside inline code/pre blocks)."""
    # Only backslash and backtick need escaping inside code blocks
    return text.replace("\\", "\\\\").replace("`", "\\`")


def verify_totp(
    code: str,
    secret: str,
    *,
    at_time: float | None = None,
    window_steps: int = 1,
) -> bool:
    """Validates a TOTP code within a small time window."""
    if not re.fullmatch(r"\d{6}", code):
        return False
    if not secret:
        return False

    now = time.time() if at_time is None else at_time
    try:
        return bool(
            pyotp.TOTP(secret).verify(code, for_time=now, valid_window=window_steps)
        )
    except Exception:
        return False


__all__ = [
    "run_command",
    "escape_markdown",
    "escape_markdown_code",
    "verify_totp",
]
