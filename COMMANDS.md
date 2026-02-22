# Botty Command Reference

This document describes the current command behavior implemented under `src/botty/cmd/handlers/`.

## Global Behavior

- Authorization: all commands require an authorized user.
- Chat scope: group/supergroup/channel chats are allowed only when their chat ID is in `AUTHORIZED_CHAT_ID`; unauthorized requests are ignored without a response.
- Parse mode: responses are sent with Telegram MarkdownV2 and escaped for safety.
- Command execution timeout: shell commands default to 10 seconds.
- TOTP confirmation: selected sensitive commands require a 6-digit TOTP code as the final argument.
- Privileged execution: commands marked `sudo=True` run through the base command sudo path.
  - With `BOTTY_SUDO_PASSWORD` set: `sudo -S` with password from env.
  - Without it: `sudo -n` (requires `NOPASSWD` sudoers).

## Command Matrix

| Command | Handler | Auth | Sudo | Purpose |
| --- | --- | --- | --- | --- |
| `/start` | `StartCommand` | Yes | No | Show currently enabled commands |
| `/status` | `StatusCommand` | Yes | No | Uptime, memory, and root disk |
| `/emby_status` | `EmbyStatusCommand` | Yes | No | Emby service + storage checks |
| `/adguard_status` | `AdguardStatusCommand` | Yes | No | AdGuard service status |
| `/network_tests` | `NetworkTestsCommand` | Yes | No | GoHome API summary |
| `/example` | `ExampleCommand` | Yes | No | Developer example command |
| `/docker_status [target]` | `DockerStatusCommand` | Yes | No | Docker daemon + optional compose status |
| `/docker_list` | `DockerListCommand` | Yes | No | List containers and statuses |
| `/docker_restart <container> <totp>` | `DockerRestartCommand` | Yes | No | Restart one container |
| `/service <name> <action> <totp>` | `ServiceCommand` | Yes | Yes | `systemctl` service control (allowlist enforced) |
| `/restartbot <totp>` | `RestartBotCommand` | Yes | Yes | Restart `botty` service (allowlist enforced) |
| `/reboot confirm <totp>` | `RebootCommand` | Yes | Yes | Reboot host |
| `/logs <service> <totp>` | `LogsCommand` | Yes | Yes | Last 20 journal lines for an allowlisted unit |
| `/temp` | `TempCommand` | Yes | No | CPU/system temperatures |
| `/top` | `TopCommand` | Yes | No | Top CPU processes |
| `/ping <host> <totp>` | `PingCommand` | Yes | No | Ping target host |
| `/wol <mac> <totp>` | `WolCommand` | Yes | No | Send Wake-on-LAN packet |
| `/check_updates <totp>` | `CheckUpdatesCommand` | Yes | No | `apt list --upgradable` |
| `/upgrade_bot confirm <totp>` | `UpgradeBotCommand` | Yes | Partial | `git pull` and restart bot service |

## Detailed Command Notes

### `/start`
- Shows only enabled commands (`ENABLED_COMMANDS` filter applies).

### `/status`
- Collects:
  - `uptime -p`
  - `df -h /`
  - `free -h`
- Returns a 3-block status summary.

### `/emby_status`
- Reports:
  - Emby service status
  - Disk usage for `EMBY_DATA_PATH`
  - Disk usage for `MEDIA_PATH`

### `/adguard_status`
- Reports AdGuard service status from handler-local checks.

### `/network_tests`
- Calls `GOHOME_API_URL` via `httpx`.
- Formats speedtest/ping/device sections.
- Caches rendered output for 30 seconds.

### `/example`
- Developer-facing example command.
- Demonstrates `context.args`, config usage, and shell command output formatting.

### `/docker_status [compose_dir_or_file]`
- Always runs `docker info`.
- Optional argument behavior:
  - If directory: auto-detects `compose.yaml`, `compose.yml`, `docker-compose.yaml`, or `docker-compose.yml`.
  - If file path ending in `.yml/.yaml`: uses it directly.
- Runs `docker compose -f <file> ps` when compose target is provided.

### `/docker_list`
- Runs `docker ps -a --format "table {{.Names}}\t{{.Status}}"`.

### `/docker_restart <container> <totp>`
- Validates container name with a conservative allow-list (`[A-Za-z0-9._-]`).
- Runs `docker restart <container>`.

### `/service <name> <action> <totp>`
- Allowed actions: `start`, `stop`, `restart`, `status`.
- Requires trailing TOTP code for all actions.
- Service must be in `BOTTY_SERVICE_ALLOWLIST`.
- Service name is sanitized before execution.
- Runs `systemctl <action> <service>` through sudo-enabled base execution.

### `/reboot confirm <totp>`
- Requires explicit `confirm` argument.
- Runs `reboot` through sudo-enabled base execution.

### `/restartbot <totp>`
- Restarts the `botty` service to load new command handlers.
- Requires trailing TOTP code.
- Requires `botty` in `BOTTY_SERVICE_ALLOWLIST`.
- Runs `systemctl restart botty` through sudo-enabled base execution.

### `/logs <service> <totp>`
- Service must be in `BOTTY_SERVICE_ALLOWLIST`.
- Service name is sanitized.
- Runs `journalctl -u <service> -n 20 --no-pager` through sudo-enabled base execution.
- Truncates long output to last 3000 chars.

### `/temp`
- First tries `sensors`.
- Falls back to `/sys/class/thermal/thermal_zone*`.

### `/top`
- Linux-first process listing:
  - `ps -eo pid,cmd,%cpu,%mem --sort=-%cpu`
- macOS fallback:
  - `ps -eo pid,command,pcpu,pmem -r`
- Returns header + top 5 processes.

### `/ping <host> <totp>`
- Validates host against `^[a-zA-Z0-9.-]+$`.
- Runs `ping -c 3 <host>`.

### `/wol <mac> <totp>`
- Accepts `:` or `-` separated MAC addresses.
- Sends UDP broadcast magic packet to `255.255.255.255:9`.

### `/check_updates <totp>`
- Runs `apt list --upgradable`.
- Removes `Listing...` line from output.

### `/upgrade_bot confirm <totp>`
- Requires explicit `confirm`.
- Steps:
  - `git pull`
  - if updated: `systemctl restart botty` with sudo
- Note: service restart currently targets `botty` unit name.

## Operational Notes

- If you run Docker commands without root and your host denies access, add the service user to the `docker` group.
- For mixed target service users (`nginx`, `postgres`, etc.), sudoers should allow the unit names you intend to manage; runtime user of those units does not need to match the bot user.
