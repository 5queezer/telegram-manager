# TelegramManager

A simple CLI and Python module to **fetch** or **listen** to Telegram messages from public channels or groups. Built with [Telethon](https://github.com/LonamiWebs/Telethon), with plug-and-play configuration support.

---

## 📦 Installation

```bash
pip install .
# or for development
pip install -e .[dev]
```

---

## ⚙️ Configuration (Recommended)

Create a `.env` file in your project root:

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
```

The default `TelegramManager()` uses this automatically via a `Config` wrapper.

---

## 🔐 Manual Credential Usage (Alternative)

If you prefer not to use a `.env` file or `Config`, instantiate the class manually:

```python
from telegram_manager.controller import TelegramManager

tg = TelegramManager(
    api_id=123456,
    api_hash="your_api_hash_here",
    phone_number="+1234567890"
)
```

This is useful for scripting, testing, or dynamic environments.

---

## 🚀 CLI Usage

Once installed, you can run the `tm` CLI command:

### 🔍 Fetch Messages

```bash
tm fetch <channel> [--min-id <id>] [--limit <n>]
```

Example:

```bash
tm fetch @openai --limit 10
```

---

### 👂 Listen for Messages

```bash
tm listen <channel>
```

Example:

```bash
tm listen "Some Group Chat"
```

---

## 🧩 Python Module Usage

### 🔧 Initialization

```python
from telegram_manager import TelegramManager

tg = TelegramManager()  # Uses .env Config automatically
```

Or manually, as described in the previous section.

---

### 📥 Fetch Messages

```python
tg.fetch_messages(
    chat_identifier="@somechannel",
    message_processor=lambda m: print(m.id, m.text),
    limit=5
)
```

---

### 📡 Listen for Live Messages

```python
tg.listen("@somechannel", message_handler=lambda m: print(f"New: {m.message}"))
```

---

## 📝 Notes

* Accepts URLs (`https://t.me/...`), usernames (`@...`), or dialog names.
* A `session` file is created locally to persist login across runs.
* First-time authentication may prompt for a verification code.

---

## 👤 Author

Christian Pojoni
📧 [christian.pojoni@gmail.com](mailto:christian.pojoni@gmail.com)

---

## 📄 License

MIT
