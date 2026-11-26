"""Exceptions raised by pyrolisten's listen()/ask()."""
import asyncio


class ListenerCanceled(Exception):
    """Raised inside listen()/ask() when cancel_listener() cancels the wait."""


# Alternative spellings / names used by other libraries.
ListenerCancelled = ListenerCanceled   # British spelling
ListenerStopped = ListenerCanceled     # pyromod v3 name


class ListenerTimeout(asyncio.TimeoutError):
    """Raised when no matching message arrived in time.

    Subclasses asyncio.TimeoutError, so `except asyncio.TimeoutError` works too.
    """
