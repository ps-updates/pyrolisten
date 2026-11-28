# pyrolisten

[![PyPI version](https://img.shields.io/pypi/v/pyrolisten.svg)](https://pypi.org/project/pyrolisten/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyrolisten.svg)](https://pypi.org/project/pyrolisten/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/ps-updates/pyrolisten/blob/main/LICENSE)

**Pyrolisten** provides `listen()`, `ask()`, and `cancel_listener()` functionality for **Pyrogram, Kurigram, and other Pyrogram-compatible forks**.

A lightweight, fork-friendly listener implementation inspired by the `pyromod` API, without overriding methods your library already provides.

## Features

- **`client.listen()` & `client.ask()`** — Wait for messages and inline button clicks.
- **Callback query listeners** — Listen for inline button clicks using `listener_type="callback_query"`.
- **Chat & User shortcuts** — Use `message.chat.ask()`, `message.chat.listen()`, `message.from_user.ask()`, and `message.from_user.listen()`.
- **Flexible targeting** — Pass numeric IDs, usernames, or lists of IDs/usernames to `chat_id` and `user_id`.
- **Listener cancellation** — Cancel pending listeners using `cancel_listener()` or `stop_listening()`.
- **Fork-friendly** — Never overwrites existing listener methods provided by your installed library.
- **Zero runtime dependencies** — Works alongside whichever Pyrogram-compatible package you already have installed.

## Installation

Install Pyrolisten:

```bash
pip install pyrolisten
```

Pyrolisten does not force a Pyrogram dependency because forks share the `pyrogram` module name and installing multiple implementations in the same environment can cause conflicts.

If you don't have a Pyrogram-compatible library installed yet, choose **one** extra:

```bash
pip install "pyrolisten[kurigram]"
```

Or:

```bash
pip install "pyrolisten[pyrogram]"
```

> Install only one Pyrogram-compatible implementation in your environment.

## Quick Start

Import `pyrolisten.listen` (or simply `pyrolisten`) once at startup, before loading your handlers.

```python
import pyrolisten.listen

from pyrogram import Client, filters
from pyrolisten import ListenerTimeout, ListenerCanceled

app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Optional: Default listener timeout in seconds.
# Default: 60 seconds
app.listener_timeout = 30


@app.on_message(filters.command("name"))
async def ask_name(client, message):
    try:
        reply = await message.chat.ask(
            "What's your name?",
            user_id=message.from_user.id,
        )

        await reply.reply(f"Hi {reply.text}!")

    except ListenerTimeout:
        await message.reply("You took too long to respond!")

    except ListenerCanceled:
        pass


app.run()
```

## Usage

### Listening for Messages

Wait for the next matching message.

```python
reply = await client.listen(
    chat_id=message.chat.id,
    user_id=message.from_user.id,
    timeout=30,
)

await message.reply(f"You said: {reply.text}")
```

You can also use the Chat shortcut:

```python
reply = await message.chat.listen(
    user_id=message.from_user.id,
    timeout=30,
)
```

### Asking Questions

`ask()` sends a message and waits for a matching reply.

```python
reply = await client.ask(
    chat_id=message.chat.id,
    text="What's your name?",
    user_id=message.from_user.id,
    timeout=30,
)

await message.reply(f"Hello, {reply.text}!")
```

The sent message is attached to the returned update as:

- `reply.request`
- `reply.sent_message`

You can also use the Chat shortcut:

```python
reply = await message.chat.ask(
    "What's your name?",
    user_id=message.from_user.id,
)
```

### Waiting for Inline Button Clicks

Use `listener_type="callback_query"` to wait for an inline button click.

```python
sent = await message.reply(
    "Confirm?",
    reply_markup=keyboard,
)

query = await client.listen(
    chat_id=message.chat.id,
    user_id=message.from_user.id,
    listener_type="callback_query",
    message_id=sent.id,
    unallowed_click_alert="This button is not for you.",
)

await query.answer("Confirmed!")
```

You can restrict callback listeners using `message_id` or `inline_message_id`.

### Chat & User Shortcuts

Pyrolisten provides shortcuts to use listener methods directly through Chat and User objects.

| Shortcut | Equivalent |
|---|---|
| `await message.chat.listen(...)` | `await client.listen(chat_id=message.chat.id, ...)` |
| `await message.chat.ask(text, ...)` | `await client.ask(chat_id=message.chat.id, text=text, ...)` |
| `message.chat.cancel_listener(user_id=...)` | `client.cancel_listener(chat_id=message.chat.id, user_id=user_id)` |
| `await message.from_user.listen(...)` | `await client.listen(user_id=message.from_user.id, ...)` |
| `await message.from_user.ask(text, ...)` | `await client.ask(chat_id=user_id, text=text, user_id=user_id, ...)` |
| `message.from_user.cancel_listener(chat_id=...)` | `client.cancel_listener(chat_id=chat_id, user_id=message.from_user.id)` |

#### User Shortcut Example

By default, `message.from_user.ask()` sends the question to the user's own chat.

```python
reply = await message.from_user.ask(
    "What's your name?",
    timeout=30,
)

await message.reply(f"Hello, {reply.text}!")
```

You can specify a chat explicitly:

```python
reply = await message.from_user.ask(
    "What's your name?",
    chat_id=message.chat.id,
    timeout=30,
)
```

### Cancelling Listeners

Cancel pending listeners whenever you need to stop waiting for a response.

```python
cancelled = client.cancel_listener(
    chat_id=message.chat.id,
    user_id=message.from_user.id,
)

await message.reply(f"Cancelled {cancelled} listener(s).")
```

You can cancel listeners using:

```python
# Cancel listeners matching a specific chat.
client.cancel_listener(chat_id=123456789)

# Cancel listeners matching a specific user.
client.cancel_listener(user_id=123456789)

# Cancel listeners matching both chat and user.
client.cancel_listener(
    chat_id=123456789,
    user_id=123456789,
)

# Cancel all pending listeners.
client.cancel_listener()
```

Alias:

```python
client.stop_listening()
```

`cancel_listener()` returns the number of listeners cancelled.

The `chat_id` and `user_id` arguments used for cancellation are numeric IDs.

## API Reference

### `client.listen()`

Wait for the next matching message or callback query.

```python
await client.listen(
    chat_id=None,
    filters=None,
    timeout=...,
    user_id=None,
    listener_type="message",
    unallowed_click_alert=True,
    message_id=None,
    inline_message_id=None,
)
```

| Parameter | Description |
|---|---|
| `chat_id` | Chat ID, username, or a list of chat IDs/usernames. |
| `filters` | Optional filters for incoming updates. |
| `timeout` | Timeout in seconds. Defaults to `client.listener_timeout` (60 seconds). Use `None` to wait indefinitely. |
| `user_id` | User ID, username, or a list of IDs/usernames. |
| `listener_type` | `"message"` or `"callback_query"`. |
| `unallowed_click_alert` | `True`, `False`, or custom alert text for unauthorized callback clicks. |
| `message_id` | Restrict callback queries to a specific message. |
| `inline_message_id` | Restrict callback queries to a specific inline message. |

### `client.ask()`

Send a message and wait for a matching response.

```python
await client.ask(
    chat_id,
    text,
    filters=None,
    timeout=...,
    user_id=None,
    listener_type="message",
    unallowed_click_alert=True,
    message_id=None,
    inline_message_id=None,
    **send_kwargs,
)
```

| Parameter | Description |
|---|---|
| `chat_id` | Chat ID, username, or list of IDs/usernames. If a list is provided, the message is sent to the first entry. |
| `text` | Message to send. Empty text skips sending and only listens. |
| `filters` | Optional filters for incoming updates. |
| `timeout` | Timeout in seconds. Defaults to `client.listener_timeout` (60 seconds). Use `None` to wait indefinitely. |
| `user_id` | User ID, username, or a list of IDs/usernames. |
| `listener_type` | `"message"` or `"callback_query"`. |
| `unallowed_click_alert` | Alert configuration for unauthorized callback clicks. |
| `message_id` | Restrict callback queries to a specific message. |
| `inline_message_id` | Restrict callback queries to a specific inline message. |
| `**send_kwargs` | Additional arguments forwarded to `client.send_message()`. |

### `client.cancel_listener()`

Cancel pending listeners matching the provided criteria.

```python
client.cancel_listener(
    chat_id=None,
    user_id=None,
)
```

| Parameter | Description |
|---|---|
| `chat_id` | Optional chat ID to match. |
| `user_id` | Optional user ID to match. |

If no arguments are provided, all pending listeners are cancelled.

Alias: `client.stop_listening()`.

## Exceptions

After importing `pyrolisten.listen`, the following exceptions can be imported directly from `pyrolisten`.

```python
from pyrolisten import ListenerTimeout, ListenerCanceled
```

| Exception | Description |
|---|---|
| `ListenerTimeout` | Raised when a listener exceeds its timeout. Subclasses `asyncio.TimeoutError`. |
| `ListenerCanceled` | Raised when a listener is cancelled. |

Aliases for `ListenerCanceled`:

- `ListenerCancelled`
- `ListenerStopped`

## Compatibility

Pyrolisten is designed for Pyrogram-compatible libraries, including:

- Pyrogram
- Kurigram
- Other compatible forks

Pyrolisten does not replace existing `listen()`, `ask()`, or `cancel_listener()` methods when they are already provided by your installed library.

When your installed library already provides its own `listen()` method, Pyrolisten's `ask()` uses that implementation instead of its own listener. In this case, only `filters`, `timeout`, and `user_id` are forwarded to the existing `listen()` method.

Advanced listener options such as `listener_type`, `message_id`, `inline_message_id`, and `unallowed_click_alert` may therefore not be supported through `ask()` when using a fork-provided listener.

## Credits

- **Author:** [Maharam Ali Khan](https://github.com/ps-updates)
- **Inspiration:** Built from scratch with original code, inspired by [Kurikit](https://github.com/TechifyBots/Kurikit) and the [pyromod](https://github.com/usernein/pyromod) API.

Found a bug or have a suggestion? Feel free to [open an issue](https://github.com/ps-updates/pyrolisten/issues).

## License

Released under the [MIT License](LICENSE).
