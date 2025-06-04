import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

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


def classify_media_type(msg: Message) -> str:
    if msg.photo:
        return 'Photo'
    elif msg.document:
        return 'Document'
    elif msg.video:
        return 'Video'
    elif msg.raw_text:
        return 'Text'
    return 'Other'


def format_message_verbose(msg: Message):
    local_date = msg.date.astimezone().strftime('%Y-%m-%d %H:%M:%S')
    utc_date = msg.date.strftime('%Y-%m-%d %H:%M:%S')
    sender = getattr(msg.sender, 'username', 'Unknown')
    sender_id = getattr(msg.sender, 'id', 'N/A')
    reply_to = getattr(msg, 'reply_to_msg_id', None)
    media_type = classify_media_type(msg)

    print()
    print(f"\033[90mID:       \033[0m {msg.id}")
    print(f"\033[90mDate:     \033[0m {local_date} (local) | {utc_date} UTC")
    print(f"\033[90mFrom:     \033[0m @{sender} (ID: {sender_id})")
    print(f"\033[90mType:     \033[0m {media_type}")
    if reply_to:
        print(f"\033[90mReply to: \033[0m {reply_to}")
    print(f"\033[90mText:     \033[0m {msg.raw_text}")


def format_message_json(msg: Message) -> str:
    return json.dumps({
        "id": msg.id,
        "date_utc": msg.date.isoformat(),
        "text": msg.raw_text,
        "from_username": getattr(msg.sender, 'username', 'Unknown'),
        "from_id": getattr(msg.sender, 'id', None),
        "reply_to_msg_id": getattr(msg, 'reply_to_msg_id', None),
        "media_type": classify_media_type(msg)
    }, ensure_ascii=False)


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
@click.option('--json', 'json_output', is_flag=True, default=False, help="Output messages as JSON.")
@click.option('--search', type=str, default=None, help="Search string to filter messages containing specific text.")
def fetch(channel, min_id, limit, since, verbose, json_output, search):
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
    found_min_id: List[Optional[int]] = [None]
    message_count = 0
    user_ids = set()
    type_counter = {"Text": 0, "Photo": 0, "Document": 0, "Video": 0, "Other": 0}

    def message_processor(msg: Message):
        nonlocal message_count
        message_count += 1
        user_ids.add(getattr(msg.sender, 'id', 'N/A'))

        media_type = classify_media_type(msg)
        type_counter[media_type] += 1

        if json_output:
            print(format_message_json(msg))
        elif verbose:
            format_message_verbose(msg)
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
        search=search
    )

    if verbose:
        print("\n\033[1mSummary\033[0m")
        if since_date:
            print(f"\033[90mSince:       \033[0m {since_date.astimezone().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\033[90mMessages:    \033[0m {message_count}")
        print(f"\033[90mUsers:       \033[0m {len(user_ids)}")
        print(f"\033[90mTypes:       \033[0m Text({type_counter['Text']}), "
              f"Photo({type_counter['Photo']}), Doc({type_counter['Document']}), "
              f"Video({type_counter['Video']}), Other({type_counter['Other']})")
        if found_min_id[0] is not None:
            print(f"\033[90mMin Msg ID:  \033[0m {found_min_id[0]}")


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
