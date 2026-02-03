import asyncio

from botty.cmd.utils import run_command
from botty.config import BottyConfig


async def get_status_checks() -> tuple[str, str, str]:
    uptime, disk_usage, memory_usage = await asyncio.gather(
        run_command(["uptime", "-p"]),
        run_command(["df", "-h", "/"]),
        run_command(["free", "-h"]),
    )
    return uptime, disk_usage, memory_usage


async def get_emby_checks(config: BottyConfig) -> tuple[str, str, str]:
    service_status, db_drive_status, media_drive_status = await asyncio.gather(
        run_command(
            ["systemctl", "status", "emby-server.service", "--no-pager", "-n", "0"]
        ),
        run_command(["df", "-h", config.emby_data_path]),
        run_command(["df", "-h", config.media_path]),
    )
    return service_status, db_drive_status, media_drive_status


async def get_adguard_checks() -> str:
    return await run_command(
        ["systemctl", "status", "AdGuardHome.service", "--no-pager", "-n", "0"]
    )
