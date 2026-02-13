import os
import glob
from telegram import Update
from telegram.ext import ContextTypes

from botty.cmd.handlers.base import Command
from botty.utils import escape_markdown_code, run_command, escape_markdown


class TopCommand(Command):
    name = "top"
    description = "Show top CPU consuming processes"
    max_rows: int = 15

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /top
        """
        reply_message = self._require_message(update)
        
        # ps command to list top processes by CPU usage
        # Linux: ps -eo pid,cmd,%cpu,%mem --sort=-%cpu
        # macOS: ps -eo pid,command,pcpu,pmem -r (but -r sorts by cpu)
        # We will try Linux syntax first, if it fails (returns usage/error), try macOS fallback or just fail.
        # But for this bot, we target Linux.
        
        cmd = ["ps", "-eo", "pid,cmd,%cpu,%mem", "--sort=-%cpu"]
        output = await run_command(cmd)
        
        if "error" in output.lower() or "usage:" in output.lower():
             # Fallback for macOS dev environment?
             cmd = ["ps", "-eo", "pid,command,pcpu,pmem", "-r"]
             output = await run_command(cmd)

        lines = output.splitlines()
        # Header + top N rows
        top_lines = lines[: self.max_rows + 1]
        
        formatted_output = "\n".join(top_lines)
        
        await self._reply_markdown(
            reply_message,
            f"*Top Processes*\n```\n{escape_markdown_code(formatted_output)}\n```"
        )


class TempCommand(Command):
    name = "temp"
    description = "Show system temperatures"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /temp
        """
        reply_message = self._require_message(update)
        
        # Try sensors first
        sensors_output = await run_command(["sensors"])
        if "not found" not in sensors_output and "Error" not in sensors_output and sensors_output.strip():
             await self._reply_markdown(
                reply_message,
                f"*System Temperatures (sensors)*\n```\n{escape_markdown_code(sensors_output)}\n```"
            )
             return

        # Fallback to /sys/class/thermal
        temps = await self._get_sys_temperatures()
        
        if temps:
             message = "*System Temperatures*\n\n"
             for label, temp in temps.items():
                 message += f"*{escape_markdown(label)}*: `{escape_markdown_code(temp)}`\n"
             await self._reply_markdown(reply_message, message)
        else:
             await self._reply_markdown(
                reply_message,
                "Could not detect temperature sensors (tried `sensors` and `/sys/class/thermal`)."
            )

    async def _get_sys_temperatures(self) -> dict[str, str]:
        results = {}
        thermal_zones = glob.glob("/sys/class/thermal/thermal_zone*")
        for zone in thermal_zones:
            try:
                type_file = os.path.join(zone, "type")
                temp_file = os.path.join(zone, "temp")
                
                if os.path.exists(type_file) and os.path.exists(temp_file):
                    with open(type_file, "r") as f:
                        label = f.read().strip()
                    with open(temp_file, "r") as f:
                        temp_str = f.read().strip()
                        # Some temp files are in millidegrees
                        try:
                            temp_c = int(temp_str) / 1000.0
                            results[label] = f"{temp_c:.1f}°C"
                        except ValueError:
                             results[label] = temp_str
            except (ValueError, OSError):
                continue
        return results


class LogsCommand(Command):
    name = "logs"
    description = "Show service logs"
    sudo = True

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /logs <service_name>
        """
        reply_message = self._require_message(update)
        
        if not context.args:
             await self._reply_markdown(
                reply_message,
                "Usage: `/logs <service_name>`"
            )
             return

        service_name = context.args[0]
        # Sanitize
        if not service_name.replace("-", "").replace(".", "").replace("_", "").isalnum():
             await self._reply_markdown(reply_message, "Invalid service name.")
             return

        cmd = ["journalctl", "-u", service_name, "-n", "20", "--no-pager"]
        output = await self._run_command(cmd)
        
        if not output.strip():
            output = "No logs found or service does not exist."

        # Truncate if too long
        if len(output) > 3000:
            output = "..." + output[-3000:]

        await self._reply_markdown(
            reply_message,
            f"*Logs for {escape_markdown(service_name)}*\n```\n{escape_markdown_code(output)}\n```"
        )
