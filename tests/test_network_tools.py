import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from botty.cmd.handlers.network_tools.command import PingCommand, WolCommand

@pytest.fixture
def mock_update():
    update = AsyncMock()
    message = AsyncMock()
    update.message = message
    update.effective_message = message
    return update

@pytest.fixture
def mock_context():
    context = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_ping_command(mock_update, mock_context):
    cmd = PingCommand(AsyncMock())
    mock_context.args = ["google.com"]
    
    with patch("botty.cmd.handlers.network_tools.command.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "PING google.com\n64 bytes from..."
        await cmd.run(mock_update, mock_context)
        
        mock_run.assert_called_with(["ping", "-c", "3", "google.com"])
        args, _ = mock_update.message.reply_text.call_args
        assert "Ping Result" in args[0]
        assert "64 bytes from" in args[0]

@pytest.mark.asyncio
async def test_wol_command_success(mock_update, mock_context):
    cmd = WolCommand(AsyncMock())
    mock_context.args = ["AA:BB:CC:DD:EE:FF"]
    
    with patch("socket.socket") as mock_socket:
        mock_sock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        
        await cmd.run(mock_update, mock_context)
        
        mock_sock_instance.sendto.assert_called()
        args, _ = mock_update.message.reply_text.call_args
        assert "Magic packet sent" in args[0]

@pytest.mark.asyncio
async def test_wol_command_invalid_mac(mock_update, mock_context):
    cmd = WolCommand(AsyncMock())
    mock_context.args = ["INVALID"]
    
    await cmd.run(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "Invalid MAC address format" in args[0]
