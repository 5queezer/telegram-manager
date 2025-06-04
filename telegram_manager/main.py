import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List

import click
from dateutil.relativedelta import relativedelta
from telethon.tl.types import Message

from telegram_manager import TelegramManager

logger = logging.getLogger(__name__)


def parse_relative_time_string(time_str: str) -> datetime:
    pattern = re.findall(r'(\d+)\s*(mo|w|d|h|m)', time_str.lower())
    now = datetime.now(timezone.utc)

    for value, unit in pattern:
        value = int(value)
        if unit == 'mo':
            now -= relativedelta(months=value)
        elif unit == 'w':
            now -= timedelta(weeks=value)
        elif unit == 'd':
            now -= timedelta(days=value)
        elif unit == 'h':
            now -= timedelta(hours=value)
        elif unit == 'm':
            now -= timedelta(minutes=value)

    return now


@click.group()
def cli():
    """Telegram CLI utility."""
    pass


@cli.command()
@click.argument('channel', metavar='<channel>', required=True, type=str)
@click.option('--min-id', type=int, default=None, help="Minimum Telegram message ID to fetch from.")
@click.option('--limit', type=int, default=None, help="Fetch the last N messages.")
@click.option('--since', type=str, default=None, help="Fetch messages sent after a relative time like '1w 2d 30m'.")
@click.option('--verbose', is_flag=True, default=False, help="Verbose output")
def fetch(channel, min_id, limit, since, verbose):
    """
    Fetch historical messages from a Telegram chat or channel.

    CHANNEL can be:
    - A full URL like 'https://t.me/example'
    - A username like '@example'
    - A plain chat name that matches an existing dialog

    Options:
    --since <relative-time>:
        Filter messages sent after a relative time expression.
        Format supports combinations of:
            - mo : months (e.g. '1mo' for one month)
            - w  : weeks  (e.g. '2w'  for two weeks)
            - d  : days   (e.g. '3d'  for three days)
            - h  : hours  (e.g. '4h'  for four hours)
            - m  : minutes (e.g. '30m' for thirty minutes)

        Example:
            --since "1mo 2w 3d 4h 30m"
    """
    try:
        since_date = parse_relative_time_string(since) if since else None
    except Exception as e:
        raise click.BadParameter(f"Invalid --since value: {since}\n{e}")

    tg = TelegramManager()
    found_min_id: List[None | int] = [None]

    def message_processor(msg: Message):
        if verbose:
            print(
                f"\033[90mID:\033[0m {msg.id}  \033[90mDate:\033[0m {msg.date.astimezone().strftime('%Y-%m-%d %H:%M')}  "
                f"\033[90mFrom:\033[0m @{getattr(msg.sender, 'username', 'Unknown')}  "
                f"\033[90mText:\033[0m {msg.raw_text}")
        else:
            print(msg.message)

        if found_min_id[0] is None or msg.id < found_min_id[0]:
            found_min_id[0] = msg.id

    def error_handler(msg: Message):
        print(f"Error processing message ID: {msg.id}")

    tg.fetch_messages(
        chat_identifier=channel,
        message_processor=message_processor,
        error_handler=error_handler,
        min_id=min_id,
        limit=limit,
        since_date=since_date,
    )

    if since and verbose:
        print(f"\n\033[90mFetched messages since {since_date.astimezone().strftime('%Y-%m-%d %H:%M:%S')} (min_id: {found_min_id[0]})\033[0m")


@cli.command()
@click.argument('channel', metavar='<channel>', required=True, type=str)
def listen(channel):
    """
    Listen for new messages in a Telegram chat or channel.

    CHANNEL can be:
    - A full URL like 'https://t.me/example'
    - A username like '@example'
    - A plain chat name that matches an existing dialog
    """
    tg = TelegramManager()

    def on_message(msg: Message):
        print(f"New message: {msg.message}")

    tg.listen(channel, message_handler=on_message)


if __name__ == "__main__":
    cli()
