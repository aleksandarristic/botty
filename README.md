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
- `GOHOME_API_URL`: endpoint for network results (default `http://localhost:8080/status`).
- `EMBY_DATA_PATH` / `MEDIA_PATH`: paths used for drive checks; defaults `/mnt/embydata` and `/mnt/media`.

Service installations store these values in `botty.env`, whereas `.env` is used during manual runs.

## Commands

All commands are registered dynamically via the `command_registry` in `src/botty/cmd/__init__.py`. Authorization is enforced in the `Command` base class; most commands require authorization, while `/start` is public.

- `/start`: list the available commands and remind the user of the current UI.
- `/status`: reports uptime, memory, and disk usage gathered from `uptime`, `free`, and `df`.
- `/emby_status`: fetches `systemctl status emby-server`, plus drive usage for `EMBY_DATA_PATH` and `MEDIA_PATH`.
- `/adguard_status`: fetches `systemctl status AdGuardHome`.
- `/network_tests`: queries the GoHome API and formats speedtest stats, ping targets, and device metrics (temperature, memory, load averages, uptime) inside fenced MarkdownV2 code blocks.

Every textual reply is sanitized with `escape_markdown` / `escape_markdown_code` helpers in `src/botty/utils.py` to stay compatible with Telegram MarkdownV2.

## Testing

The `tests/` directory covers command handlers and utilities via `pytest` and `pytest-asyncio`. Mocking (`unittest.mock`) isolates shell commands and HTTP calls. Run the suite with:

```bash
pytest
```

## Structure

- `src/botty/main.py`: entry point invoked by the `botty` console script defined in `pyproject.toml`.
- `src/botty/utils.py`: command helpers (shell execution + Markdown escaping).
- `src/botty/services/`: GoHome formatting, HTTP client setup, and system check adapters.
- `src/botty/cmd/handlers/`: command implementations and the `command_registry` in `src/botty/cmd/__init__.py`.
- `tests/`: handler and utility tests.
- `install.sh`: produces the `.venv` installation, configuration file, and systemd unit.
- `.env.example`: template for local development secrets.
