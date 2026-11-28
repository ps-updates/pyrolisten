"""pyrolisten - listen() / ask() for Pyrogram, Kurigram and other forks.

    import pyrolisten.listen   # pyromod style
    import pyrolisten          # also works
"""
from . import ask, listen  # applies the patches on import
from .exceptions import (
    ListenerCanceled,
    ListenerCancelled,
    ListenerStopped,
    ListenerTimeout,
)

__all__ = [
    "ask",
    "listen",
    "ListenerCanceled",
    "ListenerCancelled",
    "ListenerStopped",
    "ListenerTimeout",
]
