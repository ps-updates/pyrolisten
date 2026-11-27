import asyncio
import importlib
import sys
import types
import unittest
from types import SimpleNamespace


def _install_fake_pyrogram():
    """Register a minimal fake `pyrogram` package in sys.modules for testing."""
    for name in list(sys.modules):
        if name == "pyrogram" or name.startswith("pyrogram."):
            del sys.modules[name]
    for name in list(sys.modules):
        if name == "pyrolisten" or name.startswith("pyrolisten."):
            del sys.modules[name]

    class StopPropagation(Exception):
        pass

    class FakeClient:
        def __init__(self):
            self.handlers = []
            self.sent = []
            self.chats = {"@room": SimpleNamespace(id=-10042)}

        def add_handler(self, handler, group=0):
            self.handlers.append((group, handler))

        async def get_chat(self, chat_id):
            return self.chats[chat_id]

        async def send_message(self, chat_id, text, **kwargs):
            msg = SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=text, kwargs=kwargs)
            self.sent.append(msg)
            return msg

    class MessageHandler:
        def __init__(self, callback):
            self.callback = callback

    class CallbackQueryHandler:
        def __init__(self, callback):
            self.callback = callback

    pg = types.ModuleType("pyrogram")
    pg.Client = FakeClient
    pg.StopPropagation = StopPropagation

    handlers = types.ModuleType("pyrogram.handlers")
    handlers.MessageHandler = MessageHandler
    handlers.CallbackQueryHandler = CallbackQueryHandler

    errors = types.ModuleType("pyrogram.errors")
    enums = types.ModuleType("pyrogram.enums")

    pg.handlers = handlers
    pg.errors = errors
    pg.enums = enums

    sys.modules["pyrogram"] = pg
    sys.modules["pyrogram.handlers"] = handlers
    sys.modules["pyrogram.errors"] = errors
    sys.modules["pyrogram.enums"] = enums
    return pg


def _msg(chat_id, user_id, text="hi", outgoing=False):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        text=text,
        outgoing=outgoing,
    )


class PyrolistenTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pg = _install_fake_pyrogram()
        self.pl = importlib.import_module("pyrolisten")
        self.client = self.pg.Client()

    async def _dispatch(self, message):
        _, handler = self.client.handlers[0]
        try:
            await handler.callback(self.client, message)
        except self.pg.StopPropagation:
            return True
        return False

    async def _dispatch_callback(self, query):
        _, handler = self.client.handlers[1]
        try:
            await handler.callback(self.client, query)
        except self.pg.StopPropagation:
            return True
        return False

    async def _wait_for_listeners(self, count=1):
        for _ in range(20):
            if len(getattr(self.client, "_pyrolisten_listeners", ())) >= count:
                return
            await asyncio.sleep(0)
        self.fail(f"expected {count} listener(s) to register")

    async def test_listen_matches_and_ignores_outgoing(self):
        task = asyncio.create_task(self.client.listen(chat_id=1, user_id=10, timeout=1))
        await self._wait_for_listeners(1)

        self.assertFalse(await self._dispatch(_msg(1, 10, "self", outgoing=True)))
        self.assertFalse(await self._dispatch(_msg(1, 99, "wrong user")))
        self.assertTrue(await self._dispatch(_msg(1, 10, "answer")))

        reply = await task
        self.assertEqual(reply.text, "answer")

    async def test_user_specific_listener_beats_chat_wide(self):
        chat_wide = asyncio.create_task(self.client.listen(chat_id=1, timeout=1))
        user_only = asyncio.create_task(self.client.listen(chat_id=1, user_id=7, timeout=1))
        await self._wait_for_listeners(2)

        await self._dispatch(_msg(1, 7, "for user"))
        self.assertEqual((await user_only).text, "for user")
        self.assertFalse(chat_wide.done())

        await self._dispatch(_msg(1, 8, "for chat"))
        self.assertEqual((await chat_wide).text, "for chat")

    async def test_broken_filter_does_not_starve_other_listeners(self):
        def bad_filter(_client, _msg_obj):
            raise ValueError("bad filter")

        broken = asyncio.create_task(
            self.client.listen(chat_id=1, user_id=1, filters=bad_filter, timeout=1)
        )
        healthy = asyncio.create_task(self.client.listen(chat_id=1, user_id=2, timeout=1))
        await self._wait_for_listeners(2)

        # Even when user_id=1 is checked first, user_id=2's listener still works.
        await self._dispatch(_msg(1, 1, "boom"))
        with self.assertRaises(ValueError):
            await broken

        await self._dispatch(_msg(1, 2, "ok"))
        self.assertEqual((await healthy).text, "ok")

    async def test_ensure_handler_retries_after_failure_and_serializes_concurrent_calls(self):
        calls = 0
        orig_add = self.client.add_handler

        def flaky_add(handler, group=0):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("transient")
            return orig_add(handler, group=group)

        self.client.add_handler = flaky_add

        with self.assertRaises(RuntimeError):
            await self.client.listen(chat_id=1, timeout=0.1)

        t1 = asyncio.create_task(self.client.listen(chat_id=1, user_id=1, timeout=1))
        t2 = asyncio.create_task(self.client.listen(chat_id=1, user_id=2, timeout=1))
        await self._wait_for_listeners(2)

        self.assertEqual(len(self.client.handlers), 2)
        await self._dispatch(_msg(1, 1, "one"))
        await self._dispatch(_msg(1, 2, "two"))
        self.assertEqual((await t1).text, "one")
        self.assertEqual((await t2).text, "two")

    async def test_ask_attaches_request_and_cleans_up_on_send_error(self):
        task = asyncio.create_task(self.client.ask("@room", "Name?", timeout=1))
        await self._wait_for_listeners(1)
        await asyncio.sleep(0)
        await self._dispatch(_msg(-10042, 5, "Alice"))

        reply = await task
        self.assertEqual(reply.text, "Alice")
        self.assertEqual(reply.request.text, "Name?")
        self.assertIs(reply.sent_message, reply.request)

        async def fail_send(*_args, **_kwargs):
            raise OSError("network")

        self.client.send_message = fail_send
        with self.assertRaises(OSError):
            await self.client.ask(1, "Hi", timeout=1)
        self.assertEqual(self.client._pyrolisten_listeners, [])

    async def test_ask_fallback_handles_send_message_without_chat(self):
        pg = _install_fake_pyrogram()

        async def native_listen(self, chat_id=None, filters=None, timeout=60, user_id=None):
            return SimpleNamespace(text="from native", chat_id=chat_id)

        pg.Client.listen = native_listen
        importlib.import_module("pyrolisten")
        client = pg.Client()

        async def send_none(*_args, **_kwargs):
            return None

        client.send_message = send_none
        reply = await client.ask(123, "Prompt", timeout=1)
        self.assertEqual(reply.text, "from native")
        self.assertEqual(reply.chat_id, 123)
        self.assertIsNone(reply.request)

    async def test_timeout_and_cancel_listener(self):
        with self.assertRaises(self.pg.ListenerTimeout):
            await self.client.listen(chat_id=1, timeout=0.01)

        t1 = asyncio.create_task(self.client.listen(chat_id=1, user_id=1, timeout=1))
        t2 = asyncio.create_task(self.client.listen(chat_id=2, user_id=2, timeout=1))
        await self._wait_for_listeners(2)

        self.assertEqual(self.client.cancel_listener(chat_id=1), 1)
        with self.assertRaises(self.pg.ListenerCanceled):
            await t1
        self.assertEqual(self.client.stop_listening(), 1)
        with self.assertRaises(self.pg.ListenerStopped):
            await t2

    async def test_list_ids_and_username_for_chat_and_user(self):
        self.client.chats["@alice"] = SimpleNamespace(id=77)
        task = asyncio.create_task(
            self.client.listen(chat_id=["@room", 99], user_id=["@alice", 88], timeout=1)
        )
        await self._wait_for_listeners(1)

        self.assertFalse(await self._dispatch(_msg(-10042, 12, "wrong user")))
        self.assertTrue(await self._dispatch(_msg(99, 77, "matched")))
        self.assertEqual((await task).text, "matched")

    async def test_callback_query_listener_and_unallowed_click_alert(self):
        alerts = []

        def make_query(chat_id, user_id, msg_id, data):
            async def answer(text=None, show_alert=False):
                alerts.append((user_id, text, show_alert))

            return SimpleNamespace(
                message=SimpleNamespace(id=msg_id, chat=SimpleNamespace(id=chat_id)),
                from_user=SimpleNamespace(id=user_id),
                inline_message_id=None,
                data=data,
                answer=answer,
            )

        task = asyncio.create_task(
            self.client.listen(
                chat_id=1,
                user_id=10,
                listener_type=self.pl.ListenerTypes.CALLBACK_QUERY,
                unallowed_click_alert="Not for you",
                message_id=50,
                timeout=1,
            )
        )
        await self._wait_for_listeners(1)

        self.assertFalse(
            await self._dispatch_callback(make_query(1, 99, 50, "wrong_user"))
        )
        self.assertEqual(alerts, [(99, "Not for you", True)])
        self.assertFalse(task.done())

        self.assertTrue(await self._dispatch_callback(make_query(1, 10, 50, "ok")))
        self.assertEqual((await task).data, "ok")

    async def test_no_updates_raises_listener_stopped(self):
        self.client.no_updates = True
        with self.assertRaises(self.pg.ListenerStopped):
            await self.client.listen(chat_id=1, timeout=1)


if __name__ == "__main__":
    unittest.main()
