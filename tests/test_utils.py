import asyncio

import pytest

from botty.utils import escape_markdown, escape_markdown_code, run_command, verify_totp


class _FakeProcess:
    def __init__(self, *, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.communicate_input = None

    async def communicate(self, input=None):
        self.communicate_input = input
        return self._stdout, self._stderr

    def kill(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_command_success():
    """Test that run_command successfully executes a command and returns stdout."""
    command = ["echo", "hello test"]
    result = await run_command(command)
    assert result.strip() == "hello test"


@pytest.mark.asyncio
async def test_run_command_failure():
    """Test that run_command captures stderr when a command fails."""
    command = ["ls", "non_existent_directory_for_testing"]
    result = await run_command(command)
    assert "Error:" in result
    assert "No such file or directory" in result


@pytest.mark.asyncio
async def test_run_command_missing_executable():
    """Test missing executable returns a safe error string (no exception)."""
    result = await run_command(["__definitely_missing_binary__"])
    assert "Error:" in result
    assert "No such file or directory" in result


@pytest.mark.asyncio
async def test_run_command_timeout():
    """Test that run_command handles timeouts correctly."""
    command = ["sleep", "2"]
    # Use a short timeout to trigger the exception
    result = await run_command(command, timeout=0.1)
    assert "Error: Command timed out after 0.1 seconds" in result


@pytest.mark.asyncio
async def test_run_command_sudo_without_password_uses_noninteractive(monkeypatch):
    captured = {}
    fake_process = _FakeProcess(stdout=b"ok\n")

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.delenv("BOTTY_SUDO_PASSWORD", raising=False)
    monkeypatch.setattr("botty.utils.asyncio.create_subprocess_exec", _fake_exec)
    result = await run_command(["true"], sudo=True)

    assert result.strip() == "ok"
    assert captured["args"][1] == "-n"
    assert captured["kwargs"]["stdin"] == asyncio.subprocess.DEVNULL
    assert fake_process.communicate_input is None


@pytest.mark.asyncio
async def test_run_command_sudo_with_password_uses_stdin(monkeypatch):
    captured = {}
    fake_process = _FakeProcess(stdout=b"ok\n")

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.setenv("BOTTY_SUDO_PASSWORD", "secret")
    monkeypatch.setattr("botty.utils.asyncio.create_subprocess_exec", _fake_exec)
    result = await run_command(["id"], sudo=True)

    assert result.strip() == "ok"
    assert "-S" in captured["args"]
    assert captured["kwargs"]["stdin"] == asyncio.subprocess.PIPE
    assert fake_process.communicate_input == b"secret\n"


@pytest.mark.asyncio
async def test_run_command_passes_cwd(monkeypatch):
    captured = {}
    fake_process = _FakeProcess(stdout=b"ok\n")

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.setattr("botty.utils.asyncio.create_subprocess_exec", _fake_exec)
    result = await run_command(["pwd"], cwd="/tmp")

    assert result.strip() == "ok"
    assert captured["kwargs"]["cwd"] == "/tmp"


def test_escape_markdown():
    """Test the escape_markdown function (for non-code text)."""
    # No special characters
    assert escape_markdown("Hello World") == "Hello World"

    # Mixed characters
    assert escape_markdown("Status: (Active)") == r"Status: \(Active\)"
    assert escape_markdown("user_id=123") == r"user\_id\=123"

    # All special characters
    special_chars = r"_*[]()~`>#+-=|{}.!"
    escaped_chars = r"\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"
    assert escape_markdown(special_chars) == escaped_chars


def test_escape_markdown_code():
    """Test the escape_markdown_code function (for code blocks)."""
    # Only backslash and backtick should be escaped
    text = r"Active: active (running) since Sat 2026-02-02 12:00:00; 1h ago"
    assert escape_markdown_code(text) == text  # No changes expected

    text_with_specials = r"Path: C:\Windows\System32 `code`"
    expected = r"Path: C:\\Windows\\System32 \`code\`"
    assert escape_markdown_code(text_with_specials) == expected


def test_verify_totp_accepts_valid_code():
    # RFC6238 test secret (base32). At t=59, SHA1 8-digit is 94287082, so 6-digit is 287082.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert verify_totp("287082", secret, at_time=59, window_steps=0) is True


def test_verify_totp_rejects_invalid_code_and_secret():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert verify_totp("000000", secret, at_time=59, window_steps=0) is False
    assert verify_totp("287082", "not-base32", at_time=59, window_steps=0) is False
