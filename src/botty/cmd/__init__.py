from .handlers import ALL_COMMANDS

command_registry = [(command.name, command.handler) for command in ALL_COMMANDS]
