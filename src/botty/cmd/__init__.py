from .handlers import (
    start,
    help_command,
    status_command,
    emby_status_command,
    adguard_status_command,
    network_tests_command,
)

command_registry = [
    ("start", start),
    ("help", help_command),
    ("status", status_command),
    ("emby_status", emby_status_command),
    ("adguard_status", adguard_status_command),
    ("network_tests", network_tests_command),
]
