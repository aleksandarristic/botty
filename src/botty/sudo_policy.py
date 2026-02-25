from __future__ import annotations

import os
import pwd

from botty.cmd.handlers import ALL_COMMAND_CLASSES
from botty.config import BottyConfig

_SYSTEMCTL_ACTIONS = ("start", "stop", "restart", "status")


def _detect_runtime_user() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except (KeyError, OSError):
        return os.getenv("USER", "<current-user>")


def _enabled_command_names(config: BottyConfig) -> set[str]:
    discovered = {str(cls.name) for cls in ALL_COMMAND_CLASSES}
    if config.enabled_commands is None:
        enabled = discovered
    else:
        enabled = {name for name in config.enabled_commands if name in discovered}
    enabled.add("start")
    return enabled


def _normalized_allowlist(config: BottyConfig) -> list[str]:
    services: list[str] = []
    seen: set[str] = set()
    for raw in config.service_allowlist:
        name = str(raw).strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        services.append(name)
    return services


def _normalize_service_name(service_name: str) -> str:
    candidate = service_name.strip().lower()
    if candidate.endswith(".service"):
        candidate = candidate[: -len(".service")]
    return candidate


def build_startup_sudoers_guidance(
    config: BottyConfig, runtime_user: str | None = None
) -> list[str]:
    enabled = _enabled_command_names(config)
    allowlist = _normalized_allowlist(config)
    user = runtime_user or _detect_runtime_user()

    lines = [
        f"Sudo/TOTP matrix for runtime user '{user}':",
    ]

    cmd_aliases: list[tuple[str, list[str]]] = []
    warnings: list[str] = []
    needs_systemctl_alias = False
    needs_logs_alias = False
    needs_reboot_alias = False

    if "service" in enabled:
        lines.append(
            "- /service: requires TOTP + sudo; limited to BOTTY_SERVICE_ALLOWLIST entries."
        )
        if allowlist:
            needs_systemctl_alias = True
        else:
            warnings.append(
                "service enabled but BOTTY_SERVICE_ALLOWLIST is empty; command will be blocked."
            )

    if "logs" in enabled:
        lines.append(
            "- /logs: requires TOTP + sudo; limited to BOTTY_SERVICE_ALLOWLIST entries."
        )
        if allowlist:
            needs_logs_alias = True
        else:
            warnings.append(
                "logs enabled but BOTTY_SERVICE_ALLOWLIST is empty; command will be blocked."
            )

    if "restartbot" in enabled:
        lines.append(
            "- /restartbot: requires TOTP + sudo; runs 'systemctl restart botty'."
        )
        needs_systemctl_alias = True
        if "botty" not in {_normalize_service_name(s) for s in allowlist}:
            warnings.append(
                "restartbot enabled but 'botty' is not in BOTTY_SERVICE_ALLOWLIST; command will be blocked."
            )

    if "upgrade_bot" in enabled:
        lines.append(
            "- /upgrade_bot: requires TOTP; uses sudo only for 'systemctl restart botty'."
        )
        needs_systemctl_alias = True

    if "reboot" in enabled:
        lines.append("- /reboot: requires TOTP + sudo; runs reboot.")
        needs_reboot_alias = True

    if needs_systemctl_alias:
        systemctl_entries: list[str] = []
        for service in allowlist:
            for action in _SYSTEMCTL_ACTIONS:
                systemctl_entries.append(f"/usr/bin/systemctl {action} {service}")
        if "restartbot" in enabled or "upgrade_bot" in enabled:
            botty_restart = "/usr/bin/systemctl restart botty"
            if botty_restart not in systemctl_entries:
                systemctl_entries.append(botty_restart)
        if systemctl_entries:
            cmd_aliases.append(("BOTTY_SYSTEMCTL", systemctl_entries))

    if needs_logs_alias and allowlist:
        logs_entries = [
            f"/usr/bin/journalctl -u {service} -n 20 --no-pager" for service in allowlist
        ]
        cmd_aliases.append(("BOTTY_LOGS", logs_entries))

    if needs_reboot_alias:
        cmd_aliases.append(("BOTTY_REBOOT", ["/usr/sbin/reboot", "/usr/bin/reboot"]))

    if not cmd_aliases:
        lines.append("- No sudoers additions currently required by enabled commands.")
        return lines

    lines.append("Suggested sudoers additions (use visudo):")
    alias_names: list[str] = []
    for alias_name, entries in cmd_aliases:
        alias_names.append(alias_name)
        lines.append(f"Cmnd_Alias {alias_name} = {', '.join(entries)}")
    lines.append(f"{user} ALL=(root) NOPASSWD: {', '.join(alias_names)}")
    lines.append(
        "Recommendation: keep BOTTY_SUDO_PASSWORD unset and rely on scoped NOPASSWD sudoers + TOTP."
    )
    for warning in warnings:
        lines.append(f"Warning: {warning}")
    return lines


__all__ = ["build_startup_sudoers_guidance"]
