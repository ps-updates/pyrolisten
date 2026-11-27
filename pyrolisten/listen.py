"""
pyrolisten.listen - Client.listen(), Client.ask() and Client.cancel_listener()
for Pyrogram and its forks.

Works with anything that installs a `pyrogram` module (Pyrogram, Kurigram, ...).
Methods the installed library already provides are never overridden.

Usage:  import pyrolisten.listen   # (or just `import pyrolisten`) once, at startup
"""
import asyncio
import importlib
import inspect
from dataclasses import dataclass
from typing import Any, List, Optional

from .exceptions import (
    ListenerCanceled,
    ListenerCancelled,
    ListenerStopped,
    ListenerTimeout,
)

__all__ = [
    "ListenerCanceled",
    "ListenerCancelled",
    "ListenerStopped",
    "ListenerTimeout",
]

_HANDLER_GROUP = -999


# --------------------------------------------------------------------------- #
# Find the installed Pyrogram-compatible library
# --------------------------------------------------------------------------- #
def _load_backend():
    try:
        return importlib.import_module("pyrogram")
    except ImportError as exc:
        raise ImportError(
            "pyrolisten needs Pyrogram or a compatible fork (kurigram, ...). "
            'Install one, e.g.: pip install "pyrolisten[kurigram]"'
        ) from exc


_pg = _load_backend()
Client = _pg.Client
_handlers = importlib.import_module(_pg.__name__ + ".handlers")
_STOP = getattr(_pg, "StopPropagation", None)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
@dataclass(eq=False)
class _Listener:
    chat_id: Optional[int]
    user_id: Optional[int]
    future: Any
    filters: Any = None


def _store(client) -> List[_Listener]:
    try:
        return client._pyrolisten_listeners
    except AttributeError:
        client._pyrolisten_listeners = []
        return client._pyrolisten_listeners


async def _passes(flt, client, update) -> bool:
    result = flt(client, update)
    if inspect.isawaitable(result):
        result = await result
    return bool(result)


async def _on_message(client, message):
    if getattr(message, "outgoing", False):
        return
    listeners = _store(client)
    if not listeners:
        return

    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    chat_id = chat.id if chat else None
    user_id = user.id if user else None

    # listeners tied to a specific user win over chat-wide ones
    for listener in sorted(listeners, key=lambda item: item.user_id is None):
        if listener.future.done():
            continue
        if listener.chat_id is not None and listener.chat_id != chat_id:
            continue
        if listener.user_id is not None and listener.user_id != user_id:
            continue
        if listener.filters is not None and not await _passes(
            listener.filters, client, message
        ):
            continue
        if listener.future.done():
            continue
        listener.future.set_result(message)
        if _STOP is not None:
            raise _STOP  # keep the answer away from your normal handlers
        return


async def _ensure_handler(client):
    if getattr(client, "_pyrolisten_handler", False):
        return
    client._pyrolisten_handler = True
    client.add_handler(_handlers.MessageHandler(_on_message), group=_HANDLER_GROUP)
    await asyncio.sleep(0)  # let the library finish registering it


async def _await_listener(store: List[_Listener], listener: _Listener, timeout):
    try:
        return await asyncio.wait_for(listener.future, timeout)
    except asyncio.TimeoutError:
        raise ListenerTimeout(f"no answer within {timeout}s") from None
    finally:
        try:
            store.remove(listener)
        except ValueError:
            pass


# --------------------------------------------------------------------------- #
# Client methods
# --------------------------------------------------------------------------- #
async def listen(self, chat_id=None, filters=None, timeout=60, user_id=None):
    """Wait for the next matching message and return it.

    timeout=None waits forever.
    Raises ListenerTimeout on timeout and ListenerCanceled if cancelled.
    """
    if isinstance(chat_id, str):  # @username -> numeric id
        chat_id = (await self.get_chat(chat_id)).id

    await _ensure_handler(self)
    listener = _Listener(
        chat_id, user_id, asyncio.get_running_loop().create_future(), filters
    )
    store = _store(self)
    store.append(listener)
    return await _await_listener(store, listener, timeout)


async def ask(self, chat_id, text, filters=None, timeout=60, user_id=None, **send_kwargs):
    """Send `text` to chat_id, then wait for the answer (see listen()).

    Extra keyword arguments go to send_message(). The sent message is available
    as `response.request` (also `response.sent_message`). A blank `text` skips
    sending and only listens.
    """
    has_text = bool(text and str(text).strip())

    if getattr(self.listen, "_pyrolisten", False):
        if isinstance(chat_id, str):  # @username -> numeric id
            chat_id = (await self.get_chat(chat_id)).id

        await _ensure_handler(self)
        listener = _Listener(
            chat_id, user_id, asyncio.get_running_loop().create_future(), filters
        )
        store = _store(self)
        store.append(listener)

        request = None
        try:
            if has_text:
                request = await self.send_message(chat_id, text, **send_kwargs)
                if getattr(request, "chat", None) is not None:
                    listener.chat_id = request.chat.id
        except BaseException:
            try:
                store.remove(listener)
            except ValueError:
                pass
            raise

        response = await _await_listener(store, listener, timeout)
    else:
        request = None
        if has_text:
            request = await self.send_message(chat_id, text, **send_kwargs)
            chat_id = request.chat.id

        kwargs = {"filters": filters, "timeout": timeout}
        if user_id is not None:  # keeps this working with listen() from other libs
            kwargs["user_id"] = user_id
        response = await self.listen(chat_id, **kwargs)

    if response is not None:
        for attr in ("request", "sent_message"):
            try:
                setattr(response, attr, request)
            except Exception:
                pass
    return response


def cancel_listener(self, chat_id=None, user_id=None) -> int:
    """Cancel pending listeners; their listen()/ask() raises ListenerCanceled.

    With no arguments every listener of this client is cancelled.
    Returns how many were cancelled.
    """
    cancelled = 0
    for listener in list(_store(self)):
        if chat_id is not None and listener.chat_id != chat_id:
            continue
        if user_id is not None and listener.user_id != user_id:
            continue
        if not listener.future.done():
            listener.future.set_exception(ListenerCanceled())
            cancelled += 1
    return cancelled


def _install(name, func):
    existing = getattr(Client, name, None)
    if existing is not None and not getattr(existing, "_pyrolisten", False):
        return False  # the installed library already provides it
    func._pyrolisten = True
    setattr(Client, name, func)
    return True


_install("listen", listen)
_install("ask", ask)
_install("cancel_listener", cancel_listener)
_install("stop_listening", cancel_listener)


try:
    _errors = importlib.import_module(_pg.__name__ + ".errors")
except ImportError:
    _errors = getattr(_pg, "errors", None)

# Make the exceptions importable straight from `pyrogram` and `pyrogram.errors`
# (never overrides a name the installed library already defines)
_targets = (_pg, _errors) if _errors is not None else (_pg,)
for _target in _targets:
    for _name, _exc in (
        ("ListenerTimeout", ListenerTimeout),
        ("ListenerCanceled", ListenerCanceled),
        ("ListenerCancelled", ListenerCanceled),
        ("ListenerStopped", ListenerCanceled),
    ):
        if not hasattr(_target, _name):
            setattr(_target, _name, _exc)
