import logging
from datetime import datetime, timezone
from typing import Callable, Optional, Union, Any
from urllib.parse import urlparse
from functools import wraps

from telethon import events
from telethon.sync import TelegramClient
from telethon.tl.custom.dialog import Dialog
from telethon.tl.types import Message
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError

logger = logging.getLogger(__name__)


class TelegramManager:
    def __init__(self, api_id: int, api_hash: str, phone_number: str):
        if not api_id or not api_hash or not phone_number:
            raise ValueError("API credentials and phone number are required")

        self.client = TelegramClient('session', api_id, api_hash)
        self.phone_number = phone_number
        self._connected = False

    def connect(self) -> None:
        """Connect and authorize the Telegram client."""
        try:
            if not self.client.is_connected():
                logger.info("Connecting to Telegram...")
                self.client.connect()

            if not self.client.is_user_authorized():
                logger.info("Authorizing the client...")
                self.client.start(phone=self.phone_number)

            self._connected = True

        except SessionPasswordNeededError:
            logger.error("Two-factor authentication is enabled. Please provide password.")
            raise
        except PhoneCodeInvalidError:
            logger.error("Invalid phone code provided.")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self.client.is_connected():
            self.client.disconnect()
            self._connected = False
            logger.info("Disconnected from Telegram")

    @staticmethod
    def _ensure_connected(method: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to ensure client is connected before method execution."""

        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self._connected or not self.client.is_connected() or not self.client.is_user_authorized():
                self.connect()
            return method(self, *args, **kwargs)

        return wrapper

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    @_ensure_connected
    def listen(self, chat_identifier: str, message_handler: Callable[[Message], None]) -> None:
        """Listen for new messages in a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = self._resolve_chat_identifier(chat_identifier)

        @self.client.on(events.NewMessage(chats=chat_target))
        async def event_handler(event):
            try:
                if event.message and event.message.text:
                    message_handler(event.message)
            except Exception as error:
                logger.error(f"Error while handling message: {error}")

        logger.info(f"Listening for messages from {chat_target}...")
        try:
            self.client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Stopping message listener...")
        except FloodWaitError as e:
            logger.warning(f"Rate limited. Waiting {e.seconds} seconds...")
            raise

    @_ensure_connected
    def fetch_messages(
            self,
            chat_identifier: str,
            message_processor: Optional[Callable[[Message], None]] = None,
            error_handler: Optional[Callable[[Message, Exception], None]] = None,
            min_id: Optional[int] = None,
            limit: Optional[int] = None,
            since_date: Optional[datetime] = None,
            search: Optional[str] = None,
    ) -> Optional[list[Message]]:
        """
        Fetch message history from a chat or channel.

        Supports filtering by min_id, date, limit, and search string.

        NOTE: Telegram ignores `min_id` and `offset_date` when `search` is used.
        This function performs post-filtering manually to support those.
        """
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = self._resolve_chat_identifier(chat_identifier)

        if search:
            logger.warning("Telegram ignores min_id and since_date when using search. Filtering manually...")

        try:
            messages_iter = self.client.iter_messages(
                chat_target,
                reverse=True,
                limit=limit,
                search=search,
                min_id=min_id or 0,
            )

            filtered = []
            for message in messages_iter:
                try:
                    # Manual post-filtering for search queries
                    if search:
                        if min_id and message.id <= min_id:
                            continue
                        if since_date and self._compare_dates(message.date, since_date) < 0:
                            continue

                    if message_processor:
                        message_processor(message)
                    else:
                        filtered.append(message)

                except Exception as e:
                    if error_handler:
                        error_handler(message, e)
                    else:
                        logger.error(f"Error processing message {message.id}: {e}")

            return filtered if not message_processor else None

        except FloodWaitError as e:
            logger.warning(f"Rate limited while fetching messages. Wait {e.seconds} seconds.")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch messages from {chat_target}: {e}")
            raise

    @_ensure_connected
    def _get_chat_dialog(self, chat_name: str) -> Dialog:
        """Fetch a chat dialog by its name."""
        if not chat_name:
            raise ValueError("Chat name cannot be empty")

        try:
            for dialog in self.client.iter_dialogs():
                if chat_name.lower().strip() in dialog.name.lower().strip():
                    return dialog
            raise ValueError(f"Chat '{chat_name}' not found")
        except Exception as e:
            logger.error(f"Failed to find chat '{chat_name}': {e}")
            raise

    def _resolve_chat_identifier(self, identifier: str) -> Union[str, int]:
        """Resolve the chat identifier to a valid Telegram chat or channel."""
        if not identifier:
            raise ValueError("Identifier cannot be empty")

        identifier = identifier.strip()

        # Handle t.me URLs
        if identifier.startswith("https://t.me/") or identifier.startswith("http://t.me/"):
            try:
                url = urlparse(identifier)
                path = url.path.strip('/')
                if not path:
                    raise ValueError("Invalid Telegram URL - no channel/chat specified")
                return f"@{path}" if not path.startswith('@') else path
            except Exception as e:
                logger.error(f"Failed to parse Telegram URL '{identifier}': {e}")
                raise ValueError(f"Invalid Telegram URL: {identifier}")

        # Handle @username format
        elif identifier.startswith("@"):
            return identifier

        # Handle numeric chat ID
        elif identifier.lstrip('-').isdigit():
            return int(identifier)

        # Handle chat name - resolve to dialog
        else:
            try:
                dialog = self._get_chat_dialog(identifier)
                return dialog.entity
            except ValueError:
                # If not found as dialog name, try as username
                return f"@{identifier}"

    @staticmethod
    def _compare_dates(message_date: datetime, since_date: datetime) -> int:
        """
        Compare two datetime objects, handling timezone awareness.

        Returns:
            -1 if message_date < since_date
             0 if message_date == since_date
             1 if message_date > since_date
        """
        # Telegram message dates are always UTC
        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)

        # Handle since_date timezone
        if since_date.tzinfo is None:
            # Assume naive datetime is in UTC for consistency
            since_date = since_date.replace(tzinfo=timezone.utc)
            logger.warning("since_date is timezone-naive, assuming UTC")

        # Convert both to UTC for comparison
        message_utc = message_date.astimezone(timezone.utc)
        since_utc = since_date.astimezone(timezone.utc)

        if message_utc < since_utc:
            return -1
        elif message_utc > since_utc:
            return 1
        else:
            return 0