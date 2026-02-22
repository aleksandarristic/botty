from __future__ import annotations

import importlib
import inspect
import pkgutil

from .base import Command
from .status import StartCommand

_SKIP_MODULES = {"base"}


def _iter_handler_modules():
    for module_info in pkgutil.iter_modules(__path__):
        module_name = module_info.name
        if module_name in _SKIP_MODULES:
            continue
        yield importlib.import_module(f"{__name__}.{module_name}")


def _iter_command_classes(module):
    exported_names = getattr(module, "__all__", [])
    if not isinstance(exported_names, list):
        exported_names = []

    for name in exported_names:
        candidate = getattr(module, name, None)
        if not inspect.isclass(candidate):
            continue
        if not issubclass(candidate, Command) or candidate is Command:
            continue
        yield candidate


def _discover_exported_commands() -> dict[str, type[Command]]:
    discovered: dict[str, type[Command]] = {}
    for module in _iter_handler_modules():
        for command_class in _iter_command_classes(module):
            existing = discovered.get(command_class.__name__)
            if existing is not None and existing is not command_class:
                raise ValueError(
                    f"duplicate command class export detected: {command_class.__name__}"
                )
            discovered[command_class.__name__] = command_class
    return discovered


_EXPORTED_COMMANDS = _discover_exported_commands()
globals().update(_EXPORTED_COMMANDS)


def discover_command_classes() -> list[type[Command]]:
    commands = []
    for command_class in _EXPORTED_COMMANDS.values():
        if command_class is StartCommand:
            continue
        if getattr(command_class, "name", None) == "start":
            continue
        commands.append(command_class)
    commands.sort(key=lambda cls: str(getattr(cls, "name", cls.__name__)))
    return commands


ALL_COMMAND_CLASSES = discover_command_classes()

__all__ = sorted(_EXPORTED_COMMANDS) + [
    "ALL_COMMAND_CLASSES",
    "StartCommand",
    "discover_command_classes",
]
