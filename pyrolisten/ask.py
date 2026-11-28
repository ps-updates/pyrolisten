"""pyrolisten.ask - Client.ask() for Pyrogram and its forks."""
from .listen import (
    Client,
    _UNSET,
    _await_listener,
    _install_on,
    _register_listener,
)


async def ask(
    self,
    chat_id,
    text,
    filters=None,
    timeout=_UNSET,
    user_id=None,
    listener_type="message",
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


_install_on(Client, "ask", ask)
