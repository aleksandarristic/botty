from botty.config import BottyConfig

from .media import AdguardStatusCommand, EmbyStatusCommand
from .network import NetworkTestsCommand
from .status import StartCommand, StatusCommand

config = BottyConfig.from_env()

start_command = StartCommand(config)
status_command = StatusCommand(config)
emby_status_command = EmbyStatusCommand(config)
adguard_status_command = AdguardStatusCommand(config)
network_tests_command = NetworkTestsCommand(config)

ALL_COMMANDS = [
    start_command,
    status_command,
    emby_status_command,
    adguard_status_command,
    network_tests_command,
]

__all__ = [
    "StartCommand",
    "StatusCommand",
    "EmbyStatusCommand",
    "AdguardStatusCommand",
    "NetworkTestsCommand",
    "start_command",
    "status_command",
    "emby_status_command",
    "adguard_status_command",
    "network_tests_command",
    "config",
    "ALL_COMMANDS",
]
