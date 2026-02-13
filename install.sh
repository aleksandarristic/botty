#!/bin/bash

# ==============================================================================
# Botty Semi-Interactive Installer
#
# This script installs the Botty Telegram bot, creates a virtual environment,
# and sets it up as a systemd service.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/aleksandarristic/botty/main/install.sh | bash
# ==============================================================================

# --- Script Configuration ---
GIT_REPO_URL="https://github.com/aleksandarristic/botty"
DEFAULT_SERVICE_USER="botty"

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Helper Functions for Colors and Logging ---
setup_colors() {
  if [[ -t 2 ]] && [[ -z "${NO_COLOR-}" ]] && [[ "${TERM-}" != "dumb" ]]; then
    NOFORMAT='\033[0m' BOLD='\033[1m' FAINT='\033[2m' ITALIC='\033[3m' UNDERLINE='\033[4m'
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[0;33m' BLUE='\033[0;34m' MAGENTA='\033[0;35m' CYAN='\033[0;36m'
  else
    NOFORMAT='' BOLD='' FAINT='' ITALIC='' UNDERLINE=''
    RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN=''
  fi
}

msg() {
  echo >&2 -e "${1-}"
}

# --- Main Logic ---

ensure_service_user() {
  local user="$1"
  local group="$1"
  msg "\n${BOLD}Ensuring service user '$user' exists...${NOFORMAT}"

  if id -u "$user" >/dev/null 2>&1; then
    msg "${GREEN}✅ Service user '$user' already exists.${NOFORMAT}"
    return
  fi

  msg "Creating system user '$user' (group '$group')..."
  sudo groupadd --system "$group" 2>/dev/null || true
  sudo useradd --system --gid "$group" --create-home --home-dir "/home/$user" --shell /usr/sbin/nologin "$user"
  msg "${GREEN}✅ Created service user '$user'.${NOFORMAT}"
}

check_dependencies() {
  msg "${BOLD}Checking for required dependencies...${NOFORMAT}"
  local dependencies=("git" "python3" "pip")
  local missing=()
  for dep in "${dependencies[@]}"; do
    if ! command -v "$dep" &> /dev/null; then
      missing+=("$dep")
    fi
  done

  if [ ${#missing[@]} -ne 0 ]; then
    msg "${RED}Error: The following dependencies are missing: ${missing[*]}.${NOFORMAT}"
    msg "Please install them and run the script again."
    exit 1
  fi
  msg "${GREEN}✅ All dependencies are present.${NOFORMAT}"
}

get_user_input() {
  msg "\n${BOLD}Please provide the following information:${NOFORMAT}"

  # Get the installation directory
  read -p "Enter the full path to install Botty (e.g., /home/youruser/botty): " INSTALL_DIR
  # Use default if empty
  INSTALL_DIR=${INSTALL_DIR:-"$HOME/botty"}

  # Get secrets
  read -sp "Enter your TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
  msg "" # Newline after secret input
      read -p "Enter your AUTHORIZED_USER_ID (comma-separated for multiple): " AUTHORIZED_USER_ID
}

clone_and_install() {
  msg "\n${BOLD}Cloning repository into $INSTALL_DIR...${NOFORMAT}"
  if [ -d "$INSTALL_DIR" ]; then
    msg "${YELLOW}Warning: Directory $INSTALL_DIR already exists. Pulling latest changes.${NOFORMAT}"
    cd "$INSTALL_DIR"
    git pull
    cd - > /dev/null
  else
    git clone "$GIT_REPO_URL" "$INSTALL_DIR"
  fi

  msg "${BOLD}Creating Python virtual environment at $INSTALL_DIR/.venv...${NOFORMAT}"
  python3 -m venv "$INSTALL_DIR/.venv"

  msg "${BOLD}Installing Python packages...${NOFORMAT}"
  "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
  "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR"
  msg "${GREEN}✅ Python setup complete.${NOFORMAT}"
}

setup_systemd_service() {
  if ! command -v systemctl &> /dev/null; then
    msg "${YELLOW}Warning: systemd not found. Skipping service setup. You will need to run the bot manually.${NOFORMAT}"
    return
  fi

  msg "\n${BOLD}Setting up systemd service...${NOFORMAT}"
  msg "This step requires sudo privileges to create the service file."

  local SERVICE_FILE_PATH="/etc/systemd/system/botty.service"
  local ENV_FILE_PATH="$INSTALL_DIR/botty.env"

  ensure_service_user "$SERVICE_USER"
  SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

  # Create the environment file
  msg "Creating environment file at $ENV_FILE_PATH..."
  # Use existing GOHOME_API_URL if set (e.g. from sourcing existing env file), else default
  GOHOME_API_URL=${GOHOME_API_URL:-"http://localhost:8080/status"}
  # Set defaults for Emby paths if not already provided via env
  EMBY_DATA_PATH=${EMBY_DATA_PATH:-"/mnt/embydata"}
  MEDIA_PATH=${MEDIA_PATH:-"/mnt/media"}
  local enabled_commands_line=""
  if [[ -n "$ENABLED_COMMANDS" ]]; then
    enabled_commands_line="ENABLED_COMMANDS=$ENABLED_COMMANDS"
  fi
  
  cat << EOL | sudo tee "$ENV_FILE_PATH" > /dev/null
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
AUTHORIZED_USER_ID=$AUTHORIZED_USER_ID
${enabled_commands_line}
GOHOME_API_URL="$GOHOME_API_URL"
EMBY_DATA_PATH="$EMBY_DATA_PATH"
MEDIA_PATH="$MEDIA_PATH"
EOL
  sudo chown "$SERVICE_USER:$SERVICE_GROUP" "$ENV_FILE_PATH"
  sudo chmod 600 "$ENV_FILE_PATH"

  # Ensure service user can read and execute the installation tree.
  msg "Adjusting ownership for $INSTALL_DIR to $SERVICE_USER..."
  sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
  sudo find "$INSTALL_DIR" -type d -exec chmod 750 {} \;

  # Create the service file content
  local service_content
  service_content=$(cat << EOL
[Unit]
Description=Botty Telegram Bot
After=network.target

[Service]
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/botty
EnvironmentFile=$ENV_FILE_PATH
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOL
)

  # Write the service file using sudo
  msg "Creating service file at $SERVICE_FILE_PATH..."
  echo "$service_content" | sudo tee "$SERVICE_FILE_PATH" > /dev/null

  msg "Reloading systemd, enabling and starting the service..."
  sudo systemctl daemon-reload
  sudo systemctl enable botty.service
  sudo systemctl restart botty.service

  msg "${GREEN}✅ Systemd service setup complete.${NOFORMAT}"
}

uninstall_service() {
  msg "\n${BOLD}Uninstalling Botty service...${NOFORMAT}"

  if ! command -v systemctl &> /dev/null; then
    msg "${YELLOW}Warning: systemd not found. Nothing to uninstall via systemd.${NOFORMAT}"
    return
  fi

  local SERVICE_NAME="botty.service"
  local SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

  if [ -f "$SERVICE_FILE" ]; then
    msg "Stopping and disabling $SERVICE_NAME..."
    sudo systemctl stop "$SERVICE_NAME" || true
    sudo systemctl disable "$SERVICE_NAME" || true
    
    msg "Removing service file $SERVICE_FILE..."
    sudo rm "$SERVICE_FILE"
    
    msg "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    sudo systemctl reset-failed
    
    msg "${GREEN}✅ Systemd service uninstalled successfully.${NOFORMAT}"
  else
    msg "${YELLOW}Service file $SERVICE_FILE not found. It might already be uninstalled.${NOFORMAT}"
  fi
  
  msg "\nNote: The installation directory and your .env configuration were NOT removed."
}

main() {
  setup_colors
  check_dependencies

  # Parse arguments
  local REINSTALL=false
  local UNINSTALL=false
  local UPDATE=false
  SERVICE_USER="$DEFAULT_SERVICE_USER"
  for arg in "$@"; do
    case $arg in
      --reinstall)
        REINSTALL=true
        shift
        ;;
      --uninstall)
        UNINSTALL=true
        shift
        ;;
      --update)
        UPDATE=true
        shift
        ;;
      --service-user=*)
        SERVICE_USER="${arg#*=}"
        shift
        ;;
    esac
  done

  if [ "$UNINSTALL" = true ]; then
    uninstall_service
    exit 0
  fi

  # Determine the installation directory
  if [ -d ".git" ]; then
    msg "${GREEN}Git repository detected. Installing from the current directory.${NOFORMAT}"
    INSTALL_DIR=$(pwd)
    IS_LOCAL_INSTALL=true
    msg "${YELLOW}Note: service will run as '$SERVICE_USER' and installer will chown this directory to that user.${NOFORMAT}"
  else
    msg "\n${BOLD}Please provide the following information:${NOFORMAT}"
    read -p "Enter the full path to install Botty (e.g., /opt/botty): " INSTALL_DIR
    INSTALL_DIR=${INSTALL_DIR:-"/opt/botty"}
    IS_LOCAL_INSTALL=false
  fi
  
  # Check for existing configuration
  local ENV_FILE="$INSTALL_DIR/botty.env"
  if [[ -f "$ENV_FILE" ]] && [[ "$REINSTALL" == "false" ]]; then
    msg "${GREEN}Found existing configuration at $ENV_FILE. Sourcing it.${NOFORMAT}"
    # shellcheck source=/dev/null
    source "$ENV_FILE"
  fi

  # Get missing secrets/paths from the user
  if [[ -z "$TELEGRAM_BOT_TOKEN" ]] || [[ -z "$AUTHORIZED_USER_ID" ]] || [[ "$REINSTALL" == "true" ]]; then
    msg "\n${BOLD}Please provide your bot's credentials:${NOFORMAT}"
    read -sp "Enter your TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
    msg "" # Newline after secret input
            read -p "Enter your AUTHORIZED_USER_ID (comma-separated for multiple): " AUTHORIZED_USER_ID
      fi
      
      if [[ -z "$GOHOME_API_URL" ]] || [[ "$REINSTALL" == "true" ]]; then
        read -p "Enter GoHome API URL (default: http://localhost:8080/status): " GOHOME_API_URL
        GOHOME_API_URL=${GOHOME_API_URL:-"http://localhost:8080/status"}
      fi
      
      if [[ -z "$EMBY_DATA_PATH" ]] || [[ "$REINSTALL" == "true" ]]; then
    
    read -p "Enter Emby data path (default: /mnt/embydata): " EMBY_DATA_PATH
    EMBY_DATA_PATH=${EMBY_DATA_PATH:-"/mnt/embydata"}
  fi

  if [[ -z "$MEDIA_PATH" ]] || [[ "$REINSTALL" == "true" ]]; then
    read -p "Enter media storage path (default: /mnt/media): " MEDIA_PATH
    MEDIA_PATH=${MEDIA_PATH:-"/mnt/media"}
  fi

  if [[ "$REINSTALL" == "true" ]] || [[ -z "${ENABLED_COMMANDS+x}" ]]; then
    read -p "Enter ENABLED_COMMANDS (comma-separated, optional; leave empty to enable all): " ENABLED_COMMANDS
  fi

  # Clone or pull the repository
  if [ "$IS_LOCAL_INSTALL" = true ]; then
    if [ "$UPDATE" = true ]; then
      msg "\n${BOLD}Pulling latest changes...${NOFORMAT}"
      git pull
    else
      msg "\n${BOLD}Skipping git pull (use --update to pull latest changes)...${NOFORMAT}"
    fi
  else
    msg "\n${BOLD}Cloning repository into $INSTALL_DIR...${NOFORMAT}"
    if [ -d "$INSTALL_DIR" ]; then
      if [ "$UPDATE" = true ]; then
        msg "${YELLOW}Directory $INSTALL_DIR already exists. Pulling latest changes.${NOFORMAT}"
        cd "$INSTALL_DIR"
        git pull
        cd - > /dev/null
      else
        msg "${YELLOW}Directory $INSTALL_DIR already exists. Skipping pull (use --update to force pull).${NOFORMAT}"
      fi
    else
      git clone "$GIT_REPO_URL" "$INSTALL_DIR"
    fi
  fi
  
  # Install dependencies
  msg "\n${BOLD}Creating Python virtual environment at $INSTALL_DIR/.venv...${NOFORMAT}"
  python3 -m venv "$INSTALL_DIR/.venv"

  msg "${BOLD}Installing Python packages...${NOFORMAT}"
  "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
  "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR"
  msg "${GREEN}✅ Python setup complete.${NOFORMAT}"

  # Set up the service
  setup_systemd_service

  msg "\n\n${GREEN}${BOLD}🎉 Botty installation finished successfully!${NOFORMAT}"
  msg "-----------------------------------------------------"
  msg "Service user: ${CYAN}$SERVICE_USER${NOFORMAT}"
  msg "To check the service status, run: ${CYAN}sudo systemctl status botty.service${NOFORMAT}"
  msg "To view live logs, run:       ${CYAN}sudo journalctl -u botty.service -f${NOFORMAT}"
}

# --- Run the main function ---
main "$@"
