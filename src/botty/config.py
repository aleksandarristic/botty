from dataclasses import dataclass
import os
from typing import List


@dataclass
class BottyConfig:
    telegram_bot_token: str | None
    authorized_user_ids: List[str]
    gohome_api_url: str
    emby_data_path: str
    media_path: str

    @classmethod
    def from_env(cls) -> "BottyConfig":
        auth_env = os.getenv("AUTHORIZED_USER_ID", "")
        authorized_user_ids = [uid.strip() for uid in auth_env.split(",") if uid.strip()]
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            authorized_user_ids=authorized_user_ids,
            gohome_api_url=os.getenv("GOHOME_API_URL", "http://localhost:8080/status"),
            emby_data_path=os.getenv("EMBY_DATA_PATH", "/mnt/embydata"),
            media_path=os.getenv("MEDIA_PATH", "/mnt/media"),
        )

    def is_authorized(self, update) -> bool:
        return str(update.effective_user.id) in self.authorized_user_ids
