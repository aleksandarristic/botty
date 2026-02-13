from botty.config import BottyConfig
from .handlers import ALL_COMMAND_CLASSES, StartCommand


def _normalize_command_metadata(commands) -> None:
    """Ensure commands have safe, displayable metadata."""
    for cmd in commands:
        description = getattr(cmd, "description", None)
        if not isinstance(description, str) or not description.strip():
            cmd.description = "No description provided."


def get_command_registry(config: BottyConfig):
    """
    Returns a list of command instances based on the configuration.
    """
    enabled_instances = []

    for cmd_class in ALL_COMMAND_CLASSES:
        if config.enabled_commands is None or cmd_class.name in config.enabled_commands:
            enabled_instances.append(cmd_class(config))

    # StartCommand is always enabled and needs to know about other commands
    # We first create it with an empty list, then populate it
    start_cmd = StartCommand(config, [])
    all_enabled = [start_cmd] + enabled_instances
    _normalize_command_metadata(all_enabled)
    start_cmd.commands = all_enabled

    return [(cmd.name, cmd.handler) for cmd in all_enabled]
