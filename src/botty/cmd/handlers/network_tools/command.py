import socket
import struct
import re
from telegram import Update
from telegram.ext import ContextTypes

from botty.cmd.handlers.base import Command
from botty.utils import escape_markdown_code, run_command, escape_markdown


class PingCommand(Command):
    name = "ping"
    description = "Ping a host"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /ping <host>
        """
        reply_message = self._require_message(update)
        
        if not context.args:
             await self._reply_markdown(
                reply_message,
                "Usage: `/ping <host>`"
            )
             return

        host = context.args[0]
        # Sanitize host? ping command is relatively safe but let's be careful.
        # Allow alphanumeric, dots, dashes.
        if not re.match(r"^[a-zA-Z0-9.-]+$", host):
             await self._reply_markdown(reply_message, "Invalid host format.")
             return

        cmd = ["ping", "-c", "3", host]
        output = await run_command(cmd)
        
        await self._reply_markdown(
            reply_message,
            f"*Ping Result for {escape_markdown(host)}*\n```\n{escape_markdown_code(output)}\n```"
        )


class WolCommand(Command):
    name = "wol"
    description = "Send Wake-on-LAN magic packet"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /wol <mac_address>
        """
        reply_message = self._require_message(update)
        
        if not context.args:
             await self._reply_markdown(
                reply_message,
                "Usage: `/wol <mac_address>`\n"
                "Format: `AA:BB:CC:DD:EE:FF`"
            )
             return

        mac_address = context.args[0]
        
        try:
            self._send_magic_packet(mac_address)
            await self._reply_markdown(
                reply_message,
                f"Magic packet sent to `{escape_markdown_code(mac_address)}`."
            )
        except ValueError:
             await self._reply_markdown(
                reply_message,
                "Invalid MAC address format. Use `XX:XX:XX:XX:XX:XX`."
            )
        except Exception as e:
             await self._reply_markdown(
                reply_message,
                f"Failed to send WOL packet: {escape_markdown(str(e))}"
            )

    def _send_magic_packet(self, mac_address: str) -> None:
        # Validate and clean MAC
        mac_clean = mac_address.replace(":", "").replace("-", "")
        if len(mac_clean) != 12 or not re.match(r"^[0-9a-fA-F]+$", mac_clean):
            raise ValueError("Invalid MAC address")

        data = bytes.fromhex("FF" * 6 + mac_clean * 16)
        
        # Broadcast to 255.255.255.255
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, ("255.255.255.255", 9))
