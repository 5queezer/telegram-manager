import logging
import asyncio
import threading
from datetime import datetime, timezone
from typing import Callable, Optional, Union, Any, List, Coroutine
from urllib.parse import urlparse
from functools import wraps
from abc import ABC, abstractmethod

from telethon import events
from telethon import TelegramClient
from telethon.sync import TelegramClient as SyncTelegramClient
from telethon.tl.custom.dialog import Dialog
from telethon.tl.types import Message, User, Chat, Channel
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError

logger = logging.getLogger(__name__)


class BaseTelegramManager(ABC):
    """Base class containing shared logic for both sync and async implementations."""

    def __init__(self, api_id: int, api_hash: str, phone_number: str, session_name: str = 'session'):
        if not api_id or not api_hash or not phone_number:
            raise ValueError("API credentials and phone number are required")

        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_name = session_name
        self._connected = False

    @staticmethod
    def _resolve_chat_identifier_sync(identifier: str) -> Union[str, int]:
        """Resolve the chat identifier to a valid Telegram chat or channel (sync logic only)."""
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

                # Handle invite links (URLs with + in them)
                if path.startswith('+'):
                    # Return the full URL for invite links - they need to be resolved differently
                    return identifier

                # Handle regular username URLs
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

        # Handle chat name - this requires client interaction, handled in subclasses
        else:
            return identifier  # Will be resolved by subclass methods

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

    def _should_include_message(self, message: Message, min_id: Optional[int], since_date: Optional[datetime],
                                search: Optional[str]) -> bool:
        """Check if message should be included based on filters."""
        if search:
            if min_id and message.id <= min_id:
                return False
            if since_date and self._compare_dates(message.date, since_date) < 0:
                return False
        return True

    @abstractmethod
    def connect(self):
        """Connect and authorize the Telegram client."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from Telegram."""
        pass


class TelegramManager(BaseTelegramManager):
    """Synchronous Telegram client manager."""

    def __init__(self, api_id: int, api_hash: str, phone_number: str, session_name: str = 'session'):
        super().__init__(api_id, api_hash, phone_number, session_name)
        self.client = SyncTelegramClient(self.session_name, api_id, api_hash)
        self._lock = threading.Lock()

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
            with self._lock:
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

    def _resolve_chat_identifier(self, identifier: str) -> str | Coroutine[
        Any, Any, User | Chat | Channel | list[User | Chat | Channel]] | int | Any:
        """Resolve the chat identifier to a valid Telegram chat or channel."""
        base_result = self._resolve_chat_identifier_sync(identifier)

        # Handle invite links - they need to be joined first
        if isinstance(base_result, str) and base_result.startswith(('https://t.me/', 'http://t.me/')):
            url = urlparse(base_result)
            path = url.path.strip('/')
            if path.startswith('+'):
                try:
                    # For invite links, try to join the chat first
                    chat = self.client.get_entity(base_result)
                    return chat
                except Exception as e:
                    logger.error(f"Failed to resolve invite link '{base_result}': {e}")
                    raise ValueError(
                        f"Cannot access invite link '{base_result}'. You may need to join the chat first manually.")

        # If it's not a simple identifier, try to resolve as chat name
        if isinstance(base_result, str) and not base_result.startswith('@') and not base_result.lstrip('-').isdigit():
            try:
                dialog = self._get_chat_dialog(base_result)
                return dialog.entity
            except ValueError:
                # If not found as dialog name, try as username
                return f"@{base_result}"

        return base_result

    @_ensure_connected
    def listen(self, chat_identifier: str, message_handler: Callable[[Message], None]) -> None:
        """Listen for new messages from a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = self._resolve_chat_identifier(chat_identifier)

        def handler(event):
            try:
                if event.message and event.message.text:
                    # Safely call the message handler
                    try:
                        result = message_handler(event.message)
                        # In sync version, we don't need to await anything
                        # Just ensure the handler is called properly
                    except Exception as handler_error:
                        logger.error(f"Error in message handler: {handler_error}")
            except Exception as error:
                logger.error(f"Error while handling message: {error}")

        self.client.add_event_handler(handler, events.NewMessage(chats=chat_target))

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
    ) -> Optional[List[Message]]:
        """Fetch message history from a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = self._resolve_chat_identifier(chat_identifier)

        if search and (min_id is not None or since_date is not None):
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
                    if not self._should_include_message(message, min_id, since_date, search):
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
    def send_message(self, chat_identifier: str, message: str) -> Coroutine[Any, Any, Message]:
        """Send a message to a chat or channel."""
        if not chat_identifier or not message:
            raise ValueError("Chat identifier and message cannot be empty")

        chat_target = self._resolve_chat_identifier(chat_identifier)

        try:
            return self.client.send_message(chat_target, message)
        except Exception as e:
            logger.error(f"Failed to send message to {chat_target}: {e}")
            raise

    @_ensure_connected
    def get_chat_info(self, chat_identifier: str) -> dict:
        """Get basic information about a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = self._resolve_chat_identifier(chat_identifier)

        try:
            entity = self.client.get_entity(chat_target)
            return {
                'id': getattr(entity, 'id', None),
                'title': getattr(entity, 'title', None),
                'username': getattr(entity, 'username', None),
                'type': type(entity).__name__,
                'participants_count': getattr(entity, 'participants_count', None)
            }
        except Exception as e:
            logger.error(f"Failed to get chat info for {chat_target}: {e}")
            raise

    @_ensure_connected
    def download_media(self, message: Message, file_path: Optional[str] = None) -> Coroutine[
                                                                                       Any, Any, str | bytes | None] | None:
        """Download media from a message."""
        if not message.media:
            logger.warning("Message has no media to download")
            return None

        try:
            return self.client.download_media(message, file=file_path)
        except Exception as e:
            logger.error(f"Failed to download media from message {message.id}: {e}")
            raise


class AsyncTelegramManager(BaseTelegramManager):
    """Asynchronous Telegram client manager."""

    def __init__(self, api_id: int, api_hash: str, phone_number: str, session_name: str = 'async_session'):
        super().__init__(api_id, api_hash, phone_number, session_name)
        self.client = TelegramClient(self.session_name, api_id, api_hash)
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect and authorize the Telegram client."""
        try:
            if not self.client.is_connected():
                logger.info("Connecting to Telegram...")
                await self.client.connect()

            if not await self.client.is_user_authorized():
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

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self.client.is_connected():
            await self.client.disconnect()
            self._connected = False
            logger.info("Disconnected from Telegram")

    @staticmethod
    def _ensure_connected(method: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to ensure client is connected before method execution."""

        @wraps(method)
        async def wrapper(self, *args, **kwargs):
            async with self._lock:
                if not self._connected or not self.client.is_connected() or not await self.client.is_user_authorized():
                    await self.connect()
                return await method(self, *args, **kwargs)

        return wrapper

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    @_ensure_connected
    async def _get_chat_dialog(self, chat_name: str) -> Dialog:
        """Fetch a chat dialog by its name."""
        if not chat_name:
            raise ValueError("Chat name cannot be empty")

        try:
            async for dialog in self.client.iter_dialogs():
                if chat_name.lower().strip() in dialog.name.lower().strip():
                    return dialog
            raise ValueError(f"Chat '{chat_name}' not found")
        except Exception as e:
            logger.error(f"Failed to find chat '{chat_name}': {e}")
            raise

    async def _resolve_chat_identifier(self, identifier: str) -> str | User | Chat | Channel | list[
        User | Chat | Channel] | int | Any:
        """Resolve the chat identifier to a valid Telegram chat or channel."""
        base_result = self._resolve_chat_identifier_sync(identifier)

        # Handle invite links - they need to be joined first
        if isinstance(base_result, str) and base_result.startswith(('https://t.me/', 'http://t.me/')):
            url = urlparse(base_result)
            path = url.path.strip('/')
            if path.startswith('+'):
                try:
                    # For invite links, try to join the chat first
                    chat = await self.client.get_entity(base_result)
                    return chat
                except Exception as e:
                    logger.error(f"Failed to resolve invite link '{base_result}': {e}")
                    raise ValueError(
                        f"Cannot access invite link '{base_result}'. You may need to join the chat first manually.")

        # If it's not a simple identifier, try to resolve as chat name
        if isinstance(base_result, str) and not base_result.startswith('@') and not base_result.lstrip('-').isdigit():
            try:
                dialog = await self._get_chat_dialog(base_result)
                return dialog.entity
            except ValueError:
                # If not found as dialog name, try as username
                return f"@{base_result}"

        return base_result

    @_ensure_connected
    async def listen(self, chat_identifier: str, message_handler: Callable[[Message], Union[None, Any]]) -> None:
        """Listen for new messages from a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = await self._resolve_chat_identifier(chat_identifier)

        async def handler(event):
            try:
                if event.message and event.message.text:
                    try:
                        result = message_handler(event.message)
                        # Only await if result is actually a coroutine
                        if asyncio.iscoroutine(result):
                            await result
                        # If result is None or any other value, just continue
                    except Exception as handler_error:
                        logger.error(f"Error in message handler: {handler_error}")
            except Exception as error:
                logger.error(f"Error while handling message: {error}")

        self.client.add_event_handler(handler, events.NewMessage(chats=chat_target))

        logger.info(f"Listening for messages from {chat_target}...")
        try:
            await self.client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Stopping message listener...")
        except FloodWaitError as e:
            logger.warning(f"Rate limited. Waiting {e.seconds} seconds...")
            raise

    @_ensure_connected
    async def fetch_messages(
            self,
            chat_identifier: str,
            message_processor: Optional[Callable[[Message], Union[None, Any]]] = None,
            error_handler: Optional[Callable[[Message, Exception], Union[None, Any]]] = None,
            min_id: Optional[int] = None,
            limit: Optional[int] = None,
            since_date: Optional[datetime] = None,
            search: Optional[str] = None,
    ) -> Optional[List[Message]]:
        """Fetch message history from a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = await self._resolve_chat_identifier(chat_identifier)

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
            async for message in messages_iter:
                try:
                    # Manual post-filtering for search queries
                    if not self._should_include_message(message, min_id, since_date, search):
                        continue

                    if message_processor:
                        try:
                            result = message_processor(message)
                            # Only await if result is actually a coroutine
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as processor_error:
                            logger.error(f"Error in message processor: {processor_error}")
                    else:
                        filtered.append(message)

                except Exception as e:
                    if error_handler:
                        try:
                            result = error_handler(message, e)
                            # Only await if result is actually a coroutine
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as handler_error:
                            logger.error(f"Error in error handler: {handler_error}")
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
    async def send_message(self, chat_identifier: str, message: str) -> Message:
        """Send a message to a chat or channel."""
        if not chat_identifier or not message:
            raise ValueError("Chat identifier and message cannot be empty")

        chat_target = await self._resolve_chat_identifier(chat_identifier)

        try:
            return await self.client.send_message(chat_target, message)
        except Exception as e:
            logger.error(f"Failed to send message to {chat_target}: {e}")
            raise

    @_ensure_connected
    async def get_chat_info(self, chat_identifier: str) -> dict:
        """Get basic information about a chat or channel."""
        if not chat_identifier:
            raise ValueError("Chat identifier cannot be empty")

        chat_target = await self._resolve_chat_identifier(chat_identifier)

        try:
            entity = await self.client.get_entity(chat_target)
            return {
                'id': entity.id,
                'title': getattr(entity, 'title', None),
                'username': getattr(entity, 'username', None),
                'type': type(entity).__name__,
                'participants_count': getattr(entity, 'participants_count', None)
            }
        except Exception as e:
            logger.error(f"Failed to get chat info for {chat_target}: {e}")
            raise

    @_ensure_connected
    async def download_media(self, message: Message, file_path: Optional[str] = None) -> Optional[str]:
        """Download media from a message."""
        if not message.media:
            logger.warning("Message has no media to download")
            return None

        try:
            return await self.client.download_media(message, file=file_path)
        except Exception as e:
            logger.error(f"Failed to download media from message {message.id}: {e}")
            raise