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
from enum import Enum
from typing import Any, List, Optional, Tuple, Union

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
    "ListenerTypes",
]


class ListenerTypes(str, Enum):
    """Update types supported by listen() and ask()."""

    MESSAGE = "message"
    CALLBACK_QUERY = "callback_query"

_HANDLER_GROUP = -999
_UNSET = object()


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
    listener_type: str
    chat_ids: Optional[Tuple[int, ...]]
    user_ids: Optional[Tuple[int, ...]]
    message_ids: Optional[Tuple[int, ...]]
    inline_message_ids: Optional[Tuple[str, ...]]
    future: Any
    filters: Any = None
    unallowed_click_alert: Union[bool, str] = True


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


def _as_tuple(value) -> Optional[Tuple[Any, ...]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return tuple(value)
    return (value,)


async def _resolve_ids(client, value) -> Optional[Tuple[int, ...]]:
    items = _as_tuple(value)
    if items is None:
        return None
    resolved = []
    for item in items:
        if isinstance(item, str):
            item = (await client.get_chat(item)).id
        resolved.append(item)
    return tuple(resolved)


async def _dispatch(
    client,
    update,
    listener_type: str,
    chat_id: Optional[int],
    user_id: Optional[int],
    message_id: Optional[int] = None,
    inline_message_id: Optional[str] = None,
):
    listeners = _store(client)
    if not listeners:
        return

    # user-specific listeners are kept ahead of chat-wide ones on insert
    for listener in list(listeners):
        if listener.future.done() or listener.listener_type != listener_type:
            continue
        if listener.chat_ids is not None and chat_id not in listener.chat_ids:
            continue
        if listener.message_ids is not None and message_id not in listener.message_ids:
            continue
        if (
            listener.inline_message_ids is not None
            and inline_message_id not in listener.inline_message_ids
        ):
            continue
        if listener.user_ids is not None and user_id not in listener.user_ids:
            if (
                listener_type == ListenerTypes.CALLBACK_QUERY
                and listener.unallowed_click_alert
            ):
                alert_text = (
                    listener.unallowed_click_alert
                    if isinstance(listener.unallowed_click_alert, str)
                    else None
                )
                try:
                    await update.answer(text=alert_text, show_alert=True)
                except Exception:
                    pass
            continue
        if listener.filters is not None:
            try:
                matched = await _passes(listener.filters, client, update)
            except Exception as exc:
                if not listener.future.done():
                    listener.future.set_exception(exc)
                continue
            if not matched:
                continue
        if listener.future.done():
            continue
        listener.future.set_result(update)
        if _STOP is not None:
            raise _STOP  # keep the answer away from your normal handlers
        return


async def _on_message(client, message):
    if getattr(message, "outgoing", False):
        return
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    await _dispatch(
        client,
        message,
        ListenerTypes.MESSAGE,
        chat.id if chat else None,
        user.id if user else None,
        getattr(message, "id", None),
    )


async def _on_callback_query(client, query):
    msg = getattr(query, "message", None)
    chat = getattr(msg, "chat", None) if msg else None
    user = getattr(query, "from_user", None)
    await _dispatch(
        client,
        query,
        ListenerTypes.CALLBACK_QUERY,
        chat.id if chat else None,
        user.id if user else None,
        getattr(msg, "id", None) if msg else None,
        getattr(query, "inline_message_id", None),
    )


async def _ensure_handler(client):
    if getattr(client, "_pyrolisten_handler", False):
        return
    lock = getattr(client, "_pyrolisten_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        client._pyrolisten_lock = lock
    async with lock:
        if getattr(client, "_pyrolisten_handler", False):
            return
        client.add_handler(_handlers.MessageHandler(_on_message), group=_HANDLER_GROUP)
        cb_handler = getattr(_handlers, "CallbackQueryHandler", None)
        if cb_handler is not None:
            client.add_handler(cb_handler(_on_callback_query), group=_HANDLER_GROUP)
        await asyncio.sleep(0)  # let the library finish registering it
        client._pyrolisten_handler = True


async def _register_listener(
    client,
    chat_id,
    user_id,
    filters,
    listener_type=ListenerTypes.MESSAGE,
    unallowed_click_alert=True,
    message_id=None,
    inline_message_id=None,
):
    if getattr(client, "no_updates", False):
        raise ListenerStopped(
            "Cannot listen for updates on a client started with no_updates"
        )

    ltype = listener_type.value if isinstance(listener_type, Enum) else listener_type
    chat_ids = await _resolve_ids(client, chat_id)
    user_ids = await _resolve_ids(client, user_id)

    await _ensure_handler(client)
    listener = _Listener(
        listener_type=ltype,
        chat_ids=chat_ids,
        user_ids=user_ids,
        message_ids=_as_tuple(message_id),
        inline_message_ids=_as_tuple(inline_message_id),
        future=asyncio.get_running_loop().create_future(),
        filters=filters,
        unallowed_click_alert=unallowed_click_alert,
    )
    store = _store(client)
    if user_ids is None:
        store.append(listener)
    else:
        idx = next(
            (i for i, item in enumerate(store) if item.user_ids is None),
            len(store),
        )
        store.insert(idx, listener)
    return store, listener


async def _await_listener(store: List[_Listener], listener: _Listener, timeout, client=None):
    if timeout is _UNSET:
        timeout = getattr(client, "listener_timeout", 60)
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
async def listen(
    self,
    chat_id=None,
    filters=None,
    timeout=_UNSET,
    user_id=None,
    listener_type=ListenerTypes.MESSAGE,
    unallowed_click_alert=True,
    message_id=None,
    inline_message_id=None,
):
    """Wait for the next matching message or callback query and return it.

    timeout defaults to client.listener_timeout (60s); timeout=None waits forever.
    Raises ListenerTimeout on timeout and ListenerCanceled if cancelled.
    """
    store, listener = await _register_listener(
        self,
        chat_id,
        user_id,
        filters,
        listener_type=listener_type,
        unallowed_click_alert=unallowed_click_alert,
        message_id=message_id,
        inline_message_id=inline_message_id,
    )
    return await _await_listener(store, listener, timeout, self)


async def ask(
    self,
    chat_id,
    text,
    filters=None,
    timeout=_UNSET,
    user_id=None,
    listener_type=ListenerTypes.MESSAGE,
    unallowed_click_alert=True,
    message_id=None,
    inline_message_id=None,
    **send_kwargs,
):
    """Send `text` to chat_id, then wait for the answer (see listen()).

    When `chat_id` is a list, the prompt goes to `chat_id[0]` and any listed
    chat may answer. Extra keyword arguments go to send_message(). The sent
    message is available as `response.request` (also `response.sent_message`).
    A blank `text` skips sending and only listens.
    """
    has_text = bool(text and str(text).strip())

    if getattr(self.listen, "_pyrolisten", False):
        store, listener = await _register_listener(
            self,
            chat_id,
            user_id,
            filters,
            listener_type=listener_type,
            unallowed_click_alert=unallowed_click_alert,
            message_id=message_id,
            inline_message_id=inline_message_id,
        )

        request = None
        try:
            if has_text:
                target_chat = listener.chat_ids[0] if listener.chat_ids else chat_id
                request = await self.send_message(target_chat, text, **send_kwargs)
                if getattr(request, "chat", None) is not None and (
                    listener.chat_ids is None or len(listener.chat_ids) == 1
                ):
                    listener.chat_ids = (request.chat.id,)
        except BaseException:
            try:
                store.remove(listener)
            except ValueError:
                pass
            raise

        response = await _await_listener(store, listener, timeout, self)
    else:
        request = None
        target_chat = chat_id[0] if isinstance(chat_id, (list, tuple)) else chat_id
        if has_text:
            request = await self.send_message(target_chat, text, **send_kwargs)
            if getattr(request, "chat", None) is not None and not isinstance(
                chat_id, (list, tuple)
            ):
                chat_id = request.chat.id

        resolved_timeout = (
            getattr(self, "listener_timeout", 60) if timeout is _UNSET else timeout
        )
        kwargs = {"filters": filters, "timeout": resolved_timeout}
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
        if chat_id is not None and (
            listener.chat_ids is None or chat_id not in listener.chat_ids
        ):
            continue
        if user_id is not None and (
            listener.user_ids is None or user_id not in listener.user_ids
        ):
            continue
        if not listener.future.done():
            listener.future.set_exception(ListenerCanceled())
            cancelled += 1
    return cancelled


def _install_on(target, name, func):
    existing = getattr(target, name, None)
    if existing is not None and not getattr(existing, "_pyrolisten", False):
        return False  # the installed library already provides it
    func._pyrolisten = True
    setattr(target, name, func)
    return True


_install_on(Client, "listen", listen)
_install_on(Client, "ask", ask)
_install_on(Client, "cancel_listener", cancel_listener)
_install_on(Client, "stop_listening", cancel_listener)


# --------------------------------------------------------------------------- #
# Chat & User shortcuts (pyromod-style: message.chat.ask(), message.from_user.ask())
# --------------------------------------------------------------------------- #
def _bound_client(obj):
    client = getattr(obj, "_client", None)
    if client is None:
        raise RuntimeError("This object is not bound to a Pyrogram Client.")
    return client


async def _chat_listen(self, filters=None, timeout=_UNSET, user_id=None, **kwargs):
    return await _bound_client(self).listen(
        self.id, filters=filters, timeout=timeout, user_id=user_id, **kwargs
    )


async def _chat_ask(self, text, filters=None, timeout=_UNSET, user_id=None, **kwargs):
    return await _bound_client(self).ask(
        self.id, text, filters=filters, timeout=timeout, user_id=user_id, **kwargs
    )


def _chat_cancel(self, user_id=None) -> int:
    return _bound_client(self).cancel_listener(self.id, user_id=user_id)


async def _user_listen(self, chat_id=None, filters=None, timeout=_UNSET, **kwargs):
    return await _bound_client(self).listen(
        chat_id=chat_id, filters=filters, timeout=timeout, user_id=self.id, **kwargs
    )


async def _user_ask(self, text, chat_id=None, filters=None, timeout=_UNSET, **kwargs):
    return await _bound_client(self).ask(
        self.id if chat_id is None else chat_id,
        text,
        filters=filters,
        timeout=timeout,
        user_id=self.id,
        **kwargs,
    )


def _user_cancel(self, chat_id=None) -> int:
    return _bound_client(self).cancel_listener(chat_id=chat_id, user_id=self.id)


try:
    _types = importlib.import_module(_pg.__name__ + ".types")
except ImportError:
    _types = getattr(_pg, "types", None)

for _cls_name, _methods in (
    (
        "Chat",
        (
            ("listen", _chat_listen),
            ("ask", _chat_ask),
            ("cancel_listener", _chat_cancel),
            ("stop_listening", _chat_cancel),
        ),
    ),
    (
        "User",
        (
            ("listen", _user_listen),
            ("ask", _user_ask),
            ("cancel_listener", _user_cancel),
            ("stop_listening", _user_cancel),
        ),
    ),
):
    _cls = getattr(_types, _cls_name, None) if _types is not None else None
    if _cls is not None:
        for _mname, _mfunc in _methods:
            _install_on(_cls, _mname, _mfunc)


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
        ("ListenerTypes", ListenerTypes),
    ):
        if not hasattr(_target, _name):
            setattr(_target, _name, _exc)

try:
    _enums = importlib.import_module(_pg.__name__ + ".enums")
except ImportError:
    _enums = getattr(_pg, "enums", None)

if _enums is not None and not hasattr(_enums, "ListenerTypes"):
    setattr(_enums, "ListenerTypes", ListenerTypes)
