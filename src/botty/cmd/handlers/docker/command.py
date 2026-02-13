import os

from telegram import Update
from telegram.ext import ContextTypes

from botty.utils import escape_markdown, escape_markdown_code, run_command
from botty.cmd.handlers.base import Command

class DockerStatusCommand(Command):
    name = "docker_status"
    description = "Docker daemon status and optional compose service state"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        reply_message = self._require_message(update)
        docker_info = await run_command(["docker", "info"])

        compose_output = ""
        compose_target = " ".join(context.args).strip() if context.args else ""
        if compose_target:
            compose_output = await self._get_compose_status(compose_target)

        message = "*Docker Status*\n\n"
        message += f"*Docker Info:*\n```\n{escape_markdown_code(docker_info)}\n```\n"
        if compose_target:
            message += (
                f"*Compose \\({escape_markdown(compose_target)}\\):*\n"
                f"```\n{escape_markdown_code(compose_output)}\n```"
            )
        else:
            message += (
                "*Compose:*\n```\n"
                "Not requested. Pass a directory or compose file path.\n"
                "Example: /docker_status /opt/stacks/home\n```"
            )

        await reply_message.reply_text(message, parse_mode="MarkdownV2")

    async def _get_compose_status(self, target: str) -> str:
        compose_file = target
        if not target.endswith((".yml", ".yaml")):
            compose_file = self._resolve_compose_file(target)
            if compose_file is None:
                return f"Error: No compose file found in directory: {target}"

        return await run_command(["docker", "compose", "-f", compose_file, "ps"])

    def _resolve_compose_file(self, directory: str) -> str | None:
        candidates = [
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml",
        ]
        for name in candidates:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        return None


__all__ = ["DockerStatusCommand"]
