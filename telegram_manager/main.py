import logging
from typing import Callable

import click
from telethon.tl.types import Message

from telegram_manager import TelegramManager

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Telegram CLI utility."""
    pass


@cli.command()
@click.argument(
    'channel',
    metavar='<channel>',
    required=True,
    type=str
)
@click.option(
    '--min-id',
    type=int,
    default=None,
    help="Minimum Telegram message ID to start fetching from (messages with smaller IDs will be skipped)."
)
def iterate(channel, min_id):
    """
    Fetch historical messages from a Telegram chat or channel.

    CHANNEL can be:
    - A full URL like 'https://t.me/example'
    - A username like '@example'
    - A plain chat name that matches an existing dialog

    This uses the _resolve_chat_identifier method internally.
    """
    tg = TelegramManager()

    def message_processor(msg: Message):
        print(f"Message ID: {msg.id}, Content: {msg.message}")

    def error_handler(msg: Message):
        print(f"Error processing message ID: {msg.id}")

    tg.fetch_messages(
        chat_identifier=channel,
        message_processor=message_processor,
        error_handler=error_handler,
        min_id=min_id
    )


@cli.command()
@click.argument(
    'channel',
    metavar='<channel>',
    required=True,
    type=str
)
def listen(channel):
    """
    Listen for new messages in a Telegram chat or channel.

    CHANNEL can be:
    - A full URL like 'https://t.me/example'
    - A username like '@example'
    - A plain chat name that matches an existing dialog

    This uses the _resolve_chat_identifier method internally.
    """
    tg = TelegramManager()

    def on_message(msg: Message):
        print(f"New message: {msg.message}")

    tg.listen(channel, message_handler=on_message)


if __name__ == "__main__":
    cli()
