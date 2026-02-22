# Botty - A Python Telegram Bot for Home Server Monitoring

Botty is a Python-based Telegram bot that keeps an eye on a personal server by wrapping shell checks and external dashboards in secure bot commands. It runs on `python-telegram-bot`, pulls metrics via `httpx`, and sanitizes every response with custom MarkdownV2 helpers before replying.

## Installation

### Automated service deployment

The `install.sh` script builds a virtual environment, installs the package, and wires up a `systemd` service.

```bash
curl -sSL https://raw.githubusercontent.com/aleksandarristic/botty/main/install.sh | bash
```

Recommended update workflow:

1. Run `git pull` in your normal-user source repo (for example under your home directory).
2. Run `./install.sh --install-dir=/opt/botty --service-user=botty` from that source repo.

During install, the script syncs source files into `<install_dir>` (it does not run `git pull` in `<install_dir>`). Behind the scenes it:

1. Prompts for or sources `TELEGRAM_BOT_TOKEN` and one or more comma-separated `AUTHORIZED_USER_ID`s.
2. Prompts for optional service-specific values (`GOHOME_API_URL`, `EMBY_DATA_PATH`, `MEDIA_PATH`) when not already set.
3. Lists enabled systemd services and prompts for `BOTTY_SERVICE_ALLOWLIST` (services Botty may manage).
4. Creates/uses a dedicated service account (default: `botty`).
5. Creates `<install_dir>/.venv`, installs `botty` in editable mode, and writes a `botty.env` file.
6. Registers `/etc/systemd/system/botty.service` with the selected service user, reloads the daemon, enables, and restarts the service.
7. Generates a scoped sudoers policy in `/etc/sudoers.d/botty` based on the selected service allow-list.
8. Validates runtime execute permissions for the service user and refuses install if the target mount is `noexec`.

Additional flags:

- `--update`: accepted for backward compatibility; prints a note to run `git pull` in source repo first.
- `--reinstall`: re-prompts for every secret and path, overwriting `botty.env`.
- `--uninstall`: stops/disables the service and removes the unit file (leaving the install directory intact).
- `--service-user=<name>`: optional override for the service account (default `botty`).
- `--install-dir=<path>`: optional install target override (for example `--install-dir=/opt/botty`), even when running installer from a local clone.
- `--python-bin=<path>`: optional explicit Python interpreter for venv creation (example: `--python-bin=/usr/bin/python3`).

When syncing from a local source repo to a separate install directory, the installer updates ownership/permissions in the install directory for the selected service user so systemd can run it.
Installer must be run as a normal user (not root); it requests `sudo` internally for privileged steps.

### Manual development setup

For contributors or local experimentation:

```bash
git clone https://github.com/aleksandarristic/botty.git
cd botty
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Copy the configuration template and fill in your secrets:

```bash
cp .env.example .env
# EDIT: set TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID, etc.
```

Run the bot locally with `botty`.

## Configuration

- `TELEGRAM_BOT_TOKEN`: token from BotFather.
- `AUTHORIZED_USER_ID`: comma-separated list of Telegram IDs who may use the commands.
- `AUTHORIZED_CHAT_ID`: optional comma-separated list of non-private chat IDs (groups/supergroups/channels) where commands are allowed. Private chats only require an authorized user ID.
- `ENABLED_COMMANDS`: optional comma-separated list of command names to enable (e.g., `status,network_tests`). If omitted, all commands are enabled. `/start` is always enabled.
- `GOHOME_API_URL`: endpoint for network results (default `http://localhost:8080/status`).
- `EMBY_DATA_PATH` / `MEDIA_PATH`: paths used for drive checks; defaults `/mnt/embydata` and `/mnt/media`.
- `TELEGRAM_POLL_TIMEOUT_SECONDS`: Telegram long-poll timeout in seconds (default `300`; increase to reduce poll-frequency log noise).
- `TOTP_SECRET`: base32 TOTP secret used to confirm sensitive commands.
- `TOTP_WINDOW_STEPS`: allowed TOTP clock drift in 30-second steps (default `1`).
- `BOTTY_SERVICE_ALLOWLIST`: comma-separated service names allowed for `/service` and `/logs` (enforced in-app and in sudo policy), for example `botty,nginx`.
- `BOTTY_SUDO_PASSWORD`: optional sudo password used for privileged commands when command handlers enable `sudo=True`.

Service installations store these values in `botty.env`, whereas `.env` is used during manual runs. Keep `botty.env` private and out of version control.

### TOTP Setup

1. Generate a Base32 secret:
   ```bash
   python3 - <<'PY'
   import secrets, base64
   print(base64.b32encode(secrets.token_bytes(20)).decode().rstrip("="))
   PY
   ```
2. Set `TOTP_SECRET` (and optionally `TOTP_WINDOW_STEPS`) in `botty.env` or `.env`.
3. Add the same secret to your authenticator app (6 digits, 30s period, SHA1).
4. Restart bot service/process.

## Existing Commands

All commands are registered dynamically via the `command_registry` in `src/botty/cmd/__init__.py`, with handler auto-discovery from `src/botty/cmd/handlers/*`. Authorization is enforced in the `Command` base class for every command, including `/start`. Unauthorized requests are silently ignored.

### System & Control
- `/start`: List the available commands.
- `/status`: Reports uptime, memory, and disk usage.
- `/service <name> <action> <totp>`: Manage system services (`start`, `stop`, `restart`, `status`). Requires `sudo` + TOTP. Service must be in `BOTTY_SERVICE_ALLOWLIST`.
- `/reboot confirm <totp>`: Reboots the server. Requires `sudo` + TOTP.

### Monitoring
- `/top`: Returns the top 5 CPU-consuming processes.
- `/temp`: Reports system temperatures (via `sensors` or `/sys/class/thermal`).
- `/logs <service> <totp>`: Returns the last 20 lines of `journalctl -u <service>`. Requires `sudo` + TOTP. Service must be in `BOTTY_SERVICE_ALLOWLIST`.

### Docker
- `/docker_status [compose_dir]`: Reports Docker daemon info and optionally `docker compose ps`.
- `/docker_list`: Lists all containers and their status.
- `/docker_restart <container> <totp>`: Restarts a specific container (TOTP required).

### Network
- `/network_tests`: Queries the GoHome API for speedtest and device metrics.
- `/ping <host> <totp>`: Performs a simple ping check (TOTP required).
- `/wol <mac> <totp>`: Sends a Wake-on-LAN magic packet (TOTP required).

### Maintenance
- `/check_updates <totp>`: Checks for upgradable packages (via `apt`, TOTP required).
- `/upgrade_bot confirm <totp>`: Pulls latest code from git and restarts the bot service (TOTP required).

Detailed per-command behavior, arguments, output format, and operational notes are documented in `COMMANDS.md`.

Every textual reply is sanitized with `escape_markdown` / `escape_markdown_code` helpers in `src/botty/utils.py` to stay compatible with Telegram MarkdownV2.

## Permissions & Sudo

Several commands require `sudo` privileges. Command handlers opt in with `sudo=True` (default is `False` in the base `Command` class). When enabled, command execution uses `sudo` automatically:

- If `BOTTY_SUDO_PASSWORD` is set, commands run via `sudo -S` and the password is passed through stdin.
- If `BOTTY_SUDO_PASSWORD` is not set, commands run via `sudo -n` (non-interactive), which requires passwordless sudo.

For production, configure narrowly scoped passwordless sudo for the bot service user. `install.sh` now generates `/etc/sudoers.d/botty` automatically from `BOTTY_SERVICE_ALLOWLIST`.

### Privilege Matrix

| Command | Underlying OS command(s) | Needs sudo |
| --- | --- | --- |
| `/service <name> <action> <totp>` | `systemctl start/stop/restart/status <name>` | Yes |
| `/logs <service> <totp>` | `journalctl -u <service> -n 20 --no-pager` | Yes |
| `/reboot confirm` | `reboot` | Yes |
| `/upgrade_bot confirm` | `git pull` then `systemctl restart botty` | Only `systemctl` step |
| `/check_updates <totp>` | `apt list --upgradable` | No |
| `/status`, `/top`, `/temp`, `/docker_*`, `/network_*` | read-only process/network/docker commands | No (unless your host requires it for docker) |

### Recommended sudoers (service allow-list)

Create `/etc/sudoers.d/botty` with `visudo`:

```bash
sudo visudo -f /etc/sudoers.d/botty
```

Example policy for service user `botty`:

```sudoers
Cmnd_Alias BOTTY_SYSTEMCTL = /usr/bin/systemctl start botty, /usr/bin/systemctl stop botty, /usr/bin/systemctl restart botty, /usr/bin/systemctl status botty, /usr/bin/systemctl start nginx, /usr/bin/systemctl stop nginx, /usr/bin/systemctl restart nginx, /usr/bin/systemctl status nginx
Cmnd_Alias BOTTY_LOGS = /usr/bin/journalctl -u botty -n 20 --no-pager, /usr/bin/journalctl -u nginx -n 20 --no-pager
Cmnd_Alias BOTTY_REBOOT = /usr/sbin/reboot, /usr/bin/reboot

botty ALL=(root) NOPASSWD: BOTTY_SYSTEMCTL, BOTTY_LOGS, BOTTY_REBOOT
```

Then:

```bash
sudo chown root:root /etc/sudoers.d/botty
sudo chmod 440 /etc/sudoers.d/botty
sudo -l -U botty
```

If your managed services run under different Linux users, this is still fine: `systemctl`/`journalctl` are system-level controls. What matters is which unit names you allow in sudoers, not the runtime user of those units.

### Dedicated Service User Guide

Yes, `install.sh` can create the service user automatically.

Default behavior:
- service user is `botty`
- installer creates `botty` if missing
- systemd unit runs with `User=botty`

Manual setup (if you want to pre-create it yourself):

```bash
sudo groupadd --system botty
sudo useradd --system --gid botty --create-home --home-dir /home/botty --shell /usr/sbin/nologin botty
```

Then run installer:

```bash
./install.sh
# or choose another account explicitly:
./install.sh --service-user=mybot
```

## Customization: Adding New Commands

Botty uses a package-per-command style under `src/botty/cmd/handlers/`. Follow this workflow:

1. Scaffold a new command package (recommended).
   Example for a command named `hello`:
   ```bash
   botty-create-command hello --description "Example custom command"
   ```
   Interactive mode (prompts for behavior, auth, sudo/TOTP, optional shell command + cwd):
   ```bash
   botty-create-command --interactive
   ```
   Preview only (no file writes):
   ```bash
   botty-create-command hello --description "Example custom command" --dry-run
   ```
   Non-interactive shell template with explicit working directory:
   ```bash
   botty-create-command update_bridge \
     --description "Run pycodebridge update script" \
     --shell-command "./update.sh" \
     --cwd "/home/leka/Code/pycodebridge"
   ```
   This creates:
   - `src/botty/cmd/handlers/hello/command.py`
   - `src/botty/cmd/handlers/hello/__init__.py`

2. Edit `command.py` with your command logic.
   ```python
   # src/botty/cmd/handlers/hello/command.py
   from telegram import Update
   from telegram.ext import ContextTypes

   from botty.cmd.handlers.base import Command
   from botty.utils import escape_markdown_code, run_command


   class HelloCommand(Command):
       name = "hello"
       description = "Example custom command"

       async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
           message = self._require_message(update)
           args = " ".join(context.args).strip() if context.args else "(no args)"
           uptime = await run_command(["uptime", "-p"])

           reply = (
               "*Hello Command*\n\n"
               f"*Args:* `{escape_markdown_code(args)}`\n"
               f"*Uptime:* `{escape_markdown_code(uptime.strip())}`"
           )
           await message.reply_text(reply, parse_mode="MarkdownV2")
   ```

3. Command discovery and registration are automatic.
   - Any package under `src/botty/cmd/handlers/<name>/` with an exported `*Command` class in `__all__` is discovered at startup.
   - No edits to central registry files are required.

4. Optional: add handler-local support modules.
   If logic is command-specific (formatters, HTTP clients, checks, caching), keep it in the same package:
   - `src/botty/cmd/handlers/hello/checks.py`
   - `src/botty/cmd/handlers/hello/formatter.py`
   Shared utilities stay in `src/botty/utils.py` (for example markdown escaping and shell execution helpers).

5. Configure command visibility.
   - If `ENABLED_COMMANDS` is unset: all discovered commands are enabled.
   - If set: only listed command names are enabled.
   - `/start` is always enabled and auto-builds its menu from currently enabled commands.

6. Add tests.
   - Add/extend tests in `tests/test_handlers.py`.
   - Patch the correct module path for your handler package (for example `botty.cmd.handlers.hello.command.run_command`).
   - If the command has parser/formatter helpers, add focused unit tests in a dedicated test file.

7. Validate locally.
   ```bash
   .venv/bin/python -m pytest -q
   .venv/bin/python -m ruff check .
   ```

For a real reference implementation, see:
- `src/botty/cmd/handlers/example/command.py`
- `src/botty/cmd/handlers/network/`
- `src/botty/cmd/handlers/docker/command.py`

## Testing

The `tests/` directory covers command handlers and utilities via `pytest` and `pytest-asyncio`. Mocking (`unittest.mock`) isolates shell commands and HTTP calls. Run the suite with:

```bash
pytest
```

## Structure

- `src/botty/main.py`: entry point invoked by the `botty` console script defined in `pyproject.toml`.
- `src/botty/utils.py`: command helpers (shell execution + Markdown escaping).
- `src/botty/cmd/__init__.py`: command registry assembly and `ENABLED_COMMANDS` filtering.
- `src/botty/cmd/handlers/`: command packages (`<command>/command.py`, optional local helper modules, package exports).
- `tests/`: handler and utility tests.
- `install.sh`: produces the `.venv` installation, configuration file, and systemd unit.
- `.env.example`: template for local development secrets.
- `COMMANDS.md`: detailed command reference and operational behavior.
