from .docker import DockerStatusCommand
from .media import AdguardStatusCommand, EmbyStatusCommand
from .network import NetworkTestsCommand
from .status import StartCommand, StatusCommand
from .example import ExampleCommand

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
# We include StartCommand and the registration list, plus all individual classes.
__all__ = [
    "StartCommand",
    "ALL_COMMAND_CLASSES",
] + [cls.__name__ for cls in ALL_COMMAND_CLASSES]
