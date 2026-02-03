from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botty.cmd import handlers

# Set a consistent authorized user ID for testing
TEST_AUTHORIZED_USER_ID = "12345"


@pytest.fixture
def mock_update():
    """Fixture to create a mock telegram.Update object."""
    update = MagicMock()
    update.effective_user.id = int(TEST_AUTHORIZED_USER_ID)
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_start_command(mock_update, monkeypatch):
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", [TEST_AUTHORIZED_USER_ID])
    """Test the /start command handler."""
    await handlers.start(mock_update, None)
    mock_update.message.reply_html.assert_called_once()
    call_args = mock_update.message.reply_html.call_args[0][0]
    assert "Hi" in call_args
    assert "/help" in call_args


@pytest.mark.asyncio
async def test_unauthorized_user(mock_update, monkeypatch):
    """Test that an unauthorized user is rejected."""
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", ["a_different_id"])
    mock_update.effective_user.id = 99999  # Unauthorized ID

    # We can test any command that has the auth check
    await handlers.status_command(mock_update, None)

    mock_update.message.reply_text.assert_called_once_with(
        "You are not authorized to use this command."
    )


@pytest.mark.asyncio
@patch("botty.cmd.handlers.run_command")
async def test_status_command(mock_run_command, mock_update, monkeypatch):
    """Test the /status command handler."""
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", [TEST_AUTHORIZED_USER_ID])
    mock_run_command.side_effect = [
        "up 2 days",
        "disk usage /",
        "memory usage",
    ]

    await handlers.status_command(mock_update, None)

    assert mock_run_command.call_count == 3
    mock_run_command.assert_any_call(["uptime", "-p"])
    mock_run_command.assert_any_call(["df", "-h", "/"])
    mock_run_command.assert_any_call(["free", "-h"])

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "up 2 days" in call_args
    assert "disk usage /" in call_args
    assert "memory usage" in call_args


@pytest.mark.asyncio
@patch("botty.cmd.handlers.run_command")
async def test_emby_status_command(mock_run_command, mock_update, monkeypatch):
    """Test the /emby_status command handler."""
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", [TEST_AUTHORIZED_USER_ID])
    monkeypatch.setattr(handlers, "EMBY_DATA_PATH", "/fake/embydata")
    monkeypatch.setattr(handlers, "MEDIA_PATH", "/fake/media")

    mock_run_command.side_effect = [
        "emby is running",
        "embydata usage",
        "media usage",
    ]

    await handlers.emby_status_command(mock_update, None)

    assert mock_run_command.call_count == 3
    # Check the exact command with flags and custom paths
    mock_run_command.assert_any_call(
        ["systemctl", "status", "emby-server.service", "--no-pager", "-n", "0"]
    )
    mock_run_command.assert_any_call(["df", "-h", "/fake/embydata"])
    mock_run_command.assert_any_call(["df", "-h", "/fake/media"])

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "emby is running" in call_args
    assert "/fake/embydata" in call_args
    assert "/fake/media" in call_args


@pytest.mark.asyncio
@patch("botty.cmd.handlers.run_command")
async def test_adguard_status_command(mock_run_command, mock_update, monkeypatch):
    """Test the /adguard_status command handler."""
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", [TEST_AUTHORIZED_USER_ID])
    mock_run_command.return_value = "adguard is running"

    await handlers.adguard_status_command(mock_update, None)

    mock_run_command.assert_called_once_with(
        ["systemctl", "status", "AdGuardHome.service", "--no-pager", "-n", "0"]
    )
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "adguard is running" in call_args


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_network_tests_command_success(MockAsyncClient, mock_update, monkeypatch):
    """Test the /network_tests command on a successful API call."""
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", [TEST_AUTHORIZED_USER_ID])
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

    await handlers.network_tests_command(mock_update, None)

    mock_get.assert_called_once_with(handlers.GOHOME_API_URL)
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
@patch("httpx.AsyncClient")
async def test_network_tests_command_failure(MockAsyncClient, mock_update, monkeypatch):
    """Test the /network_tests command on a failed API call."""
    monkeypatch.setattr(handlers, "AUTHORIZED_USER_IDS", [TEST_AUTHORIZED_USER_ID])
    mock_get = AsyncMock()
    mock_get.side_effect = Exception("Test API failure")
    MockAsyncClient.return_value.__aenter__.return_value.get = mock_get

    await handlers.network_tests_command(mock_update, None)

    mock_update.message.reply_text.assert_called_once_with(
        "An error occurred: Test API failure", parse_mode="MarkdownV2"
    )
