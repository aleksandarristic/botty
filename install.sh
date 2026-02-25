#!/bin/bash

# ==============================================================================
# Botty Installer
#
# Installs/updates Botty, configures systemd, and generates scoped sudoers rules.
#
# Run as a normal user (NOT root). The script uses sudo for privileged steps.
# ==============================================================================

set -euo pipefail

# Default to the account running the installer so Botty can run as the current user
# without extra service-account setup.
DEFAULT_SERVICE_USER="$(id -un)"
SERVICE_NAME="botty"
SUDOERS_PATH="/etc/sudoers.d/botty"

setup_colors() {
  if [[ -t 2 ]] && [[ -z "${NO_COLOR-}" ]] && [[ "${TERM-}" != "dumb" ]]; then
    NOFORMAT='\033[0m'
    BOLD='\033[1m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
  else
    NOFORMAT='' BOLD='' RED='' GREEN='' YELLOW='' CYAN=''
  fi
}

msg() { echo >&2 -e "${1-}"; }

die() {
  msg "${RED}Error: $1${NOFORMAT}"
  exit 1
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  echo "$s"
}

require_non_root() {
  [[ "${EUID}" -ne 0 ]] || die "Do not run install.sh with sudo/root. Run as your normal user."
}

require_dependencies() {
  local deps=(git pip sudo rsync)
  local missing=()
  for dep in "${deps[@]}"; do
    command -v "$dep" >/dev/null 2>&1 || missing+=("$dep")
  done
  [[ ${#missing[@]} -eq 0 ]] || die "Missing dependencies: ${missing[*]}"
}

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    [[ -x "$PYTHON_BIN" ]] || die "--python-bin is not executable: $PYTHON_BIN"
    msg "${GREEN}Using explicit python: $PYTHON_BIN${NOFORMAT}"
    return
  fi

  if [[ -x "/usr/bin/python3" ]]; then
    PYTHON_BIN="/usr/bin/python3"
    msg "${GREEN}Using system python: $PYTHON_BIN${NOFORMAT}"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
    msg "${GREEN}Using python3 from PATH: $PYTHON_BIN${NOFORMAT}"
    return
  fi

  if command -v mise >/dev/null 2>&1; then
    local mise_python
    mise_python="$(mise which python 2>/dev/null || true)"
    if [[ -n "$mise_python" && -x "$mise_python" ]]; then
      PYTHON_BIN="$mise_python"
      msg "${YELLOW}Using mise python fallback: $PYTHON_BIN${NOFORMAT}"
      return
    fi
  fi

  die "No usable python found. Install python3 or pass --python-bin=<path>."
}

ensure_sudo_access() {
  msg "\n${BOLD}Requesting sudo access for privileged steps...${NOFORMAT}"
  sudo -v
}

check_noexec_mount() {
  local target="$1"
  command -v findmnt >/dev/null 2>&1 || return 0
  local options
  options="$(findmnt -no OPTIONS "$target" 2>/dev/null || true)"
  if [[ ",$options," == *",noexec,"* ]]; then
    die "$target is on a noexec mount. Choose a different install dir."
  fi
}

ensure_install_dir_access() {
  local install_dir="$1"
  local user group
  user="$(id -un)"
  group="$(id -gn)"

  if [[ ! -e "$install_dir" ]]; then
    msg "${YELLOW}Creating install dir $install_dir with sudo...${NOFORMAT}"
    sudo mkdir -p "$install_dir"
    sudo chown "$user:$group" "$install_dir"
    sudo chmod 755 "$install_dir"
    return
  fi

  [[ -d "$install_dir" ]] || die "$install_dir exists but is not a directory."
  if [[ ! -w "$install_dir" ]]; then
    msg "${YELLOW}Fixing ownership on $install_dir for current user...${NOFORMAT}"
    sudo chown -R "$user:$group" "$install_dir"
  fi
}

safe_load_env_file() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim "$line")"
    [[ -n "$line" ]] || continue
    [[ "${line:0:1}" == "#" ]] && continue
    [[ "$line" == *=* ]] || continue

    local key="${line%%=*}"
    local value="${line#*=}"
    key="$(trim "$key")"
    value="$(trim "$value")"
    if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
      value="${value:1:${#value}-2}"
    fi

    case "$key" in
      TELEGRAM_BOT_TOKEN) TELEGRAM_BOT_TOKEN="$value" ;;
      AUTHORIZED_USER_ID) AUTHORIZED_USER_ID="$value" ;;
      GOHOME_API_URL) GOHOME_API_URL="$value" ;;
      EMBY_DATA_PATH) EMBY_DATA_PATH="$value" ;;
      MEDIA_PATH) MEDIA_PATH="$value" ;;
      ENABLED_COMMANDS) ENABLED_COMMANDS_RAW="$value" ;;
      BOTTY_SERVICE_ALLOWLIST) BOTTY_SERVICE_ALLOWLIST="$value" ;;
      BOTTY_SUDO_PASSWORD) BOTTY_SUDO_PASSWORD="$value" ;;
    esac
  done < "$env_file"
}

prompt_secret_if_empty() {
  local var_name="$1"
  local prompt="$2"
  local current="${!var_name:-}"
  if [[ -z "$current" || "$REINSTALL" == "true" ]]; then
    read -rsp "$prompt" current
    echo
    [[ -n "$current" ]] || die "$var_name cannot be empty."
    printf -v "$var_name" "%s" "$current"
  fi
}

prompt_if_empty() {
  local var_name="$1"
  local prompt="$2"
  local default="$3"
  local current="${!var_name:-}"
  if [[ -z "$current" || "$REINSTALL" == "true" ]]; then
    read -rp "$prompt" current
    current="${current:-$default}"
    printf -v "$var_name" "%s" "$current"
  fi
}

parse_csv_to_array() {
  local input="$1"
  local -n out_ref="$2"
  out_ref=()
  IFS=',' read -r -a raw_items <<< "$input"
  for item in "${raw_items[@]}"; do
    item="$(trim "$item")"
    [[ -n "$item" ]] && out_ref+=("$item")
  done
}

validate_service_name() {
  local service="$1"
  [[ "$service" =~ ^[a-zA-Z0-9_.@-]+$ ]]
}

collect_service_allowlist() {
  BOTTY_SERVICE_ALLOWLIST="${BOTTY_SERVICE_ALLOWLIST:-botty}"
  msg "\n${BOLD}Enabled systemd services on this host:${NOFORMAT}"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl list-unit-files --type=service --state=enabled --no-legend --no-pager 2>/dev/null | awk '{print "  - " $1}' >&2 || true
  else
    msg "${YELLOW}systemctl not found; service list unavailable.${NOFORMAT}"
  fi

  msg "\nChoose service names Botty may manage via /service and /logs."
  read -rp "Enter BOTTY_SERVICE_ALLOWLIST (comma-separated, default: ${BOTTY_SERVICE_ALLOWLIST}): " selected
  if [[ -n "$(trim "$selected")" ]]; then
    BOTTY_SERVICE_ALLOWLIST="$selected"
  fi

  local services=()
  parse_csv_to_array "$BOTTY_SERVICE_ALLOWLIST" services
  [[ ${#services[@]} -gt 0 ]] || services=("botty")

  local normalized=()
  for service in "${services[@]}"; do
    validate_service_name "$service" || die "Invalid service name in allow-list: $service"
    normalized+=("$service")
  done
  BOTTY_SERVICE_ALLOWLIST="$(IFS=','; echo "${normalized[*]}")"
}

discover_commands() {
  sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/python" - "$INSTALL_DIR" << 'PY'
import sys
from pathlib import Path

install_dir = Path(sys.argv[1])
sys.path.insert(0, str(install_dir / "src"))

from botty.cmd.handlers import ALL_COMMAND_CLASSES  # noqa: E402
for cls in ALL_COMMAND_CLASSES:
    print(cls.name)
PY
}

collect_enabled_commands_interactive() {
  local commands=()
  mapfile -t commands < <(discover_commands)
  [[ ${#commands[@]} -gt 0 ]] || die "Could not discover bot commands from install tree."

  local current_display="all commands"
  if [[ "${ENABLED_COMMANDS_RAW}" == "__UNSET__" ]]; then
    current_display="all commands"
  elif [[ -z "${ENABLED_COMMANDS_RAW}" ]]; then
    current_display="none (except /start)"
  else
    current_display="${ENABLED_COMMANDS_RAW}"
  fi

  msg "\n${BOLD}Interactive Bot Command Selection${NOFORMAT}"
  msg "Current selection: ${CYAN}${current_display}${NOFORMAT}"
  msg "Available commands:"
  local i=1
  for cmd in "${commands[@]}"; do
    msg "  [$i] $cmd"
    ((i++))
  done
  msg "Choose by comma-separated numbers or names."
  msg "Special values: all, none, or Enter to keep current."

  local selection_raw selection lowered
  read -rp "Enter ENABLED_COMMANDS selection: " selection_raw
  selection="$(trim "$selection_raw")"
  [[ -n "$selection" ]] || return

  lowered="$(echo "$selection" | tr '[:upper:]' '[:lower:]')"
  if [[ "$lowered" == "all" ]]; then
    ENABLED_COMMANDS_RAW="__UNSET__"
    return
  fi
  if [[ "$lowered" == "none" ]]; then
    ENABLED_COMMANDS_RAW=""
    return
  fi

  local selected=()
  IFS=',' read -r -a items <<< "$selection"
  for item in "${items[@]}"; do
    item="$(trim "$item")"
    [[ -n "$item" ]] || continue
    if [[ "$item" =~ ^[0-9]+$ ]]; then
      local idx=$((item))
      ((idx >= 1 && idx <= ${#commands[@]})) || die "Invalid command index: $item"
      selected+=("${commands[$((idx-1))]}")
    else
      local found=false
      for cmd in "${commands[@]}"; do
        if [[ "$cmd" == "$item" ]]; then
          selected+=("$cmd")
          found=true
          break
        fi
      done
      [[ "$found" == "true" ]] || die "Unknown command: $item"
    fi
  done

  if [[ ${#selected[@]} -eq 0 ]]; then
    ENABLED_COMMANDS_RAW=""
    return
  fi

  local dedup=()
  for cmd in "${selected[@]}"; do
    local seen=false
    for existing in "${dedup[@]}"; do
      if [[ "$existing" == "$cmd" ]]; then
        seen=true
        break
      fi
    done
    [[ "$seen" == "false" ]] && dedup+=("$cmd")
  done
  ENABLED_COMMANDS_RAW="$(IFS=','; echo "${dedup[*]}")"
}

service_user_shell() {
  if [[ -x "/usr/sbin/nologin" ]]; then
    echo "/usr/sbin/nologin"
  elif [[ -x "/sbin/nologin" ]]; then
    echo "/sbin/nologin"
  else
    echo "/bin/false"
  fi
}

ensure_service_user() {
  local user="$1"
  local group="$1"
  if id -u "$user" >/dev/null 2>&1; then
    msg "${GREEN}✅ Service user '$user' already exists.${NOFORMAT}"
    return
  fi
  local shell_path
  shell_path="$(service_user_shell)"
  msg "Creating system user '$user'..."
  sudo groupadd --system "$group" 2>/dev/null || true
  sudo useradd --system --gid "$group" --create-home --home-dir "/home/$user" --shell "$shell_path" "$user"
  msg "${GREEN}✅ Created service user '$user'.${NOFORMAT}"
}

ensure_parent_traverse() {
  local user="$1"
  local path="$2"
  local current="$path"
  local parents=()
  while [[ "$current" != "/" ]]; do
    current="$(dirname "$current")"
    parents=("$current" "${parents[@]}")
  done
  for parent in "${parents[@]}"; do
    if ! sudo -u "$user" test -x "$parent" 2>/dev/null; then
      if command -v setfacl >/dev/null 2>&1; then
        sudo setfacl -m "u:${user}:x" "$parent"
      else
        die "Service user '$user' cannot traverse $parent and setfacl is unavailable."
      fi
    fi
  done
}

sync_source_to_install_dir() {
  local source_dir="$1"
  local install_dir="$2"

  [[ -f "$source_dir/pyproject.toml" ]] || die "Source dir '$source_dir' is missing pyproject.toml"
  mkdir -p "$install_dir"

  if [[ "$source_dir" == "$install_dir" ]]; then
    msg "${GREEN}Install dir is source dir; skipping sync.${NOFORMAT}"
    return
  fi

  msg "\n${BOLD}Syncing source from $source_dir -> $install_dir...${NOFORMAT}"
  rsync -a --delete \
    --exclude ".git/" \
    --exclude ".venv/" \
    --exclude "__pycache__/" \
    --exclude ".pytest_cache/" \
    --exclude ".ruff_cache/" \
    --exclude "tmp/" \
    "$source_dir/" "$install_dir/"
}

prepare_runtime_tree() {
  local user="$1"
  local group="$2"
  local dir="$3"
  ensure_parent_traverse "$user" "$dir"

  msg "${BOLD}Setting ownership and runtime permissions for $dir...${NOFORMAT}"
  sudo chown -R "$user:$group" "$dir"
  sudo chmod -R u=rwX,g=rX,o= "$dir"
  sudo chmod 750 "$dir"
}

build_python_env_as_service_user() {
  local user="$1"
  local group="$2"
  local dir="$3"

  msg "${YELLOW}Resetting virtual environment at $dir/.venv...${NOFORMAT}"
  sudo rm -rf "$dir/.venv"

  msg "\n${BOLD}Creating Python virtual environment at $dir/.venv...${NOFORMAT}"
  # Prefer copies to reduce runtime coupling to source interpreter path.
  # Some distros/Python builds can throw SameFileError for python3; retry without --copies.
  local venv_err
  venv_err="$(mktemp)"
  if ! sudo "$PYTHON_BIN" -m venv --copies "$dir/.venv" 2>"$venv_err"; then
    if rg -q "are the same file" "$venv_err"; then
      msg "${YELLOW}venv --copies failed with same-file error; retrying without --copies...${NOFORMAT}"
      sudo rm -rf "$dir/.venv"
      sudo "$PYTHON_BIN" -m venv "$dir/.venv"
    else
      cat "$venv_err" >&2
      rm -f "$venv_err"
      die "Failed to create virtual environment with $PYTHON_BIN"
    fi
  fi
  rm -f "$venv_err"
  sudo chown -R "$user:$group" "$dir/.venv"

  msg "${BOLD}Installing Python packages as $user...${NOFORMAT}"
  sudo -u "$user" "$dir/.venv/bin/pip" install --upgrade pip
  sudo -u "$user" "$dir/.venv/bin/pip" install -e "$dir"

  sudo -u "$user" test -x "$dir/.venv/bin/python" || die "Service user '$user' cannot execute $dir/.venv/bin/python"
  sudo -u "$user" test -x "$dir/.venv/bin/botty" || die "Service user '$user' cannot execute $dir/.venv/bin/botty"
}

write_env_file() {
  local user="$1"
  local group="$2"
  local env_file="$3"

  local enabled_line=""
  if [[ "$ENABLED_COMMANDS_RAW" != "__UNSET__" ]]; then
    enabled_line="ENABLED_COMMANDS=$ENABLED_COMMANDS_RAW"
  fi
  local allowlist_line="BOTTY_SERVICE_ALLOWLIST=$BOTTY_SERVICE_ALLOWLIST"
  local sudo_pass_line=""
  if [[ -n "${BOTTY_SUDO_PASSWORD:-}" ]]; then
    sudo_pass_line="BOTTY_SUDO_PASSWORD=$BOTTY_SUDO_PASSWORD"
  fi

  msg "Writing $env_file..."
  cat << EOF_ENV | sudo tee "$env_file" > /dev/null
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
AUTHORIZED_USER_ID=$AUTHORIZED_USER_ID
$enabled_line
$allowlist_line
$sudo_pass_line
GOHOME_API_URL="$GOHOME_API_URL"
EMBY_DATA_PATH="$EMBY_DATA_PATH"
MEDIA_PATH="$MEDIA_PATH"
EOF_ENV

  sudo chown "$user:$group" "$env_file"
  sudo chmod 600 "$env_file"
}

write_sudoers_policy() {
  local services=()
  parse_csv_to_array "$BOTTY_SERVICE_ALLOWLIST" services
  [[ ${#services[@]} -gt 0 ]] || services=("botty")

  local actions=(start stop restart status)
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

  msg "Writing scoped sudoers policy at $SUDOERS_PATH..."
  cat << EOF_SUDO | sudo tee "$SUDOERS_PATH" > /dev/null
Cmnd_Alias BOTTY_SYSTEMCTL = $joined_systemctl
Cmnd_Alias BOTTY_LOGS = $joined_logs
Cmnd_Alias BOTTY_REBOOT = /usr/sbin/reboot, /usr/bin/reboot

$SERVICE_USER ALL=(root) NOPASSWD: BOTTY_SYSTEMCTL, BOTTY_LOGS, BOTTY_REBOOT
EOF_SUDO
  sudo chown root:root "$SUDOERS_PATH"
  sudo chmod 440 "$SUDOERS_PATH"
}

write_systemd_unit() {
  local group="$1"
  local env_file="$2"
  local unit_path="/etc/systemd/system/${SERVICE_NAME}.service"

  msg "Writing systemd unit at $unit_path..."
  cat << EOF_UNIT | sudo tee "$unit_path" > /dev/null
[Unit]
Description=Botty Telegram Bot
After=network.target

[Service]
User=$SERVICE_USER
Group=$group
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/botty
EnvironmentFile=$env_file
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF_UNIT
}

setup_systemd_service() {
  command -v systemctl >/dev/null 2>&1 || die "systemctl not found."
  local group
  group="$(id -gn "$SERVICE_USER")"
  local env_file="$INSTALL_DIR/botty.env"

  write_env_file "$SERVICE_USER" "$group" "$env_file"
  write_systemd_unit "$group" "$env_file"
  write_sudoers_policy

  msg "Reloading and starting ${SERVICE_NAME}.service..."
  sudo systemctl daemon-reload
  sudo systemctl enable "${SERVICE_NAME}.service"
  sudo systemctl restart "${SERVICE_NAME}.service"
}

uninstall_service() {
  local unit_path="/etc/systemd/system/${SERVICE_NAME}.service"
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl stop "${SERVICE_NAME}.service" || true
    sudo systemctl disable "${SERVICE_NAME}.service" || true
    sudo rm -f "$unit_path"
    sudo systemctl daemon-reload
    sudo systemctl reset-failed
  fi
  sudo rm -f "$SUDOERS_PATH"
  msg "${GREEN}✅ Uninstall complete.${NOFORMAT}"
}

main() {
  setup_colors
  require_non_root
  require_dependencies

  REINSTALL=false
  UNINSTALL=false
  UPDATE=false
  INSTALL_DIR_OVERRIDE=""
  SERVICE_USER="$DEFAULT_SERVICE_USER"
  PYTHON_BIN="${PYTHON_BIN:-}"
  SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  for arg in "$@"; do
    case "$arg" in
      --reinstall) REINSTALL=true ;;
      --uninstall) UNINSTALL=true ;;
      --update) UPDATE=true ;;
      --service-user=*) SERVICE_USER="${arg#*=}" ;;
      --install-dir=*) INSTALL_DIR_OVERRIDE="${arg#*=}" ;;
      --python-bin=*) PYTHON_BIN="${arg#*=}" ;;
      *) die "Unknown argument: $arg" ;;
    esac
  done

  ensure_sudo_access
  resolve_python_bin

  if [[ "$UNINSTALL" == "true" ]]; then
    uninstall_service
    exit 0
  fi

  if [[ "$UPDATE" == "true" ]]; then
    msg "${YELLOW}Note: --update no longer pulls from git in install dir.${NOFORMAT}"
    msg "${YELLOW}Run 'git pull' in your source repo before running install.sh.${NOFORMAT}"
  fi

  if [[ -n "$INSTALL_DIR_OVERRIDE" ]]; then
    INSTALL_DIR="$INSTALL_DIR_OVERRIDE"
    msg "${GREEN}Using explicit install dir: $INSTALL_DIR${NOFORMAT}"
  elif [[ -d "$SOURCE_DIR/.git" ]]; then
    INSTALL_DIR="$SOURCE_DIR"
    msg "${GREEN}Installing in-place from source dir: $INSTALL_DIR${NOFORMAT}"
  else
    read -rp "Enter install path (default: /opt/botty): " INSTALL_DIR
    INSTALL_DIR="${INSTALL_DIR:-/opt/botty}"
  fi

  if [[ "$INSTALL_DIR" != "$SOURCE_DIR" ]]; then
    ensure_install_dir_access "$INSTALL_DIR"
  fi

  if [[ "$INSTALL_DIR" == "$SOURCE_DIR" ]] && [[ "$SERVICE_USER" != "$(id -un)" ]]; then
    die "In-place install with --service-user=$SERVICE_USER would change source repo ownership. Use --install-dir=/opt/botty."
  fi

  check_noexec_mount "$INSTALL_DIR"

  local env_file="$INSTALL_DIR/botty.env"
  TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
  AUTHORIZED_USER_ID="${AUTHORIZED_USER_ID:-}"
  GOHOME_API_URL="${GOHOME_API_URL:-}"
  EMBY_DATA_PATH="${EMBY_DATA_PATH:-}"
  MEDIA_PATH="${MEDIA_PATH:-}"
  ENABLED_COMMANDS_RAW="__UNSET__"
  BOTTY_SERVICE_ALLOWLIST="${BOTTY_SERVICE_ALLOWLIST:-}"
  BOTTY_SUDO_PASSWORD="${BOTTY_SUDO_PASSWORD:-}"

  if [[ -f "$env_file" && "$REINSTALL" == "false" ]]; then
    msg "${GREEN}Found existing config at $env_file. Loading known keys...${NOFORMAT}"
    safe_load_env_file "$env_file"
  fi

  prompt_secret_if_empty TELEGRAM_BOT_TOKEN "Enter TELEGRAM_BOT_TOKEN: "
  prompt_if_empty AUTHORIZED_USER_ID "Enter AUTHORIZED_USER_ID (comma-separated): " ""
  prompt_if_empty GOHOME_API_URL "Enter GOHOME API URL (default: http://localhost:8080/status): " "http://localhost:8080/status"
  prompt_if_empty EMBY_DATA_PATH "Enter Emby data path (default: /mnt/embydata): " "/mnt/embydata"
  prompt_if_empty MEDIA_PATH "Enter media storage path (default: /mnt/media): " "/mnt/media"

  collect_service_allowlist
  sync_source_to_install_dir "$SOURCE_DIR" "$INSTALL_DIR"
  [[ -f "$INSTALL_DIR/pyproject.toml" ]] || die "$INSTALL_DIR is missing pyproject.toml"

  ensure_service_user "$SERVICE_USER"
  local service_group
  service_group="$(id -gn "$SERVICE_USER")"

  if [[ "$INSTALL_DIR" == "$SOURCE_DIR" && "$SERVICE_USER" == "$(id -un)" ]]; then
    msg "${GREEN}In-place install as current user; skipping ownership/permission hardening.${NOFORMAT}"
  else
    prepare_runtime_tree "$SERVICE_USER" "$service_group" "$INSTALL_DIR"
  fi
  build_python_env_as_service_user "$SERVICE_USER" "$service_group" "$INSTALL_DIR"
  collect_enabled_commands_interactive
  setup_systemd_service

  msg "\n${GREEN}${BOLD}✅ Botty installation complete.${NOFORMAT}"
  msg "Service user: ${CYAN}$SERVICE_USER${NOFORMAT}"
  msg "Service status: ${CYAN}sudo systemctl status ${SERVICE_NAME}.service${NOFORMAT}"
  msg "Logs:          ${CYAN}sudo journalctl -u ${SERVICE_NAME}.service -f${NOFORMAT}"
}

main "$@"
