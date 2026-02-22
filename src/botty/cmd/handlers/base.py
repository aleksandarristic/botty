from abc import ABC, abstractmethod
import logging
import re

from telegram import Message, Update
from telegram.error import BadRequest

from botty.config import BottyConfig
from botty.utils import run_command, verify_totp

logger = logging.getLogger(__name__)


class Command(ABC):
    """Base class for bot commands."""

    name: str
    description: str
    auth_required: bool = True
    sudo: bool = False
    requires_totp: bool = False

    def __init__(self, config: BottyConfig) -> None:
        self.config = config

    def _get_message(self, update: Update) -> Message | None:
        message = update.message
        return message if message is not None else update.effective_message

    def _require_message(self, update: Update) -> Message:
        message = self._get_message(update)
        if message is None:
            raise ValueError("Command requires a message update.")
        return message

    async def _reply_markdown(self, message: Message, text: str) -> None:
        """Send MarkdownV2 reply with a plain-text fallback on parse errors."""
        try:
            await message.reply_text(text, parse_mode="MarkdownV2")
        except BadRequest as exc:
            if "Can't parse entities" not in str(exc):
                raise
            logger.warning(
                "command.markdown_parse_failed",
                extra={"command": getattr(self, "name", self.__class__.__name__)},
                exc_info=exc,
            )
            await message.reply_text(text)

    async def handle(self, update: Update, context) -> None:
        """Shared entrypoint for command execution."""
        message = self._get_message(update)
        if self.auth_required and not self.config.is_authorized(update):
            return
        if message is None:
            return
        if self.requires_totp_for(update, context):
            if not self.config.totp_secret:
                await message.reply_text(
                    "TOTP is not configured. Set TOTP_SECRET to use this command."
                )
                return

            code = self._extract_totp_from_context(context)
            if code is None:
                await message.reply_text(
                    "TOTP required. Append a 6-digit code as the last command argument."
                )
                return

            if not verify_totp(
                code,
                self.config.totp_secret,
                window_steps=self.config.totp_window_steps,
            ):
                await message.reply_text("Invalid or expired TOTP code.")
                return
        try:
            await self.run(update, context)
        except Exception:
            logger.exception(
                "command.run_failed",
                extra={"command": getattr(self, "name", self.__class__.__name__)},
            )
            await message.reply_text("Error executing command.")

    async def _run_command(
        self,
        command: list[str],
        timeout: float = 10.0,
        sudo: bool | None = None,
        cwd: str | None = None,
    ) -> str:
        """Execute shell commands with command-level sudo defaults."""
        use_sudo = self.sudo if sudo is None else sudo
        if cwd is None:
            return await run_command(command, timeout=timeout, sudo=use_sudo)
        return await run_command(command, timeout=timeout, sudo=use_sudo, cwd=cwd)

    @abstractmethod
    async def run(self, update: Update, context) -> None:
        """Implement command behavior."""
        raise NotImplementedError

    def requires_totp_for(self, update: Update, context) -> bool:
        return self.requires_totp

    def _extract_totp_from_context(self, context) -> str | None:
        args = getattr(context, "args", None)
        if not isinstance(args, list) or not args:
            return None
        candidate = args[-1]
        if not isinstance(candidate, str):
            return None
        candidate = candidate.strip()
        if not re.fullmatch(r"\d{6}", candidate):
            return None
        return candidate

    @property
    def handler(self):
        """Return the handler callable for registration."""
        return self.handle
