from unittest.mock import AsyncMock, patch

import pytest

from botty.cmd.handlers.monitoring.command import LogsCommand, TempCommand, TopCommand

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
async def test_top_command(mock_update, mock_context):
    cmd = TopCommand(AsyncMock())
    
    with patch("botty.cmd.handlers.monitoring.command.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "PID CMD %CPU %MEM\n1 systemd 0.0 0.1"
        await cmd.run(mock_update, mock_context)
        
        # Should call ps
        mock_run.assert_called()
        args, _ = mock_update.message.reply_text.call_args
        assert "Top Processes" in args[0]
        assert "systemd" in args[0]

@pytest.mark.asyncio
async def test_temp_command_sensors(mock_update, mock_context):
    cmd = TempCommand(AsyncMock())
    
    with patch("botty.cmd.handlers.monitoring.command.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "coretemp-isa-0000\nAdapter: ISA adapter\nPackage id 0:  +45.0°C"
        await cmd.run(mock_update, mock_context)
        
        args, _ = mock_update.message.reply_text.call_args
        assert "System Temperatures (sensors)" in args[0]
        assert "+45.0°C" in args[0]

@pytest.mark.asyncio
async def test_logs_command_no_args(mock_update, mock_context):
    cmd = LogsCommand(AsyncMock())
    mock_context.args = []
    
    await cmd.run(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "Usage: `/logs" in args[0]

@pytest.mark.asyncio
async def test_logs_command_success(mock_update, mock_context):
    cmd = LogsCommand(AsyncMock())
    mock_context.args = ["botty"]
    
    with patch("botty.cmd.handlers.base.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "Feb 13 12:00:00 botty[123]: Started"
        await cmd.run(mock_update, mock_context)

        mock_run.assert_called_with(
            ["journalctl", "-u", "botty", "-n", "20", "--no-pager"],
            timeout=10.0,
            sudo=True,
        )
        args, _ = mock_update.message.reply_text.call_args
        assert "Logs for botty" in args[0]
        assert "Started" in args[0]
