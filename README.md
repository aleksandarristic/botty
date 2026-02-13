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
3. Creates `./.venv`, installs `botty` in editable mode, and writes a `botty.env` file.
4. Registers `/etc/systemd/system/botty.service`, reloads the daemon, enables, and restarts the service.

Additional flags:

- `--update`: reruns `git pull` prior to reinstalling (skipped by default in local mode).
- `--reinstall`: re-prompts for every secret and path, overwriting `botty.env`.
- `--uninstall`: stops/disables the service and removes the unit file (leaving the install directory intact).

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

Service installations store these values in `botty.env`, whereas `.env` is used during manual runs.

## Existing Commands

All commands are registered dynamically via the `command_registry` in `src/botty/cmd/__init__.py`. Authorization is enforced in the `Command` base class; most commands require authorization, while `/start` is public.

- `/start`: list the available commands and remind the user of the current UI.
- `/status`: reports uptime, memory, and disk usage gathered from `uptime`, `free`, and `df`.
- `/emby_status`: fetches `systemctl status emby-server`, plus drive usage for `EMBY_DATA_PATH` and `MEDIA_PATH`.
- `/adguard_status`: fetches `systemctl status AdGuardHome`.
- `/network_tests`: queries the GoHome API and formats speedtest stats, ping targets, and device metrics (temperature, memory, load averages, uptime) inside fenced MarkdownV2 code blocks.
- `/example [args...]`: demo command that shows command execution, config usage, and argument handling via `context.args`.
- `/docker_status [compose_dir_or_file]`: reports Docker daemon info and optionally runs `docker compose ps` for a provided compose directory/file.

Every textual reply is sanitized with `escape_markdown` / `escape_markdown_code` helpers in `src/botty/utils.py` to stay compatible with Telegram MarkdownV2.

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
