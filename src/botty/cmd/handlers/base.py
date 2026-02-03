from abc import ABC, abstractmethod

from botty.cmd.utils import is_authorized


class Command(ABC):
    """Base class for bot commands."""

    name: str
    auth_required: bool = True

    async def handle(self, update, context) -> None:
        """Shared entrypoint for command execution."""
        if self.auth_required and not is_authorized(update):
            await update.message.reply_text(
                "You are not authorized to use this command."
            )
            return
        await self.run(update, context)

    @abstractmethod
    async def run(self, update, context) -> None:
        """Implement command behavior."""
        raise NotImplementedError

    @property
    def handler(self):
        """Return the handler callable for registration."""
        return self.handle
