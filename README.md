# TelegramManager

A Python CLI tool and module for fetching and monitoring Telegram messages from public channels and groups. Built with Telethon for reliable Telegram API integration.

## Installation

Install TelegramManager using pip:

```bash
pip install .
```

For development installation:

```bash
pip install -e .[dev]
```

## Configuration

### Environment Configuration

Create a `.env` file in your project root directory:

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
```

The default `TelegramManager()` constructor automatically loads these environment variables.

### Manual Configuration

For programmatic usage without environment files:

```python
from telegram_manager.controller import TelegramManager

tg = TelegramManager(
    api_id=123456,
    api_hash="your_api_hash_here",
    phone_number="+1234567890"
)
```

## Command Line Interface

The `tm` command provides two primary operations:

### Fetch Messages

Retrieve historical messages from a channel or group:

```bash
tm fetch <channel> [--min-id <id>] [--limit <n>] [--since <relative-time>] [--verbose]
```

Supported `--since` formats:

* mo : months (e.g. `1mo`)
* w  : weeks  (e.g. `2w`)
* d  : days   (e.g. `3d`)
* h  : hours  (e.g. `4h`)
* m  : minutes (e.g. `30m`)

You can combine multiple units:

```bash
tm fetch @openai --since "1mo 2w 3d 4h 30m" --verbose
```

### Listen for Messages

Monitor channels for new messages in real-time:

```bash
tm listen <channel>
```

Example:

```bash
tm listen "Some Group Chat"
```

## Verbose Mode

When `--verbose` is enabled in `fetch`, additional message details are printed:

* ID, date (local + UTC), sender, type, reply info
* Message text
* Summary: total messages, user count, message types

## Python API

### Basic Usage

```python
from telegram_manager import TelegramManager

tg = TelegramManager()
```

### Fetching Messages

```python
tg.fetch_messages(
    chat_identifier="@somechannel",
    message_processor=lambda m: print(m.id, m.raw_text),
    limit=5
)
```

### Real-time Message Monitoring

```python
tg.listen("@somechannel", message_handler=lambda m: print(f"New: {m.message}"))
```

## Supported Input Formats

TelegramManager accepts multiple channel identifier formats:

* Telegram URLs: `https://t.me/channelname`
* Username format: `@channelname`
* Dialog names: `"Channel Display Name"`

## Authentication

* Session files are created locally to maintain authentication across sessions
* First-time usage requires verification code entry
* Authentication state persists between program runs

## Requirements

* Python 3.7 or higher
* Valid Telegram API credentials
* Network connectivity for Telegram API access
