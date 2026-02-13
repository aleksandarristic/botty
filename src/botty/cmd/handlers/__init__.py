from .adguard import AdguardStatusCommand
from .docker import DockerListCommand, DockerRestartCommand, DockerStatusCommand
from .example import ExampleCommand
from .maintenance import CheckUpdatesCommand, UpgradeBotCommand
from .media import EmbyStatusCommand
from .monitoring import LogsCommand, TempCommand, TopCommand
from .network import NetworkTestsCommand
from .network_tools import PingCommand, WolCommand
from .status import StartCommand, StatusCommand
from .system_control import RebootCommand, ServiceCommand

# List of command classes that can be optionally enabled via configuration.
# StartCommand is excluded here as it is always enabled and handled specially.
ALL_COMMAND_CLASSES = [
    StatusCommand,
    EmbyStatusCommand,
    AdguardStatusCommand,
    NetworkTestsCommand,
    ExampleCommand,
    DockerStatusCommand,
    DockerListCommand,
    DockerRestartCommand,
    RebootCommand,
    ServiceCommand,
    LogsCommand,
    TempCommand,
    TopCommand,
    PingCommand,
    WolCommand,
    CheckUpdatesCommand,
    UpgradeBotCommand,
]

# Define the public API for this subpackage.
# Keep this static so type checkers can resolve exports.
__all__ = [
    "AdguardStatusCommand",
    "CheckUpdatesCommand",
    "DockerListCommand",
    "DockerRestartCommand",
    "DockerStatusCommand",
    "ExampleCommand",
    "EmbyStatusCommand",
    "LogsCommand",
    "NetworkTestsCommand",
    "PingCommand",
    "RebootCommand",
    "ServiceCommand",
    "StartCommand",
    "StatusCommand",
    "TempCommand",
    "TopCommand",
    "UpgradeBotCommand",
    "WolCommand",
    "ALL_COMMAND_CLASSES",
]
