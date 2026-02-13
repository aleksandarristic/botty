from unittest.mock import AsyncMock, patch

import pytest

from botty.cmd.handlers.maintenance.command import CheckUpdatesCommand, UpgradeBotCommand

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
async def test_check_updates_command(mock_update, mock_context):
    cmd = CheckUpdatesCommand(AsyncMock())
    
    with patch("botty.cmd.handlers.base.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "Listing...\npython3/stable 3.12.0 amd64 [upgradable from: 3.11.0]"
        await cmd.run(mock_update, mock_context)
        
        mock_run.assert_called_with(["apt", "list", "--upgradable"], timeout=10.0, sudo=False)
        args, _ = mock_update.message.reply_text.call_args
        assert "Available Updates" in args[0]
        assert "python3/stable" in args[0]
        assert "Listing..." not in args[0]

@pytest.mark.asyncio
async def test_upgrade_bot_command_no_confirm(mock_update, mock_context):
    cmd = UpgradeBotCommand(AsyncMock())
    mock_context.args = []
    
    await cmd.run(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "Upgrade requested" in args[0]

@pytest.mark.asyncio
async def test_upgrade_bot_command_confirm(mock_update, mock_context):
    cmd = UpgradeBotCommand(AsyncMock())
    mock_context.args = ["confirm"]
    
    with patch("botty.cmd.handlers.base.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "Updating abc..def"
        await cmd.run(mock_update, mock_context)
        
        # Should call git pull and systemctl restart
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["git", "pull"], timeout=10.0, sudo=False)
        mock_run.assert_any_call(["systemctl", "restart", "botty"], timeout=10.0, sudo=True)
        
        # Check messages
        # reply_text is called 2 times: "Pulling..." and "Restarting..."
        assert mock_update.message.reply_text.call_count == 2
        args, _ = mock_update.message.reply_text.call_args_list[1]
        assert "Restarting service" in args[0]
