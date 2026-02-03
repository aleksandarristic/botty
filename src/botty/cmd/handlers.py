import os
from functools import wraps

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from .utils import escape_markdown, escape_markdown_code, run_command

# Parse authorized user IDs from a comma-separated string
auth_env = os.getenv("AUTHORIZED_USER_ID", "")
AUTHORIZED_USER_IDS = [uid.strip() for uid in auth_env.split(",") if uid.strip()]
GOHOME_API_URL = os.getenv("GOHOME_API_URL", "http://localhost:8080/status")
EMBY_DATA_PATH = os.getenv("EMBY_DATA_PATH", "/mnt/embydata")
MEDIA_PATH = os.getenv("MEDIA_PATH", "/mnt/media")


def authorized_only(func):
    """Decorator to restrict access to authorized users only."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if user_id not in AUTHORIZED_USER_IDS:
            await update.message.reply_text(
                "You are not authorized to use this command."
            )
            return
        return await func(update, context)

    return wrapper


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Here are the available commands:"
        "\n/start - Shows this message"
        "\n/help - Shows this message"
        "\n/status - General server health"
        "\n/emby_status - Emby media server status"
        "\n/adguard_status - AdGuard Home status"
        "\n/network_tests - Latest network test results"
    )


@authorized_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides a general server health check."""
    uptime = await run_command(["uptime", "-p"])
    disk_usage = await run_command(["df", "-h", "/"])
    memory_usage = await run_command(["free", "-h"])

    message = "*Server Status*\n\n"
    message += f"*Uptime:*\n```\n{escape_markdown_code(uptime)}\n```\n"
    message += f"*Memory Usage:*\n```\n{escape_markdown_code(memory_usage)}\n```\n"
    message += f"*Disk Usage \\(/\\):*\n```\n{escape_markdown_code(disk_usage)}\n```"

    await update.message.reply_text(message, parse_mode="MarkdownV2")


@authorized_only
async def emby_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Checks the status of Emby media server."""
    # -n 0 suppresses logs to avoid "Message too long" and parsing issues with special chars in logs
    service_status = await run_command(
        ["systemctl", "status", "emby-server.service", "--no-pager", "-n", "0"]
    )
    db_drive_status = await run_command(["df", "-h", EMBY_DATA_PATH])
    media_drive_status = await run_command(["df", "-h", MEDIA_PATH])

    message = "*Emby Media Server Status*\n\n"
    message += f"*Service Status:*\n```\n{escape_markdown_code(service_status)}\n```\n"
    message += f"*Database Drive \\({escape_markdown(EMBY_DATA_PATH)}\\):*\n```\n{escape_markdown_code(db_drive_status)}\n```\n"
    message += f"*Media Drive \\({escape_markdown(MEDIA_PATH)}\\):*\n```\n{escape_markdown_code(media_drive_status)}\n```"

    await update.message.reply_text(message, parse_mode="MarkdownV2")


@authorized_only
async def adguard_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Checks the status of AdGuard Home."""
    # -n 0 suppresses logs
    service_status = await run_command(
        ["systemctl", "status", "AdGuardHome.service", "--no-pager", "-n", "0"]
    )

    message = (
        f"*AdGuard Home Status*\n\n```\n{escape_markdown_code(service_status)}\n```"
    )

    await update.message.reply_text(message, parse_mode="MarkdownV2")


@authorized_only
async def network_tests_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Fetches the latest network test results."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(GOHOME_API_URL)
            response.raise_for_status()
            data = response.json()

            # Safely extract data with checks
            speed_data = data.get("speedtest", {})
            ping_data = data.get("ping", {})
            device_data = data.get("device", {})

            message = "*Network Test Results*\n\n"

            # Speedtest Section
            if speed_data and speed_data.get("Available"):
                dl = speed_data.get("DownloadMbps")
                ul = speed_data.get("UploadMbps")
                ping = speed_data.get("PingMs")
                last_updated = speed_data.get("LastUpdatedText", "N/A")
                next_run = speed_data.get("NextScheduledISO", "N/A")

                dl_str = f"{dl:.2f}" if isinstance(dl, (int, float)) else "N/A"
                ul_str = f"{ul:.2f}" if isinstance(ul, (int, float)) else "N/A"
                ping_str = f"{ping}" if ping is not None else "N/A"

                section = f"Download: {dl_str} Mbps\n"
                section += f"Upload:   {ul_str} Mbps\n"
                section += f"Ping:     {ping_str} ms\n"
                section += f"Updated:  {last_updated}\n"
                section += f"Next Run: {next_run}"

                message += f"*Speedtest:*\n```\n{escape_markdown_code(section)}\n```\n"
            else:
                message += "*Speedtest:*\n```\nNo data available\n```\n"

            # Ping Section
            if ping_data and ping_data.get("Available"):
                targets = ping_data.get("Targets", [])
                if targets:
                    section = ""
                    for target in targets:
                        name = target.get("Name", "Unknown")
                        avg = target.get("AvgMs")
                        loss = target.get("PacketLoss")

                        avg_str = (
                            f"{avg:.2f}" if isinstance(avg, (int, float)) else "N/A"
                        )
                        loss_str = f"{loss}" if loss is not None else "N/A"

                        section += (
                            f"{name[:15]:<15}: {avg_str:>6} ms (Loss: {loss_str:>3}%)\n"
                        )
                    message += (
                        f"*Ping:*\n```\n{escape_markdown_code(section.strip())}\n```\n"
                    )
                else:
                    message += "*Ping:*\\n```\\nNo targets found\\n```\\n"
            else:
                message += "*Ping:*\\n```\\nNo data available\\n```\\n"

            # Device Section
            if device_data and device_data.get("Available"):
                temp = device_data.get("TemperatureC")
                uptime = device_data.get("UptimeText")
                mem_used = device_data.get("MemoryUsedMB")
                mem_total = device_data.get("MemoryTotalMB")
                load_1 = device_data.get("Load1")
                load_5 = device_data.get("Load5")
                load_15 = device_data.get("Load15")

                temp_str = f"{temp}" if temp is not None else "N/A"
                uptime_str = uptime if uptime else "N/A"

                if isinstance(mem_used, (int, float)) and isinstance(
                    mem_total, (int, float)
                ):
                    mem_str = f"{mem_used / 1024:.2f}/{mem_total / 1024:.2f} GB used"
                else:
                    mem_str = "N/A"

                load_str = (
                    f"{load_1:.2f}, {load_5:.2f}, {load_15:.2f}"
                    if all(
                        isinstance(load, (int, float))
                        for load in [load_1, load_5, load_15]
                    )
                    else "N/A"
                )

                section = f"CPU Temp: {temp_str}°C\n"
                section += f"Memory:   {mem_str}\n"
                section += f"Loads:    {load_str}\n"
                section += f"Uptime:   {uptime_str}"

                message += (
                    f"*Device Metrics:*\n```\n{escape_markdown_code(section)}\n```"
                )
            else:
                message += "*Device Metrics:*\n```\nNo data available\n```"

            await update.message.reply_text(message, parse_mode="MarkdownV2")

    except httpx.RequestError as e:
        await update.message.reply_text(
            f"Could not connect to the GoHome API: {escape_markdown(str(e))}",
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        await update.message.reply_text(
            f"An error occurred: {escape_markdown(str(e))}", parse_mode="MarkdownV2"
        )
