from __future__ import annotations

import logging

from botty.utils import escape_markdown_code

logger = logging.getLogger(__name__)


class GoHomeParseError(ValueError):
    """Raised when the GoHome payload cannot be parsed."""


def format_network_tests(data: dict) -> str:
    """Format GoHome API response data into a MarkdownV2 message."""
    if not isinstance(data, dict):
        logger.warning("gohome.invalid_payload", extra={"payload_type": type(data)})
        raise GoHomeParseError("GoHome payload must be a dict")

    speed_data = data.get("speedtest", {})
    ping_data = data.get("ping", {})
    device_data = data.get("device", {})

    message = "*Network Test Results*\n\n"

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

    if ping_data and ping_data.get("Available"):
        targets = ping_data.get("Targets", [])
        if targets:
            section = ""
            for target in targets:
                name = target.get("Name", "Unknown")
                avg = target.get("AvgMs")
                loss = target.get("PacketLoss")

                avg_str = f"{avg:.2f}" if isinstance(avg, (int, float)) else "N/A"
                loss_str = f"{loss}" if loss is not None else "N/A"
                section += f"{name[:15]:<15}: {avg_str:>6} ms (Loss: {loss_str:>3}%)\n"
            message += f"*Ping:*\n```\n{escape_markdown_code(section.strip())}\n```\n"
        else:
            message += "*Ping:*\\n```\\nNo targets found\\n```\\n"
    else:
        message += "*Ping:*\\n```\\nNo data available\\n```\\n"

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

        if isinstance(mem_used, (int, float)) and isinstance(mem_total, (int, float)):
            mem_str = f"{mem_used / 1024:.2f}/{mem_total / 1024:.2f} GB used"
        else:
            mem_str = "N/A"

        load_str = (
            f"{load_1:.2f}, {load_5:.2f}, {load_15:.2f}"
            if all(isinstance(load, (int, float)) for load in [load_1, load_5, load_15])
            else "N/A"
        )

        section = f"CPU Temp: {temp_str}°C\n"
        section += f"Memory:   {mem_str}\n"
        section += f"Loads:    {load_str}\n"
        section += f"Uptime:   {uptime_str}"
        message += f"*Device Metrics:*\n```\n{escape_markdown_code(section)}\n```"
    else:
        message += "*Device Metrics:*\n```\nNo data available\n```"

    return message
