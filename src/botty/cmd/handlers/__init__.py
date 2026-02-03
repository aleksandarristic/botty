from .media import AdguardStatusCommand, EmbyStatusCommand
from .network import NetworkTestsCommand
from .status import StartCommand, StatusCommand

start_command = StartCommand()
status_command = StatusCommand()
emby_status_command = EmbyStatusCommand()
adguard_status_command = AdguardStatusCommand()
network_tests_command = NetworkTestsCommand()

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
    "ALL_COMMANDS",
]
