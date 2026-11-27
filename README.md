# pyrolisten

`client.listen()` and `client.ask()` for **Pyrogram, Kurigram and other Pyrogram forks**.
Methods your library already provides are never overridden.

## Install

```bash
pip install pyrolisten
```

pyrolisten does not force a Pyrogram library on you, because most forks install the same
`pyrogram` module and two of them in one environment break each other. If you already have one
(`pyrogram`, `kurigram`, ...), you're done. If not, pick one with an extra:

```bash
pip install "pyrolisten[kurigram]"
```

Extras: `pyrogram`, `kurigram`. Choose **one**.

## Usage

```python
import pyrolisten.listen        # once, at startup (e.g. main.py), before your plugins load
from pyrogram import Client, filters, ListenerTimeout, ListenerCanceled

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("name"))
async def name(client, message):
    try:
        reply = await client.ask(
            message.chat.id, "What's your name?",
            user_id=message.from_user.id, timeout=30,
        )
        await reply.reply(f"Hi {reply.text}!")
    except ListenerTimeout:
        await message.reply("Too slow!")
    except ListenerCanceled:
        pass  # client.cancel_listener(...) was called

app.run()
```

## API

| Method | Description |
|---|---|
| `await client.listen(chat_id=None, filters=None, timeout=..., user_id=None, listener_type=ListenerTypes.MESSAGE, unallowed_click_alert=True, message_id=None, inline_message_id=None)` | Wait for the next matching message or callback query. `chat_id`/`user_id` accept an ID, `@username`, or list of them. `timeout` defaults to `client.listener_timeout` (`60`s); `timeout=None` waits forever. |
| `await client.ask(chat_id, text, filters=None, timeout=..., user_id=None, listener_type=ListenerTypes.MESSAGE, unallowed_click_alert=True, message_id=None, inline_message_id=None, **send_kwargs)` | Send `text` (to `chat_id[0]` if a list), then wait. The sent message is `response.request` / `response.sent_message`. |
| `client.cancel_listener(chat_id=None, user_id=None)` | Cancel pending listeners (all if no arguments). Returns the count. Alias: `stop_listening`. |
| `await message.chat.ask(text, ...)` / `await message.chat.listen(...)` | Shortcuts bound to that chat (also `chat.cancel_listener()`). |
| `await message.from_user.ask(text, ...)` / `await message.from_user.listen(...)` | Shortcuts bound to that user (also `user.cancel_listener()`). |

After `import pyrolisten.listen` the exceptions can be imported from `pyrogram`
(`from pyrogram import ListenerTimeout, ListenerCanceled`), `pyrogram.errors`
(`from pyrogram.errors import ListenerTimeout`), or directly from `pyrolisten`. This needs
`pyrolisten.listen` to be imported **first**; editors and type checkers won't know about
patched names on `pyrogram`, so `from pyrolisten import ...` is the safer choice for typed projects.

Exceptions: `ListenerTimeout` (also an `asyncio.TimeoutError`) and `ListenerCanceled`
(aliases: `ListenerCancelled`, `ListenerStopped`).

## Author

[Maharam Ali Khan](https://github.com/ps-updates)

Based on the idea of [Kurikit](https://github.com/TechifyBots/Kurikit); the `listen`/`ask` API
is inspired by pyromod. No pyromod code is used.

## License

MIT (see `LICENSE`)
