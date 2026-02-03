import asyncio
import time

from botty.utils import run_command
from botty.config import BottyConfig

_CACHE_TTL_SECONDS = 15.0
_CACHE: dict[str, tuple[float, object]] = {}


def _get_cached(key: str):
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return value


def _set_cached(key: str, value: object) -> None:
    _CACHE[key] = (time.monotonic(), value)


async def get_status_checks() -> tuple[str, str, str]:
    cached = _get_cached("status")
    if cached is not None:
        return cached
    uptime, disk_usage, memory_usage = await asyncio.gather(
        run_command(["uptime", "-p"]),
        run_command(["df", "-h", "/"]),
        run_command(["free", "-h"]),
    )
    result = (uptime, disk_usage, memory_usage)
    _set_cached("status", result)
    return result


async def get_emby_checks(config: BottyConfig) -> tuple[str, str, str]:
    cached = _get_cached("emby")
    if cached is not None:
        return cached
    service_status, db_drive_status, media_drive_status = await asyncio.gather(
        run_command(
            ["systemctl", "status", "emby-server.service", "--no-pager", "-n", "0"]
        ),
        run_command(["df", "-h", config.emby_data_path]),
        run_command(["df", "-h", config.media_path]),
    )
    result = (service_status, db_drive_status, media_drive_status)
    _set_cached("emby", result)
    return result


async def get_adguard_checks() -> str:
    cached = _get_cached("adguard")
    if cached is not None:
        return cached
    result = await run_command(
        ["systemctl", "status", "AdGuardHome.service", "--no-pager", "-n", "0"]
    )
    _set_cached("adguard", result)
    return result
