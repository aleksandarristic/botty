# Botty - A Python Telegram Bot for Home Server Monitoring

This project contains the source code for "botty", a Python-based Telegram bot designed to monitor a home server. The bot is built using the `python-telegram-bot` library for handling Telegram API interactions and `httpx` for making asynchronous HTTP requests to a local dashboard application.

The bot's functionality is centered around a series of slash commands that can be issued from a Telegram chat. For security, the bot is configured to only respond to a single, authorized user ID.

## Easy Installation (Recommended)

An interactive script is provided to handle the installation and setup of the bot as a systemd service.

### Remote Installation (via `curl`)

You can install the bot using a single command. The script will guide you through the process, asking for an installation directory and your credentials.

```bash
curl -sSL https://raw.githubusercontent.com/aleksandarristic/botty/main/install.sh | bash
```

> **Security Warning:** Piping a script from the internet directly into `bash` is convenient but can be dangerous. We recommend you inspect the script's contents by visiting the URL in your browser before running it.

### Local Installation (from clone)

If you have already cloned the repository, you can run the installer directly. It will automatically detect the local repository, pull the latest changes, and use the current directory for the installation.

```bash
cd botty
./install.sh
```

### What the Script Does

The `install.sh` script is context-aware:

*   **Remote Installation (via `curl`):**
    *   Asks for an installation directory.
    *   **Clones the repository** into that directory.
*   **Local Installation (from clone):**
    *   Automatically uses the current directory.
    *   **Performs a `git pull`** to ensure the code is up-to-date.

In both cases, it then proceeds to:
- Check for dependencies (`git`, `python3`, `pip`).
- Ask for your Telegram credentials.
- Set up a Python virtual environment and install the package.
- Create, enable, and start a `systemd` service to run the bot in the background.

## Developer Setup

If you want to run the bot manually or contribute to development, follow these steps.

### 1. Clone the Repository
```bash
git clone https://github.com/aleksandarristic/botty.git
cd botty
```

### 2. Set up the Environment
Create a Python virtual environment and install the project in editable mode. This will also install all dependencies, including development tools like `pytest`.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Configure the Bot
Create a `.env` file in the root of the project by copying the example file:
```bash
cp .env.example .env
```
Now, edit the `.env` file and add your credentials:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from BotFather.
- `AUTHORIZED_USER_ID`: Your Telegram user ID.
- `GOHOME_API_URL`: (Optional) The URL for your dashboard's status API.

### 4. Running the Bot Manually
After activating the virtual environment (`source .venv/bin/activate`), you can run the bot using the entry point created during installation:
```bash
botty
```

### 5. Running Tests
To run the test suite, use `pytest`:
```bash
pytest
```

### Development Conventions
The project uses a modular structure for commands, making it easy to extend.
- **`src/botty/main.py`**: The main application entry point.
- **`src/botty/cmd/`**: The command module.
  - **`handlers.py`**: Contains the implementation for each command handler.
  - **`__init__.py`**: Acts as a central command registry.
- To add a new command, add your handler to `handlers.py` and register it in `__init__.py`.