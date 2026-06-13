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
    _emit({"type": "state", "state": state.value})


def broadcast_text(role: str, text: str) -> None:
    """Broadcast a conversation message to all UI subscribers."""
    _emit({"type": "message", "role": role, "text": text})


def _emit(payload: dict) -> None:
    data = json.dumps(payload)
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(data), _loop)


async def _broadcast(payload: str) -> None:
    for q in list(_subscribers):
        await q.put(payload)


def get_state() -> JarvisState:
    return _current_state
