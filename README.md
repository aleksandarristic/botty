# Botty - A Python Telegram Bot for Home Server Monitoring

Botty is a Python-based Telegram bot that keeps an eye on a personal server by wrapping shell checks and external dashboards in secure bot commands. It runs on `python-telegram-bot`, pulls metrics via `httpx`, and sanitizes every response with custom MarkdownV2 helpers before replying.

## Installation

### Automated service deployment

The `install.sh` script builds a virtual environment, installs the package, and wires up a `systemd` service. It can run either from a local clone or fetched directly over `curl`:

```bash
curl -sSL https://raw.githubusercontent.com/aleksandarristic/botty/main/install.sh | bash
```

When run from within the repository, `./install.sh` detects the local tree, prompts for any missing credentials or paths, and (when `--update` is passed) pulls the latest commits before reinstalling dependencies. Behind the scenes it:

1. Prompts for or sources `TELEGRAM_BOT_TOKEN` and one or more comma-separated `AUTHORIZED_USER_ID`s.
2. Prompts for optional service-specific values (`GOHOME_API_URL`, `EMBY_DATA_PATH`, `MEDIA_PATH`) when not already set.
3. Creates/uses a dedicated service account (default: `botty`).
4. Creates `<install_dir>/.venv`, installs `botty` in editable mode, and writes a `botty.env` file.
5. Registers `/etc/systemd/system/botty.service` with `User=botty`, reloads the daemon, enables, and restarts the service.

Additional flags:

- `--update`: reruns `git pull` prior to reinstalling (skipped by default in local mode).
- `--reinstall`: re-prompts for every secret and path, overwriting `botty.env`.
- `--uninstall`: stops/disables the service and removes the unit file (leaving the install directory intact).
- `--service-user=<name>`: optional override for the service account (default `botty`).

When installing from an existing local clone, the installer updates ownership of the install directory to the selected service user so systemd can run it.

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
- `ENABLED_COMMANDS`: optional comma-separated list of command names to enable (e.g., `status,network_tests`). If omitted, all commands are enabled. `/start` is always enabled.
- `GOHOME_API_URL`: endpoint for network results (default `http://localhost:8080/status`).
- `EMBY_DATA_PATH` / `MEDIA_PATH`: paths used for drive checks; defaults `/mnt/embydata` and `/mnt/media`.
- `BOTTY_SUDO_PASSWORD`: optional sudo password used for privileged commands when command handlers enable `sudo=True`.

Service installations store these values in `botty.env`, whereas `.env` is used during manual runs. Keep `botty.env` private and out of version control.

## Existing Commands

All commands are registered dynamically via the `command_registry` in `src/botty/cmd/__init__.py`. Authorization is enforced in the `Command` base class; most commands require authorization, while `/start` is public.

### System & Control
- `/start`: List the available commands.
- `/status`: Reports uptime, memory, and disk usage.
- `/service <name> <action>`: Manage system services (`start`, `stop`, `restart`, `status`). Requires `sudo`.
- `/reboot confirm`: Reboots the server. Requires `sudo`.

### Monitoring
- `/top`: Returns the top 5 CPU-consuming processes.
- `/temp`: Reports system temperatures (via `sensors` or `/sys/class/thermal`).
- `/logs <service>`: Returns the last 20 lines of `journalctl -u <service>`. Requires `sudo`.

### Docker
- `/docker_status [compose_dir]`: Reports Docker daemon info and optionally `docker compose ps`.
- `/docker_list`: Lists all containers and their status.
- `/docker_restart <container>`: Restarts a specific container.

### Network
- `/network_tests`: Queries the GoHome API for speedtest and device metrics.
- `/ping <host>`: Performs a simple ping check.
- `/wol <mac>`: Sends a Wake-on-LAN magic packet.

### Maintenance
- `/check_updates`: Checks for upgradable packages (via `apt`).
- `/upgrade_bot confirm`: Pulls latest code from git and restarts the bot service.

Detailed per-command behavior, arguments, output format, and operational notes are documented in `COMMANDS.md`.

Every textual reply is sanitized with `escape_markdown` / `escape_markdown_code` helpers in `src/botty/utils.py` to stay compatible with Telegram MarkdownV2.

## Permissions & Sudo

Several commands require `sudo` privileges. Command handlers opt in with `sudo=True` (default is `False` in the base `Command` class). When enabled, command execution uses `sudo` automatically:

- If `BOTTY_SUDO_PASSWORD` is set, commands run via `sudo -S` and the password is passed through stdin.
- If `BOTTY_SUDO_PASSWORD` is not set, commands run via `sudo -n` (non-interactive), which requires passwordless sudo.

For production, configure narrowly scoped passwordless sudo for the bot service user.

### Privilege Matrix

| Command | Underlying OS command(s) | Needs sudo |
| --- | --- | --- |
| `/service <name> <action>` | `systemctl start/stop/restart/status <name>` | Yes |
| `/logs <service>` | `journalctl -u <service> -n 20 --no-pager` | Yes |
| `/reboot confirm` | `reboot` | Yes |
| `/upgrade_bot confirm` | `git pull` then `systemctl restart botty` | Only `systemctl` step |
| `/check_updates` | `apt list --upgradable` | No |
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

1. Create a handler package.
   Example for a command named `hello`:
   ```bash
   mkdir -p src/botty/cmd/handlers/hello
   ```

2. Add `command.py` with a command class.
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

3. Add package exports.
   ```python
   # src/botty/cmd/handlers/hello/__init__.py
   from .command import HelloCommand as HelloCommand

   __all__ = ["HelloCommand"]
   ```

4. Register the command class.
   Edit `src/botty/cmd/handlers/__init__.py`:
   - import it (`from .hello import HelloCommand`)
   - add it to `ALL_COMMAND_CLASSES`
   - add it to `__all__`

5. Optional: add handler-local support modules.
   If logic is command-specific (formatters, HTTP clients, checks, caching), keep it in the same package:
   - `src/botty/cmd/handlers/hello/checks.py`
   - `src/botty/cmd/handlers/hello/formatter.py`
   Shared utilities stay in `src/botty/utils.py` (for example markdown escaping and shell execution helpers).

6. Configure command visibility.
   - If `ENABLED_COMMANDS` is unset: all commands in `ALL_COMMAND_CLASSES` are enabled.
   - If set: only listed command names are enabled.
   - `/start` is always enabled and auto-builds its menu from currently enabled commands.

7. Add tests.
   - Add/extend tests in `tests/test_handlers.py`.
   - Patch the correct module path for your handler package (for example `botty.cmd.handlers.hello.command.run_command`).
   - If the command has parser/formatter helpers, add focused unit tests in a dedicated test file.

8. Validate locally.
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
