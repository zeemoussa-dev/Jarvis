import asyncio
import json
import threading
from enum import Enum
from typing import Set

import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    _GPU_OK = True
except Exception:
    _GPU_OK = False


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


def _collect_stats() -> dict:
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    stats = {
        "type": "stats",
        "cpu_pct": round(cpu, 1),
        "mem_pct": round(mem.percent, 1),
        "mem_used_gb": round(mem.used / 1e9, 1),
        "mem_total_gb": round(mem.total / 1e9, 1),
        "gpu_pct": None,
        "gpu_mem_used_gb": None,
        "gpu_mem_total_gb": None,
    }
    if _GPU_OK:
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(_GPU_HANDLE)
            stats["gpu_pct"] = util.gpu
            stats["gpu_mem_used_gb"] = round(mem_info.used / 1e9, 1)
            stats["gpu_mem_total_gb"] = round(mem_info.total / 1e9, 1)
        except Exception:
            pass
    return stats


def _stats_loop() -> None:
    psutil.cpu_percent(interval=None)  # prime the first reading
    while True:
        threading.Event().wait(2)
        _emit(_collect_stats())


def start_stats_broadcaster() -> None:
    t = threading.Thread(target=_stats_loop, daemon=True)
    t.start()


# Token usage counters
_tokens_local: int = 0
_tokens_cloud_in: int = 0
_tokens_cloud_out: int = 0


def add_local_tokens(n: int) -> None:
    global _tokens_local
    _tokens_local += n
    _emit({"type": "tokens", "local": _tokens_local, "cloud_in": _tokens_cloud_in, "cloud_out": _tokens_cloud_out})


def add_cloud_tokens(input_tokens: int, output_tokens: int) -> None:
    global _tokens_cloud_in, _tokens_cloud_out
    _tokens_cloud_in += input_tokens
    _tokens_cloud_out += output_tokens
    _emit({"type": "tokens", "local": _tokens_local, "cloud_in": _tokens_cloud_in, "cloud_out": _tokens_cloud_out})
