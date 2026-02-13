import pytest
from unittest.mock import AsyncMock, patch
from botty.cmd.handlers.docker.command import DockerListCommand, DockerRestartCommand

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
async def test_docker_list_command(mock_update, mock_context):
    cmd = DockerListCommand(AsyncMock())
    
    with patch("botty.cmd.handlers.docker.command.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "NAMES STATUS\ncontainer1 Up 2 days"
        await cmd.run(mock_update, mock_context)
        
        mock_run.assert_called()
        args, _ = mock_update.message.reply_text.call_args
        assert "Docker Containers" in args[0]
        assert "container1" in args[0]

@pytest.mark.asyncio
async def test_docker_restart_command_no_args(mock_update, mock_context):
    cmd = DockerRestartCommand(AsyncMock())
    mock_context.args = []
    
    await cmd.run(mock_update, mock_context)
    
    args, _ = mock_update.message.reply_text.call_args
    assert "Usage: `/docker_restart" in args[0]

@pytest.mark.asyncio
async def test_docker_restart_command_success(mock_update, mock_context):
    cmd = DockerRestartCommand(AsyncMock())
    mock_context.args = ["my-container"]
    
    with patch("botty.cmd.handlers.docker.command.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "my-container"
        await cmd.run(mock_update, mock_context)
        
        mock_run.assert_called_with(["docker", "restart", "my-container"])
        args, _ = mock_update.message.reply_text.call_args
        assert "Docker Restart" in args[0]
        assert "my-container" in args[0]
