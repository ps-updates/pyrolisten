# pyrolisten

[![PyPI version](https://img.shields.io/pypi/v/pyrolisten.svg)](https://pypi.org/project/pyrolisten/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyrolisten.svg)](https://pypi.org/project/pyrolisten/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

`pyromod`-style `listen()`, `ask()`, and `cancel_listener()` for **Pyrogram, Kurigram, and other Pyrogram forks** — without overriding methods your library already provides.

## Features

- **`client.listen()` & `client.ask()`** for waiting on messages and inline button clicks (`listener_type="callback_query"`).
- **Chat & User shortcuts:** `message.chat.ask(...)`, `message.chat.listen(...)`, `message.from_user.ask(...)`, and `message.from_user.listen(...)`.
- **Flexible targeting:** Pass a numeric ID, `@username`, or a list of IDs/`@username`s to `chat_id` and `user_id`.
- **Fork-safe:** Never overwrites `listen`, `ask`, or `cancel_listener` if your installed fork already defines them.
- **Zero runtime dependencies:** Works alongside whichever `pyrogram`-compatible package you already have installed.

## Installation

```bash
pip install pyrolisten
```

`pyrolisten` does not force a Pyrogram dependency because forks share the `pyrogram` module name and installing two in the same environment conflicts. If you don't have one installed yet, pick **one** extra:

```bash
pip install "pyrolisten[kurigram]"
# or
pip install "pyrolisten[pyrogram]"
```

## Quick Start

Import `pyrolisten.listen` (or `import pyrolisten`) **once at startup** before loading your handlers:

```python
import pyrolisten.listen
from pyrogram import Client, filters
from pyrogram.errors import ListenerTimeout, ListenerCanceled

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
app.listener_timeout = 30  # optional default timeout in seconds (default: 60)

@app.on_message(filters.command("name"))
async def ask_name(client, message):
    try:
        reply = await message.chat.ask(
            "What's your name?",
            user_id=message.from_user.id,
        )
        await reply.reply(f"Hi {reply.text}!")
    except ListenerTimeout:
        await message.reply("Too slow!")
    except ListenerCanceled:
        pass  # cancelled via cancel_listener()

app.run()
```

### Waiting for Inline Button Clicks

```python
sent = await message.reply("Confirm?", reply_markup=keyboard)
query = await client.listen(
    chat_id=message.chat.id,
    user_id=message.from_user.id,
    listener_type="callback_query",
    message_id=sent.id,
    unallowed_click_alert="This button is not for you.",
)
await query.answer("Confirmed!")
```

## API Reference

| Method | Description |
|---|---|
| `await client.listen(chat_id=None, filters=None, timeout=..., user_id=None, listener_type="message", unallowed_click_alert=True, message_id=None, inline_message_id=None)` | Wait for the next matching message or callback query. `chat_id` and `user_id` accept an ID, `@username`, or a list of them. `timeout` defaults to `client.listener_timeout` (`60`s); `timeout=None` waits forever. |
| `await client.ask(chat_id, text, filters=None, timeout=..., user_id=None, listener_type="message", unallowed_click_alert=True, message_id=None, inline_message_id=None, **send_kwargs)` | Send `text` (to `chat_id[0]` if a list), then wait. The sent message is attached as `response.request` and `response.sent_message`. A blank `text` skips sending. |
| `client.cancel_listener(chat_id=None, user_id=None)` | Cancel pending listeners (all if no arguments). Returns the number cancelled. Alias: `stop_listening`. |
| `await message.chat.ask(text, ...)` / `await message.chat.listen(...)` | Chat-bound shortcuts (also `chat.cancel_listener()` / `chat.stop_listening()`). |
| `await message.from_user.ask(text, ...)` / `await message.from_user.listen(...)` | User-bound shortcuts (also `user.cancel_listener()` / `user.stop_listening()`). |

## Exceptions

After `import pyrolisten.listen`, import exceptions from `pyrogram.errors` or directly from `pyrolisten` (recommended for type checkers):

- `ListenerTimeout` (subclasses `asyncio.TimeoutError`)
- `ListenerCanceled` (aliases: `ListenerCancelled`, `ListenerStopped`)

## Credits

Created by [Maharam Ali Khan](https://github.com/ps-updates).

Inspired by [Kurikit](https://github.com/TechifyBots/Kurikit) and the `pyromod` API. Written from scratch with original code.

## License

[MIT](LICENSE)
