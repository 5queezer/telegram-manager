import logging
from typing import Callable, Optional
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from telethon import events
from telethon.sync import TelegramClient
from telethon.tl.custom.dialog import Dialog
from telethon.tl.types import Message

logger = logging.getLogger(__name__)


class TelegramManager:
    def __init__(self, api_id: int, api_hash: str, phone_number: str):
        self.client = TelegramClient('session', api_id, api_hash)
        self.phone_number = phone_number

    def connect(self) -> None:
        if not self.client.is_connected():
            logger.info("Connecting to Telegram...")
            self.client.connect()

        if not self.client.is_user_authorized():
            logger.info("Authorizing the client...")
            self.client.start(phone=self.phone_number)

    @staticmethod
    def _ensure_connected(method: Callable):
        def wrapper(self, *args, **kwargs):
            if not self.client.is_connected() or not self.client.is_user_authorized():
                self.connect()
            return method(self, *args, **kwargs)

        return wrapper

    @_ensure_connected
    def listen(self, chat_identifier: str, message_handler: Callable[[Message], None]) -> None:
        """Listen for new messages in a chat or channel."""
        chat_target = self._resolve_chat_identifier(chat_identifier)

        with self.client:
            @self.client.on(events.NewMessage(chats=chat_target))
            async def event_handler(event):
                try:
                    if event.message.text:
                        message_handler(event.message)
                except Exception as error:
                    logger.error(f"Error while handling message: {error}")

            logger.info(f"Listening for messages from {chat_target}...")
            self.client.run_until_disconnected()

    @_ensure_connected
    def fetch_messages(
            self, chat_identifier: str, message_processor: Optional[Callable[[Message], None]] = None,
            error_handler: Optional[Callable[[Message], None]] = None,
            min_id: Optional[int] = None
    ) -> Optional[list[Message]]:
        """Fetch message history from a chat or channel."""
        chat_target = self._resolve_chat_identifier(chat_identifier)
        with self.client:
            messages = self.client.iter_messages(chat_target, reverse=True, min_id=min_id or 0)
            if message_processor:
                for message in messages:
                    try:
                        message_processor(message)
                    except IntegrityError:
                        pass
                    except Exception as e:
                        if error_handler:
                            error_handler(message)
                        logger.error(e)
            else:
                return list(messages)

    @_ensure_connected
    def _get_chat_dialog(self, chat_name: str) -> Dialog:
        """Fetch a chat dialog by its name."""
        with self.client:
            try:
                return next(
                    dialog for dialog in self.client.iter_dialogs()
                    if chat_name.lower().strip() in dialog.name.lower().strip()
                )
            except StopIteration:
                raise ValueError(f"Chat '{chat_name}' not found")

    def _resolve_chat_identifier(self, identifier: str) -> str:
        """Resolve the chat identifier to a valid Telegram chat or channel."""
        if identifier.startswith("https://t.me/"):
            url = urlparse(identifier)
            return url.path.strip('/')
        elif identifier.startswith("@"):
            return identifier
        return self._get_chat_dialog(identifier).name
