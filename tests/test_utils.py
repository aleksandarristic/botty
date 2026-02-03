import pytest

from botty.cmd.utils import escape_markdown, escape_markdown_code, run_command


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
async def test_run_command_timeout():
    """Test that run_command handles timeouts correctly."""
    command = ["sleep", "2"]
    # Use a short timeout to trigger the exception
    result = await run_command(command, timeout=0.1)
    assert "Error: Command timed out after 0.1 seconds" in result


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
