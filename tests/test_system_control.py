import pytest
from unittest.mock import AsyncMock, patch
from botty.cmd.handlers.system_control.command import ServiceCommand, RebootCommand

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
async def test_service_command_invalid_args(mock_update, mock_context):
    cmd = ServiceCommand(AsyncMock())
    mock_context.args = []
    
    await cmd.run(mock_update, mock_context)
    
    assert mock_update.message.reply_text.called
    args, _ = mock_update.message.reply_text.call_args
    assert "Usage: `/service" in args[0]

@pytest.mark.asyncio
async def test_service_command_success(mock_update, mock_context):
    cmd = ServiceCommand(AsyncMock())
    mock_context.args = ["nginx", "restart"]
    
    with patch("botty.cmd.handlers.system_control.command.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = ""
        await cmd.run(mock_update, mock_context)
        
        mock_run.assert_called_with(["sudo", "systemctl", "restart", "nginx"])
        assert mock_update.message.reply_text.called
        args, _ = mock_update.message.reply_text.call_args
        assert "Service Restarted" in args[0] or "Service restart" in args[0] or "Service nginx restarted" in args[0]

@pytest.mark.asyncio
async def test_reboot_command_no_confirm(mock_update, mock_context):
    cmd = RebootCommand(AsyncMock())
    mock_context.args = []
    
    await cmd.run(mock_update, mock_context)
    
    assert mock_update.message.reply_text.called
    args, _ = mock_update.message.reply_text.call_args
    assert "To confirm, run: `/reboot confirm`" in args[0]

@pytest.mark.asyncio
async def test_reboot_command_confirm(mock_update, mock_context):
    cmd = RebootCommand(AsyncMock())
    mock_context.args = ["confirm"]
    
    with patch("botty.cmd.handlers.system_control.command.run_command", new_callable=AsyncMock) as mock_run:
        await cmd.run(mock_update, mock_context)
        
        mock_run.assert_called_with(["sudo", "reboot"])
        assert mock_update.message.reply_text.called
        args, _ = mock_update.message.reply_text.call_args
        assert "Rebooting system now" in args[0]
