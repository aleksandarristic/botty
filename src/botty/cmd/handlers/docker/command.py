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

        await self._reply_markdown(reply_message, message)

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


class DockerListCommand(Command):
    name = "docker_list"
    description = "List all docker containers"

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /docker_list
        """
        reply_message = self._require_message(update)
        
        cmd = ["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}"]
        output = await run_command(cmd)
        
        if not output.strip():
            output = "No containers found or docker daemon not reachable."
            
        await self._reply_markdown(
            reply_message,
            f"*Docker Containers*\n```\n{escape_markdown_code(output)}\n```"
        )


class DockerRestartCommand(Command):
    name = "docker_restart"
    description = "Restart a docker container"
    requires_totp = True

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Usage: /docker_restart <container_name>
        """
        reply_message = self._require_message(update)
        
        if not context.args:
             await self._reply_markdown(
                reply_message,
                "Usage: `/docker_restart <container_name>`"
            )
             return

        container_name = context.args[0]
        # Minimal sanitization, though docker CLI handles errors well.
        if not container_name.replace("-", "").replace(".", "").replace("_", "").isalnum():
             await self._reply_markdown(reply_message, "Invalid container name.")
             return

        cmd = ["docker", "restart", container_name]
        output = await run_command(cmd)
        
        if not output.strip():
            # success usually outputs the container name
             output = f"Container {container_name} restarted."
        
        await self._reply_markdown(
            reply_message,
            f"*Docker Restart*\n```\n{escape_markdown_code(output)}\n```"
        )


__all__ = ["DockerStatusCommand", "DockerListCommand", "DockerRestartCommand"]
