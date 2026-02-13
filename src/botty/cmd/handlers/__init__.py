from .adguard import AdguardStatusCommand
from .docker import DockerStatusCommand
from .example import ExampleCommand
from .media import EmbyStatusCommand
from .network import NetworkTestsCommand
from .status import StartCommand, StatusCommand

# List of command classes that can be optionally enabled via configuration.
# StartCommand is excluded here as it is always enabled and handled specially.
ALL_COMMAND_CLASSES = [
    StatusCommand,
    EmbyStatusCommand,
    AdguardStatusCommand,
    NetworkTestsCommand,
    ExampleCommand,
    DockerStatusCommand,
]

# Define the public API for this subpackage.
# Keep this static so type checkers can resolve exports.
__all__ = [
    "AdguardStatusCommand",
    "DockerStatusCommand",
    "ExampleCommand",
    "EmbyStatusCommand",
    "NetworkTestsCommand",
    "StartCommand",
    "StatusCommand",
    "ALL_COMMAND_CLASSES",
]
