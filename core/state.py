"""
Shared Jarvis state broadcaster.
The UI server subscribes here; main.py sets state here.
"""

import asyncio
import json
from enum import Enum
from typing import Set


class JarvisState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


_subscribers: Set[asyncio.Queue] = set()
_current_state: JarvisState = JarvisState.IDLE
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def set_state(state: JarvisState) -> None:
    global _current_state
    _current_state = state
    payload = json.dumps({"state": state.value})
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(payload), _loop)


async def _broadcast(payload: str) -> None:
    for q in list(_subscribers):
        await q.put(payload)


def get_state() -> JarvisState:
    return _current_state
