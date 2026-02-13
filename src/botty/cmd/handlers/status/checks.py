import asyncio
import time

from botty.utils import run_command

_CACHE_TTL_SECONDS = 15.0
_cache: tuple[float, tuple[str, str, str]] | None = None


async def get_status_checks() -> tuple[str, str, str]:
    global _cache
    if _cache is not None:
        ts, value = _cache
        if time.monotonic() - ts <= _CACHE_TTL_SECONDS:
            return value

    uptime, disk_usage, memory_usage = await asyncio.gather(
        run_command(["uptime", "-p"]),
        run_command(["df", "-h", "/"]),
        run_command(["free", "-h"]),
    )
    result = (uptime, disk_usage, memory_usage)
    _cache = (time.monotonic(), result)
    return result
