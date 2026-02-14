from dataclasses import dataclass
import os
from typing import List

from telegram import Update


@dataclass
class BottyConfig:
    telegram_bot_token: str | None
    authorized_user_ids: List[str]
    authorized_chat_ids: List[str]
    service_allowlist: List[str]
    enabled_commands: List[str] | None
    gohome_api_url: str
    gohome_timeout_seconds: float
    emby_data_path: str
    media_path: str
    telegram_poll_timeout_seconds: float = 300.0
    totp_secret: str | None = None
    totp_window_steps: int = 1

    @classmethod
    def from_env(cls) -> "BottyConfig":
        auth_env = os.getenv("AUTHORIZED_USER_ID", "")
        authorized_user_ids = [
            uid.strip() for uid in auth_env.split(",") if uid.strip()
        ]
        chat_auth_env = os.getenv("AUTHORIZED_CHAT_ID", "")
        authorized_chat_ids = [
            cid.strip() for cid in chat_auth_env.split(",") if cid.strip()
        ]
        service_allowlist_env = os.getenv("BOTTY_SERVICE_ALLOWLIST", "")
        service_allowlist = [
            svc.strip() for svc in service_allowlist_env.split(",") if svc.strip()
        ]

        enabled_cmd_env = os.getenv("ENABLED_COMMANDS")
        if enabled_cmd_env is not None and enabled_cmd_env.strip():
            enabled_commands = [
                cmd.strip() for cmd in enabled_cmd_env.split(",") if cmd.strip()
            ]
        else:
            enabled_commands = None

        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            authorized_user_ids=authorized_user_ids,
            authorized_chat_ids=authorized_chat_ids,
            service_allowlist=service_allowlist,
            enabled_commands=enabled_commands,
            gohome_api_url=os.getenv("GOHOME_API_URL", "http://localhost:8080/status"),
            gohome_timeout_seconds=float(os.getenv("GOHOME_TIMEOUT_SECONDS", "10")),
            emby_data_path=os.getenv("EMBY_DATA_PATH", "/mnt/embydata"),
            media_path=os.getenv("MEDIA_PATH", "/mnt/media"),
            telegram_poll_timeout_seconds=float(
                os.getenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "300")
            ),
            totp_secret=os.getenv("TOTP_SECRET"),
            totp_window_steps=int(os.getenv("TOTP_WINDOW_STEPS", "1")),
        )

    def is_authorized(self, update: Update) -> bool:
        user = update.effective_user
        chat = update.effective_chat
        if user is None or str(user.id) not in self.authorized_user_ids:
            return False
        if chat is None:
            return False
        if chat.type == "private":
            return True
        return str(chat.id) in self.authorized_chat_ids

    @staticmethod
    def _normalize_service_name(service_name: str) -> str:
        candidate = service_name.strip().lower()
        if candidate.endswith(".service"):
            candidate = candidate[: -len(".service")]
        return candidate

    def is_service_allowed(self, service_name: str) -> bool:
        requested = self._normalize_service_name(service_name)
        if not requested:
            return False
        allowlisted = {
            self._normalize_service_name(svc)
            for svc in self.service_allowlist
            if isinstance(svc, str) and svc.strip()
        }
        if not allowlisted:
            return False
        return requested in allowlisted
