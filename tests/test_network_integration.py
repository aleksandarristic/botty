from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botty.cmd.handlers import network_tests_command
from botty.cmd.handlers import config as handler_config


@pytest.mark.asyncio
@patch("botty.services.http.httpx.AsyncClient")
async def test_network_tests_integration(MockAsyncClient, monkeypatch):
    handler_config.authorized_user_ids = ["123"]
    handler_config.gohome_api_url = "http://stub/status"
    network_tests_command._cache_timestamp = None
    network_tests_command._cache_message = None

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "speedtest": {
            "Available": True,
            "DownloadMbps": 100.0,
            "UploadMbps": 50.0,
            "PingMs": 5.0,
            "LastUpdatedText": "just now",
            "NextScheduledISO": "2026-02-03T12:00:00Z",
        },
        "ping": {"Available": False},
        "device": {"Available": False},
    }

    mock_get = AsyncMock(return_value=mock_response)
    MockAsyncClient.return_value.__aenter__.return_value.get = mock_get

    update = MagicMock()
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()

    await network_tests_command.handle(update, None)

    mock_get.assert_called_once_with("http://stub/status")
    update.message.reply_text.assert_called_once()
    message = update.message.reply_text.call_args[0][0]
    assert "Download: 100.00 Mbps" in message
    assert "Ping:" in message
