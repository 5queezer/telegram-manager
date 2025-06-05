# TelegramManager

A Python CLI tool and module for fetching and monitoring Telegram messages from public channels and groups. Built with Telethon for reliable Telegram API integration. Supports both synchronous and asynchronous operations.

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

The default `TelegramManager()` and `AsyncTelegramManager()` constructors automatically load these environment variables.

### Manual Configuration

For programmatic usage without environment files:

```python
from telegram_manager.controller import TelegramManager, AsyncTelegramManager

# Synchronous version
tg = TelegramManager(
    api_id=123456,
    api_hash="your_api_hash_here",
    phone_number="+1234567890"
)

# Asynchronous version
async_tg = AsyncTelegramManager(
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
tm fetch <channel> [--min-id <id>] [--limit <n>] [--since <relative-time>] [--search <text>] [--json] [--verbose]
```

**Options:**

* `--min-id`: Minimum message ID to fetch from.
* `--limit`: Maximum number of messages to retrieve.
* `--since`: Filter messages newer than a relative time expression.
* `--search`: Filter messages containing the given search string.
* `--json`: Output each message in JSON format.
* `--verbose`: Print detailed metadata per message.

**Supported `--since` formats:**

* `mo`: months (e.g. `1mo`)
* `w`: weeks (e.g. `2w`)
* `d`: days (e.g. `3d`)
* `h`: hours (e.g. `4h`)
* `m`: minutes (e.g. `30m`)

You can combine units:

```bash
tm fetch @openai --since "1mo 2w 3d 4h 30m" --search GPT --verbose
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

When `--verbose` is enabled in `fetch`, each message will include:

* Message ID
* Date in local time and UTC
* Sender username and ID
* Message type (text, photo, document, video)
* Reply-to message ID (if any)
* Raw text content

A final summary is also printed, including:

* Total messages
* Unique user count
* Breakdown by media type
* Minimum message ID fetched

## JSON Output

Use `--json` to emit each message as a structured JSON object. This is useful for piping into other programs or saving to file.

## Python API

TelegramManager provides both synchronous and asynchronous APIs. Choose the one that best fits your application's architecture.

### Synchronous API

The synchronous API is simpler and suitable for most use cases, especially scripts and applications that don't require concurrent operations.

#### Basic Usage

```python
from telegram_manager import TelegramManager

# Using environment variables
tg = TelegramManager()

# Or with explicit credentials
tg = TelegramManager(
    api_id=12345,
    api_hash="your_api_hash",
    phone_number="+1234567890"
)
```

#### Context Manager Usage

```python
with TelegramManager() as tg:
    # Fetch messages
    messages = tg.fetch_messages("@channel_name", limit=10)
    
    # Send message
    tg.send_message("@username", "Hello!")
    
    # Get chat info
    info = tg.get_chat_info("@channel_name")
```

#### Fetching Messages

```python
# Basic message fetching
messages = tg.fetch_messages("@somechannel", limit=5)

# With custom message processor
def process_message(message):
    print(f"ID: {message.id}, Text: {message.raw_text}")

tg.fetch_messages(
    chat_identifier="@somechannel",
    message_processor=process_message,
    limit=10
)

# With filtering options
messages = tg.fetch_messages(
    "@channel",
    limit=100,
    min_id=12345,
    search_text="important"
)
```

#### Real-time Message Monitoring

```python
def handle_new_message(message):
    print(f"New message: {message.message}")

tg.listen("@somechannel", message_handler=handle_new_message)
```

### Asynchronous API

The asynchronous API is ideal for applications that need to handle multiple operations concurrently or integrate with async frameworks like FastAPI, aiohttp, or Discord.py.

#### Basic Usage

```python
import asyncio
from telegram_manager import AsyncTelegramManager

async def main():
    # Using environment variables
    async_tg = AsyncTelegramManager()
    
    # Or with explicit credentials
    async_tg = AsyncTelegramManager(
        api_id=12345,
        api_hash="your_api_hash",
        phone_number="+1234567890"
    )

# Run the async function
asyncio.run(main())
```

#### Context Manager Usage

```python
async def main():
    async with AsyncTelegramManager() as tg:
        # Fetch messages
        messages = await tg.fetch_messages("@channel_name", limit=10)
        
        # Send message
        await tg.send_message("@username", "Hello from async!")
        
        # Get chat info
        info = await tg.get_chat_info("@channel_name")
        print(f"Chat info: {info}")

asyncio.run(main())
```

#### Fetching Messages Asynchronously

```python
async def fetch_example():
    async with AsyncTelegramManager() as tg:
        # Basic message fetching
        messages = await tg.fetch_messages("@somechannel", limit=5)
        
        # With custom message processor
        async def process_message(message):
            print(f"ID: {message.id}, Text: {message.raw_text}")
            # Can perform async operations here
            await some_async_operation(message)
        
        await tg.fetch_messages(
            chat_identifier="@somechannel",
            message_processor=process_message,
            limit=10
        )

asyncio.run(fetch_example())
```

#### Concurrent Operations

```python
async def concurrent_example():
    async with AsyncTelegramManager() as tg:
        # Fetch from multiple channels concurrently
        tasks = [
            tg.fetch_messages("@channel1", limit=10),
            tg.fetch_messages("@channel2", limit=10),
            tg.fetch_messages("@channel3", limit=10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        for i, messages in enumerate(results, 1):
            print(f"Channel {i} has {len(messages)} messages")

asyncio.run(concurrent_example())
```

#### Real-time Message Monitoring (Async)

```python
async def handle_new_message(message):
    print(f"New async message: {message.message}")
    # Can perform async operations
    await process_message_async(message)

async def listen_example():
    async with AsyncTelegramManager() as tg:
        await tg.listen("@somechannel", message_handler=handle_new_message)

asyncio.run(listen_example())
```

#### Integration with Web Frameworks

```python
# FastAPI example
from fastapi import FastAPI
from telegram_manager import AsyncTelegramManager

app = FastAPI()
tg = AsyncTelegramManager()

@app.on_event("startup")
async def startup():
    await tg.start()

@app.on_event("shutdown")
async def shutdown():
    await tg.disconnect()

@app.get("/messages/{channel}")
async def get_messages(channel: str, limit: int = 10):
    messages = await tg.fetch_messages(f"@{channel}", limit=limit)
    return {"messages": [msg.raw_text for msg in messages]}

@app.post("/send/{channel}")
async def send_message(channel: str, message: str):
    await tg.send_message(f"@{channel}", message)
    return {"status": "sent"}
```

### Complete Usage Examples

#### Synchronous Example

```python
def sync_example():
    """Example of synchronous usage."""
    manager = TelegramManager(
        api_id=12345,
        api_hash="your_api_hash",
        phone_number="+1234567890"
    )

    with manager:
        # Fetch messages
        messages = manager.fetch_messages("@channel_name", limit=10)
        print(f"Fetched {len(messages)} messages")

        # Send message
        manager.send_message("@username", "Hello from sync!")

        # Get chat info
        info = manager.get_chat_info("@channel_name")
        print(f"Chat info: {info}")

        # Listen for new messages (blocks)
        def message_handler(msg):
            print(f"New: {msg.raw_text}")
        
        manager.listen("@channel_name", message_handler=message_handler)
```

#### Asynchronous Example

```python
async def async_example():
    """Example of asynchronous usage."""
    manager = AsyncTelegramManager(
        api_id=12345,
        api_hash="your_api_hash",
        phone_number="+1234567890"
    )

    async with manager:
        # Fetch messages
        messages = await manager.fetch_messages("@channel_name", limit=10)
        print(f"Fetched {len(messages)} messages")

        # Send message
        await manager.send_message("@username", "Hello from async!")

        # Get chat info
        info = await manager.get_chat_info("@channel_name")
        print(f"Chat info: {info}")

        # Listen for new messages (non-blocking with other async operations)
        async def message_handler(msg):
            print(f"New: {msg.raw_text}")
            await some_async_processing(msg)
        
        # Can run concurrently with other async operations
        listen_task = asyncio.create_task(
            manager.listen("@channel_name", message_handler=message_handler)
        )
        
        # Do other async work while listening
        await other_async_operations()
        
        # Cancel listening when done
        listen_task.cancel()

# Run the async example
asyncio.run(async_example())
```

## API Comparison

| Feature | Synchronous API | Asynchronous API |
|---------|----------------|------------------|
| **Context Manager** | `with TelegramManager():` | `async with AsyncTelegramManager():` |
| **Fetch Messages** | `messages = tg.fetch_messages()` | `messages = await tg.fetch_messages()` |
| **Send Message** | `tg.send_message()` | `await tg.send_message()` |
| **Listen** | `tg.listen()` (blocks) | `await tg.listen()` (non-blocking) |
| **Concurrency** | Sequential operations | Concurrent operations with `asyncio.gather()` |
| **Integration** | Simple scripts, CLI tools | Web frameworks, concurrent applications |

## When to Use Which API

**Use Synchronous API when:**
- Building simple scripts or CLI tools
- Operations are naturally sequential
- You don't need concurrent Telegram operations
- Working with sync-only libraries

**Use Asynchronous API when:**
- Building web applications (FastAPI, aiohttp)
- Need to handle multiple channels concurrently
- Integrating with other async libraries
- Building real-time applications
- Performance and concurrency are important

## Supported Input Formats

TelegramManager accepts multiple channel identifier formats:

* Telegram URLs: `https://t.me/channelname`
* Username format: `@channelname`
* Dialog names: `"Channel Display Name"`

## Authentication

* Session files are created locally to maintain authentication across sessions
* First-time usage requires verification code entry
* Authentication state persists between program runs
* Both sync and async APIs share the same session management

## Requirements

* Python 3.7 or higher
* Valid Telegram API credentials
* Network connectivity for Telegram API access
* For async usage: Basic understanding of Python asyncio