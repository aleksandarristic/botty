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

require_non_root() {
  if [[ "$EUID" -eq 0 ]]; then
    msg "${RED}Error: Do not run install.sh with sudo/root.${NOFORMAT}"
    msg "Run it as your normal user."
    msg "The script will invoke sudo only for privileged steps."
    exit 1
  fi
}

ensure_install_dir_access() {
  local install_dir="$1"
  local owner_user
  owner_user="$(id -un)"
  local owner_group
  owner_group="$(id -gn)"

  if [[ ! -e "$install_dir" ]]; then
    msg "${YELLOW}Install directory $install_dir does not exist. Creating it with sudo...${NOFORMAT}"
    sudo mkdir -p "$install_dir"
    sudo chown "$owner_user:$owner_group" "$install_dir"
    sudo chmod 755 "$install_dir"
    return
  fi

  if [[ ! -d "$install_dir" ]]; then
    msg "${RED}Error: $install_dir exists but is not a directory.${NOFORMAT}"
    exit 1
  fi

  if [[ ! -w "$install_dir" ]]; then
    msg "${YELLOW}Install directory $install_dir is not writable by $owner_user. Fixing ownership with sudo...${NOFORMAT}"
    sudo chown -R "$owner_user:$owner_group" "$install_dir"
  fi
}

ensure_sudo_access() {
  msg "\n${BOLD}Requesting sudo access for privileged install steps...${NOFORMAT}"
  sudo -v
}

check_noexec_mount() {
  local target="$1"
  if ! command -v findmnt &> /dev/null; then
    return
  fi
  local options
  options="$(findmnt -no OPTIONS "$target" 2>/dev/null || true)"
  if [[ ",$options," == *",noexec,"* ]]; then
    msg "${RED}Error: $target is on a noexec mount. Executables cannot run from here.${NOFORMAT}"
    msg "Use a different install directory (for example /opt/botty on an exec-enabled mount)."
    exit 1
  fi
}

ensure_service_runtime_access() {
  local service_user="$1"
  local service_group="$2"
  local install_dir="$3"

  # Ensure service user can traverse all parent directories.
  local current="$install_dir"
  local parents=()
  while [[ "$current" != "/" ]]; do
    current="$(dirname "$current")"
    parents=("$current" "${parents[@]}")
  done

  for parent in "${parents[@]}"; do
    if ! sudo -u "$service_user" test -x "$parent" 2>/dev/null; then
      if command -v setfacl &> /dev/null; then
        msg "${YELLOW}Granting traverse permission on $parent for $service_user via ACL...${NOFORMAT}"
        sudo setfacl -m "u:$service_user:x" "$parent" || true
      fi
    fi
  done

  # Directory + file permissions for runtime.
  sudo find "$install_dir" -type d -exec chmod 750 {} \;
  if [[ -d "$install_dir/.venv/bin" ]]; then
    sudo find "$install_dir/.venv/bin" -type f -exec chmod 750 {} \;
  fi

  # Validate executability as service user before starting systemd unit.
  if ! sudo -u "$service_user" test -x "$install_dir/.venv/bin/python"; then
    msg "${RED}Error: service user '$service_user' cannot execute $install_dir/.venv/bin/python${NOFORMAT}"
    exit 1
  fi
  if ! sudo -u "$service_user" test -x "$install_dir/.venv/bin/botty"; then
    msg "${RED}Error: service user '$service_user' cannot execute $install_dir/.venv/bin/botty${NOFORMAT}"
    exit 1
  fi
}

trim() {
  local s="$1"
  # shellcheck disable=SC2001
  s="$(echo "$s" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  echo "$s"
}

parse_csv_to_array() {
  local input="$1"
  local -n out_ref="$2"
  out_ref=()
  IFS=',' read -r -a raw_items <<< "$input"
  for item in "${raw_items[@]}"; do
    item="$(trim "$item")"
    if [[ -n "$item" ]]; then
      out_ref+=("$item")
    fi
  done
}

validate_service_name() {
  local service="$1"
  [[ "$service" =~ ^[a-zA-Z0-9_.@-]+$ ]]
}

collect_enabled_commands_interactive() {
  local commands=()
  mapfile -t commands < <("$INSTALL_DIR/.venv/bin/python" - "$INSTALL_DIR" << 'PY'
import sys
from pathlib import Path

install_dir = Path(sys.argv[1])
sys.path.insert(0, str(install_dir / "src"))

from botty.cmd.handlers import ALL_COMMAND_CLASSES  # noqa: E402

for cmd_class in ALL_COMMAND_CLASSES:
    print(cmd_class.name)
PY
  )

  if [[ ${#commands[@]} -eq 0 ]]; then
    msg "${YELLOW}Could not discover command list automatically. Keeping existing ENABLED_COMMANDS.${NOFORMAT}"
    return
  fi

  local current_display="all commands"
  if [[ -n "${ENABLED_COMMANDS+x}" ]] && [[ -n "$ENABLED_COMMANDS" ]]; then
    current_display="$ENABLED_COMMANDS"
  elif [[ -n "${ENABLED_COMMANDS+x}" ]] && [[ -z "$ENABLED_COMMANDS" ]]; then
    current_display="none (except /start)"
  fi

  msg "\n${BOLD}Interactive Bot Command Selection${NOFORMAT}"
  msg "Current selection: ${CYAN}$current_display${NOFORMAT}"
  msg "Available commands:"
  local i=1
  for cmd in "${commands[@]}"; do
    msg "  [$i] $cmd"
    ((i++))
  done
  msg "Choose by comma-separated numbers or names."
  msg "Examples: 1,3,5   OR   status,network_tests"
  msg "Special values: 'all' (enable all), 'none' (disable all except /start), Enter (keep current)"

  read -p "Enter ENABLED_COMMANDS selection: " selection_raw
  local selection
  selection="$(trim "$selection_raw")"

  if [[ -z "$selection" ]]; then
    return
  fi

  local lowered
  lowered="$(echo "$selection" | tr '[:upper:]' '[:lower:]')"
  if [[ "$lowered" == "all" ]]; then
    ENABLED_COMMANDS=""
    unset ENABLED_COMMANDS
    return
  fi
  if [[ "$lowered" == "none" ]]; then
    ENABLED_COMMANDS="__NONE__"
    return
  fi

  local selected_commands=()
  IFS=',' read -r -a selected_items <<< "$selection"
  for item in "${selected_items[@]}"; do
    item="$(trim "$item")"
    if [[ -z "$item" ]]; then
      continue
    fi

    if [[ "$item" =~ ^[0-9]+$ ]]; then
      local idx=$((item))
      if ((idx < 1 || idx > ${#commands[@]})); then
        msg "${RED}Error: invalid command index '$item'.${NOFORMAT}"
        exit 1
      fi
      selected_commands+=("${commands[$((idx-1))]}")
    else
      local found=false
      for cmd in "${commands[@]}"; do
        if [[ "$cmd" == "$item" ]]; then
          selected_commands+=("$cmd")
          found=true
          break
        fi
      done
      if [[ "$found" == "false" ]]; then
        msg "${RED}Error: unknown command '$item'.${NOFORMAT}"
        exit 1
      fi
    fi
  done

  if [[ ${#selected_commands[@]} -eq 0 ]]; then
    ENABLED_COMMANDS="__NONE__"
    return
  fi

  # De-duplicate while preserving order.
  local deduped=()
  for cmd in "${selected_commands[@]}"; do
    local seen=false
    for existing in "${deduped[@]}"; do
      if [[ "$existing" == "$cmd" ]]; then
        seen=true
        break
      fi
    done
    if [[ "$seen" == "false" ]]; then
      deduped+=("$cmd")
    fi
  done

  ENABLED_COMMANDS="$(IFS=','; echo "${deduped[*]}")"
}

collect_service_allowlist() {
  BOTTY_SERVICE_ALLOWLIST=${BOTTY_SERVICE_ALLOWLIST:-"botty"}

  if ! command -v systemctl &> /dev/null; then
    msg "${YELLOW}systemctl not found; skipping service allow-list prompt.${NOFORMAT}"
    return
  fi

  msg "\n${BOLD}Enabled systemd services detected on this host:${NOFORMAT}"
  mapfile -t enabled_services < <(systemctl list-unit-files --type=service --state=enabled --no-legend --no-pager 2>/dev/null | awk '{print $1}')
  if [[ ${#enabled_services[@]} -eq 0 ]]; then
    msg "${YELLOW}No enabled services detected (or access restricted).${NOFORMAT}"
  else
    for service in "${enabled_services[@]}"; do
      msg "  - $service"
    done
  fi

  msg "\nChoose service names that Botty may manage via /service and /logs."
  msg "Use names exactly as you will type them in Telegram (e.g., botty, nginx, ssh)."
  read -p "Enter BOTTY_SERVICE_ALLOWLIST (comma-separated, default: ${BOTTY_SERVICE_ALLOWLIST}): " user_services
  if [[ -n "$(trim "$user_services")" ]]; then
    BOTTY_SERVICE_ALLOWLIST="$user_services"
  fi

  local selected_services=()
  parse_csv_to_array "$BOTTY_SERVICE_ALLOWLIST" selected_services
  if [[ ${#selected_services[@]} -eq 0 ]]; then
    selected_services=("botty")
  fi

  local normalized=()
  for service in "${selected_services[@]}"; do
    if ! validate_service_name "$service"; then
      msg "${RED}Error: Invalid service name '$service' in BOTTY_SERVICE_ALLOWLIST.${NOFORMAT}"
      exit 1
    fi
    normalized+=("$service")
  done

  BOTTY_SERVICE_ALLOWLIST="$(IFS=','; echo "${normalized[*]}")"
}

setup_sudoers_policy() {
  local sudoers_path="/etc/sudoers.d/botty"
  local services=()
  parse_csv_to_array "$BOTTY_SERVICE_ALLOWLIST" services

  if [[ ${#services[@]} -eq 0 ]]; then
    services=("botty")
  fi

  local actions=("start" "stop" "restart" "status")
  local systemctl_entries=()
  local logs_entries=()
  for service in "${services[@]}"; do
    for action in "${actions[@]}"; do
      systemctl_entries+=("/usr/bin/systemctl $action $service")
    done
    logs_entries+=("/usr/bin/journalctl -u $service -n 20 --no-pager")
  done

  local joined_systemctl joined_logs
  joined_systemctl="$(IFS=', '; echo "${systemctl_entries[*]}")"
  joined_logs="$(IFS=', '; echo "${logs_entries[*]}")"

  msg "Writing scoped sudoers policy to $sudoers_path..."
  cat << EOL | sudo tee "$sudoers_path" > /dev/null
Cmnd_Alias BOTTY_SYSTEMCTL = $joined_systemctl
Cmnd_Alias BOTTY_LOGS = $joined_logs
Cmnd_Alias BOTTY_REBOOT = /usr/sbin/reboot, /usr/bin/reboot

$SERVICE_USER ALL=(root) NOPASSWD: BOTTY_SYSTEMCTL, BOTTY_LOGS, BOTTY_REBOOT
EOL

  sudo chown root:root "$sudoers_path"
  sudo chmod 440 "$sudoers_path"
  msg "${GREEN}✅ Sudoers policy updated at $sudoers_path.${NOFORMAT}"
}

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
  if [[ -n "$ENABLED_COMMANDS" ]] && [[ "$ENABLED_COMMANDS" != "__NONE__" ]]; then
    enabled_commands_line="ENABLED_COMMANDS=$ENABLED_COMMANDS"
  elif [[ "$ENABLED_COMMANDS" == "__NONE__" ]]; then
    enabled_commands_line="ENABLED_COMMANDS="
  fi
  local service_allowlist_line=""
  if [[ -n "$BOTTY_SERVICE_ALLOWLIST" ]]; then
    service_allowlist_line="BOTTY_SERVICE_ALLOWLIST=$BOTTY_SERVICE_ALLOWLIST"
  fi
  
  cat << EOL | sudo tee "$ENV_FILE_PATH" > /dev/null
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
AUTHORIZED_USER_ID=$AUTHORIZED_USER_ID
${enabled_commands_line}
${service_allowlist_line}
GOHOME_API_URL="$GOHOME_API_URL"
EMBY_DATA_PATH="$EMBY_DATA_PATH"
MEDIA_PATH="$MEDIA_PATH"
EOL
  sudo chown "$SERVICE_USER:$SERVICE_GROUP" "$ENV_FILE_PATH"
  sudo chmod 600 "$ENV_FILE_PATH"

  # Ensure service user can read and execute the installation tree.
  msg "Adjusting ownership for $INSTALL_DIR to $SERVICE_USER..."
  sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
  ensure_service_runtime_access "$SERVICE_USER" "$SERVICE_GROUP" "$INSTALL_DIR"

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
  setup_sudoers_policy

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
  require_non_root
  check_dependencies

  # Parse arguments
  local REINSTALL=false
  local UNINSTALL=false
  local UPDATE=false
  local INSTALL_DIR_OVERRIDE=""
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
      --install-dir=*)
        INSTALL_DIR_OVERRIDE="${arg#*=}"
        shift
        ;;
    esac
  done

  if [ "$UNINSTALL" = true ]; then
    ensure_sudo_access
    uninstall_service
    exit 0
  fi

  # Determine the installation directory
  if [[ -n "$INSTALL_DIR_OVERRIDE" ]]; then
    INSTALL_DIR="$INSTALL_DIR_OVERRIDE"
    if [[ -d ".git" ]] && [[ "$INSTALL_DIR" == "$(pwd)" ]]; then
      msg "${GREEN}Using explicit install dir: $INSTALL_DIR (current git repository).${NOFORMAT}"
      IS_LOCAL_INSTALL=true
      msg "${YELLOW}Note: service will run as '$SERVICE_USER' and installer will chown this directory to that user.${NOFORMAT}"
    else
      msg "${GREEN}Using explicit install dir: $INSTALL_DIR${NOFORMAT}"
      IS_LOCAL_INSTALL=false
    fi
  elif [ -d ".git" ]; then
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

  if [[ "$IS_LOCAL_INSTALL" != "true" ]]; then
    ensure_install_dir_access "$INSTALL_DIR"
  fi
  check_noexec_mount "$INSTALL_DIR"
  ensure_sudo_access
  
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

  if [[ "$REINSTALL" == "true" ]] || [[ -z "${BOTTY_SERVICE_ALLOWLIST+x}" ]]; then
    collect_service_allowlist
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
    if [[ -d "$INSTALL_DIR/.git" ]]; then
      if [[ "$UPDATE" == "true" ]]; then
        msg "${YELLOW}Directory $INSTALL_DIR already exists. Pulling latest changes.${NOFORMAT}"
        cd "$INSTALL_DIR"
        git pull
        cd - > /dev/null
      else
        msg "${YELLOW}Directory $INSTALL_DIR already exists. Skipping pull (use --update to force pull).${NOFORMAT}"
      fi
    elif [[ -d "$INSTALL_DIR" ]]; then
      if [[ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
        msg "${GREEN}Directory $INSTALL_DIR exists and is empty. Cloning repository.${NOFORMAT}"
        git clone "$GIT_REPO_URL" "$INSTALL_DIR"
      elif [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
        msg "${YELLOW}Directory $INSTALL_DIR exists and looks like a Python project (no .git). Using it as-is.${NOFORMAT}"
      else
        msg "${RED}Error: $INSTALL_DIR exists but is not a git checkout or Python project.${NOFORMAT}"
        msg "Either remove it, pick a different --install-dir, or clone the bot repo there first."
        exit 1
      fi
    else
      git clone "$GIT_REPO_URL" "$INSTALL_DIR"
    fi
  fi

  if [[ ! -f "$INSTALL_DIR/pyproject.toml" ]]; then
    msg "${RED}Error: $INSTALL_DIR is missing pyproject.toml. Aborting install.${NOFORMAT}"
    exit 1
  fi
  
  # Install dependencies
  msg "\n${BOLD}Creating Python virtual environment at $INSTALL_DIR/.venv...${NOFORMAT}"
  python3 -m venv "$INSTALL_DIR/.venv"

  msg "${BOLD}Installing Python packages...${NOFORMAT}"
  "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
  "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR"
  msg "${GREEN}✅ Python setup complete.${NOFORMAT}"

  collect_enabled_commands_interactive

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
