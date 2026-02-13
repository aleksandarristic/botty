from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botty.cmd import get_command_registry
from botty.cmd.handlers.base import Command
from botty.config import BottyConfig
from botty.cmd.handlers import (
    AdguardStatusCommand,
    DockerStatusCommand,
    EmbyStatusCommand,
    ExampleCommand,
    NetworkTestsCommand,
    StartCommand,
    StatusCommand,
)

# Set a consistent authorized user ID for testing
TEST_AUTHORIZED_USER_ID = "12345"


@pytest.fixture
def test_config():
    """Fixture to create a standard test config."""
    return BottyConfig(
        telegram_bot_token="test_token",
        authorized_user_ids=[TEST_AUTHORIZED_USER_ID],
        enabled_commands=None,
        gohome_api_url="http://localhost:8080/status",
        gohome_timeout_seconds=10.0,
        emby_data_path="/mnt/embydata",
        media_path="/mnt/media",
    )


@pytest.fixture
def mock_update():
    """Fixture to create a mock telegram.Update object."""
    update = MagicMock()
    update.effective_user.id = int(TEST_AUTHORIZED_USER_ID)
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_start_command(mock_update, test_config):
    """Test the /start command handler."""
    status_cmd = StatusCommand(test_config)
    cmd = StartCommand(test_config, [status_cmd])
    await cmd.handle(mock_update, None)
    mock_update.message.reply_html.assert_called_once()
    call_args = mock_update.message.reply_html.call_args[0][0]
    assert "Hi" in call_args
    assert "/status" in call_args


@pytest.mark.asyncio
async def test_start_command_escapes_html(mock_update, test_config):
    class HtmlCommand(Command):
        name = "x<y"
        description = "Dangerous <b>tag</b> & value"

        async def run(self, update, context):
            return None

    cmd = StartCommand(test_config, [HtmlCommand(test_config)])
    await cmd.handle(mock_update, None)

    call_args = mock_update.message.reply_html.call_args[0][0]
    assert "/x&lt;y - Dangerous &lt;b&gt;tag&lt;/b&gt; &amp; value" in call_args


def test_registry_fills_missing_description(test_config, monkeypatch):
    class NoDescriptionCommand(Command):
        name = "no_description"

        async def run(self, update, context):
            return None

    monkeypatch.setattr("botty.cmd.ALL_COMMAND_CLASSES", [NoDescriptionCommand])
    registry = get_command_registry(test_config)
    handlers = dict(registry)
    command_instance = handlers["no_description"].__self__
    assert command_instance.description == "No description provided."


@pytest.mark.asyncio
async def test_unauthorized_user(mock_update, test_config):
    """Test that an unauthorized user is rejected."""
    test_config.authorized_user_ids = ["a_different_id"]
    mock_update.effective_user.id = 99999  # Unauthorized ID

    cmd = StatusCommand(test_config)
    # We can test any command that has the auth check
    await cmd.handle(mock_update, None)

    mock_update.message.reply_text.assert_called_once_with(
        "You are not authorized to use this command."
    )


@pytest.mark.asyncio
@patch("botty.cmd.handlers.status.get_status_checks")
async def test_status_command(mock_run_command, mock_update, test_config):
    """Test the /status command handler."""
    mock_run_command.return_value = ("up 2 days", "disk usage /", "memory usage")

    cmd = StatusCommand(test_config)
    await cmd.handle(mock_update, None)

    mock_run_command.assert_called_once_with()

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "up 2 days" in call_args
    assert "disk usage /" in call_args
    assert "memory usage" in call_args


@pytest.mark.asyncio
@patch("botty.cmd.handlers.media.get_emby_checks")
async def test_emby_status_command(mock_run_command, mock_update, test_config):
    """Test the /emby_status command handler."""
    test_config.emby_data_path = "/fake/embydata"
    test_config.media_path = "/fake/media"

    mock_run_command.return_value = (
        "emby is running",
        "embydata usage",
        "media usage",
    )

    cmd = EmbyStatusCommand(test_config)
    await cmd.handle(mock_update, None)

    mock_run_command.assert_called_once_with(test_config)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "emby is running" in call_args
    assert "/fake/embydata" in call_args
    assert "/fake/media" in call_args


@pytest.mark.asyncio
@patch("botty.cmd.handlers.media.get_adguard_checks")
async def test_adguard_status_command(mock_run_command, mock_update, test_config):
    """Test the /adguard_status command handler."""
    mock_run_command.return_value = "adguard is running"

    cmd = AdguardStatusCommand(test_config)
    await cmd.handle(mock_update, None)

    mock_run_command.assert_called_once_with()
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "adguard is running" in call_args


@pytest.mark.asyncio
@patch("botty.services.http.httpx.AsyncClient")
async def test_network_tests_command_success(MockAsyncClient, mock_update, test_config):
    """Test the /network_tests command on a successful API call."""
    test_config.gohome_api_url = "http://example.local/status"
    cmd = NetworkTestsCommand(test_config)
    cmd._cache_timestamp = None
    cmd._cache_message = None
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "speedtest": {
            "Available": True,
            "DownloadMbps": 491.17468,
            "UploadMbps": 235.042288,
            "PingMs": 2.217,
            "LastUpdatedText": "1h ago",
            "NextScheduledISO": "2026-02-02T12:19:56+01:00",
        },
        "ping": {
            "Available": True,
            "Targets": [
                {"Name": "Cloudflare DNS", "AvgMs": 3.625, "PacketLoss": 0},
                {"Name": "Quad9", "AvgMs": 4.457, "PacketLoss": 0},
            ],
        },
        "device": {
            "Available": True,
            "TemperatureC": 61.8,
            "UptimeText": "2d 1h 50m",
            "MemoryUsedMB": 1024.0,
            "MemoryTotalMB": 2048.0,
            "Load1": 0.06,
            "Load5": 0.02,
            "Load15": 0.01,
        },
    }

    mock_get = AsyncMock(return_value=mock_response)
    MockAsyncClient.return_value.__aenter__.return_value.get = mock_get

    await cmd.handle(mock_update, None)

    mock_get.assert_called_once_with(test_config.gohome_api_url)
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]

    # Assertions based on formatted output
    assert "Download: 491.17 Mbps" in call_args
    assert "Updated:  1h ago" in call_args
    assert "Next Run: 2026-02-02T12:19:56+01:00" in call_args
    assert "Cloudflare DNS :   3.62 ms" in call_args
    assert "Memory:   1.00/2.00 GB used" in call_args
    assert "Loads:    0.06, 0.02, 0.01" in call_args
    assert "```" in call_args  # Verify code blocks are present


@pytest.mark.asyncio
@patch("botty.services.http.httpx.AsyncClient")
async def test_network_tests_command_failure(MockAsyncClient, mock_update, test_config):
    """Test the /network_tests command on a failed API call."""
    cmd = NetworkTestsCommand(test_config)
    cmd._cache_timestamp = None
    cmd._cache_message = None
    mock_get = AsyncMock()
    mock_get.side_effect = Exception("Test API failure")
    MockAsyncClient.return_value.__aenter__.return_value.get = mock_get

    await cmd.handle(mock_update, None)

    mock_update.message.reply_text.assert_called_once_with(
        "An error occurred: Test API failure", parse_mode="MarkdownV2"
    )


@pytest.mark.asyncio
@patch("botty.cmd.handlers.example.run_command", new_callable=AsyncMock)
async def test_example_command_with_args(mock_run_command, mock_update, test_config):
    mock_run_command.return_value = "up 10 minutes"
    context = MagicMock()
    context.args = ["hello", "world"]

    cmd = ExampleCommand(test_config)
    await cmd.handle(mock_update, context)

    mock_run_command.assert_called_once_with(["uptime", "-p"])
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "up 10 minutes" in call_args
    assert "hello world" in call_args


@pytest.mark.asyncio
@patch("botty.cmd.handlers.docker.os.path.isfile")
@patch("botty.cmd.handlers.docker.run_command", new_callable=AsyncMock)
async def test_docker_status_with_directory(
    mock_run_command, mock_isfile, mock_update, test_config
):
    mock_run_command.side_effect = ["docker info ok", "compose ps ok"]
    mock_isfile.side_effect = lambda p: p.endswith("docker-compose.yml")
    context = MagicMock()
    context.args = ["/opt/stacks/home"]

    cmd = DockerStatusCommand(test_config)
    await cmd.handle(mock_update, context)

    assert mock_run_command.call_count == 2
    assert mock_run_command.call_args_list[0].args[0] == ["docker", "info"]
    assert mock_run_command.call_args_list[1].args[0] == [
        "docker",
        "compose",
        "-f",
        "/opt/stacks/home/docker-compose.yml",
        "ps",
    ]
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "docker info ok" in call_args
    assert "compose ps ok" in call_args


@pytest.mark.asyncio
@patch("botty.cmd.handlers.docker.run_command", new_callable=AsyncMock)
async def test_docker_status_without_directory(mock_run_command, mock_update, test_config):
    mock_run_command.return_value = "docker info ok"
    context = MagicMock()
    context.args = []

    cmd = DockerStatusCommand(test_config)
    await cmd.handle(mock_update, context)

    mock_run_command.assert_called_once_with(["docker", "info"])
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Not requested. Pass a directory or compose file path." in call_args
