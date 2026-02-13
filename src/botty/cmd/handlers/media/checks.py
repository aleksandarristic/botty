import asyncio
import time

from botty.config import BottyConfig
from botty.utils import run_command

_CACHE_TTL_SECONDS = 15.0
_cache: tuple[float, tuple[str, str, str]] | None = None


async def get_emby_checks(config: BottyConfig) -> tuple[str, str, str]:
    global _cache
    if _cache is not None:
        ts, value = _cache
        if time.monotonic() - ts <= _CACHE_TTL_SECONDS:
            return value

    service_status, db_drive_status, media_drive_status = await asyncio.gather(
        run_command(
            ["systemctl", "status", "emby-server.service", "--no-pager", "-n", "0"]
        ),
        run_command(["df", "-h", config.emby_data_path]),
        run_command(["df", "-h", config.media_path]),
    )
    result = (service_status, db_drive_status, media_drive_status)
    _cache = (time.monotonic(), result)
    return result
