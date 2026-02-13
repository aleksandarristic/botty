import time

from botty.utils import run_command

_CACHE_TTL_SECONDS = 15.0
_cache: tuple[float, str] | None = None


async def get_adguard_checks() -> str:
    global _cache
    if _cache is not None:
        ts, value = _cache
        if time.monotonic() - ts <= _CACHE_TTL_SECONDS:
            return value

    result = await run_command(
        ["systemctl", "status", "AdGuardHome.service", "--no-pager", "-n", "0"]
    )
    _cache = (time.monotonic(), result)
    return result
