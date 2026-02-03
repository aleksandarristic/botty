import asyncio
import os
from botty.markdown import escape_markdown, escape_markdown_code
import subprocess
import shutil
from typing import List


async def run_command(command: List[str], timeout: float = 10.0) -> str:
    """Runs a subprocess and returns the output, with an optional timeout."""
    if not command:
        return "Error: No command provided"

    executable = command[0]
    if not os.path.isabs(executable):
        resolved = shutil.which(executable)
        if resolved:
            command = [resolved, *command[1:]]

    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        env=env,
    )
    timed_out = False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
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


__all__ = ["run_command", "escape_markdown", "escape_markdown_code"]
