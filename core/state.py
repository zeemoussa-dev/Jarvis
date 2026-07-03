"""
state.py — Shared Jarvis state and WebSocket broadcast hub

Responsibilities:
  - Track the current JarvisState (IDLE / LISTENING / THINKING / SPEAKING)
  - Maintain a set of WebSocket subscriber queues (one per connected UI client)
  - Broadcast state changes, messages, sysinfo, and stats to all subscribers
  - Collect CPU, RAM, and GPU stats every 2 seconds via a background thread
  - Track cumulative token usage (local LLM + Claude cloud)

All broadcast calls are thread-safe: the main audio loop runs in the main thread,
but the FastAPI WebSocket server runs in a separate asyncio event loop. We use
asyncio.run_coroutine_threadsafe() to bridge the two.
"""

import asyncio
import json
import threading
from enum import Enum
from typing import Set

import psutil

# ── GPU monitoring (optional) ─────────────────────────────────────────────────
# pynvml is NVIDIA's management library. If it's not installed or no GPU is found,
# GPU stats are simply omitted from the stats broadcast — no crash.
try:
    import pynvml
    pynvml.nvmlInit()
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    _GPU_OK = True
except Exception:
    _GPU_OK = False


# ── Jarvis state enum ─────────────────────────────────────────────────────────

class JarvisState(str, Enum):
    """The four states Jarvis cycles through on every voice interaction."""
    IDLE      = "idle"       # waiting for wake word
    LISTENING = "listening"  # recording user speech
    THINKING  = "thinking"   # transcribing / running orchestrator
    SPEAKING  = "speaking"   # TTS playback in progress


# ── Internal state ────────────────────────────────────────────────────────────

# Set of asyncio queues — one per connected WebSocket client.
# Each UI tab gets its own queue so they all receive every broadcast.
_subscribers: Set[asyncio.Queue] = set()

_current_state: JarvisState = JarvisState.IDLE

# The asyncio event loop that the FastAPI server is running on.
# Set by server.py via set_loop() before any broadcasts happen.
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the asyncio event loop used by the UI server (called from server.py)."""
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    """Create and register a new subscriber queue for a WebSocket connection."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove a subscriber queue when a WebSocket connection closes."""
    _subscribers.discard(q)


def set_state(state: JarvisState) -> None:
    """Update the current Jarvis state and broadcast it to all UI clients."""
    global _current_state
    _current_state = state
    _emit({"type": "state", "state": state.value})


def broadcast_text(role: str, text: str) -> None:
    """
    Broadcast a conversation message to the UI chat panel.
    role is either "user" or "jarvis".
    """
    _emit({"type": "message", "role": role, "text": text})


def get_state() -> JarvisState:
    """Return the current Jarvis state (used by the /state REST endpoint)."""
    return _current_state


def _emit(payload: dict) -> None:
    """
    Serialize payload to JSON and push it to all subscriber queues.
    Thread-safe: uses run_coroutine_threadsafe to cross from the audio thread
    into the asyncio event loop where the WebSocket connections live.
    """
    data = json.dumps(payload)
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(data), _loop)


async def _broadcast(payload: str) -> None:
    """Put a serialized payload into every subscriber queue (asyncio coroutine)."""
    for q in list(_subscribers):
        await q.put(payload)


# ── System stats broadcaster ──────────────────────────────────────────────────

def _collect_stats() -> dict:
    """
    Collect current CPU, RAM, and GPU metrics.
    Returns a dict matching the 'stats' WebSocket message schema.
    """
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
            util     = pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(_GPU_HANDLE)
            stats["gpu_pct"]          = util.gpu
            stats["gpu_mem_used_gb"]  = round(mem_info.used / 1e9, 1)
            stats["gpu_mem_total_gb"] = round(mem_info.total / 1e9, 1)
        except Exception:
            pass  # GPU query failed transiently — skip this tick
    return stats


def _stats_loop() -> None:
    """Background thread that collects and broadcasts system stats every 2 seconds."""
    psutil.cpu_percent(interval=None)  # prime the first reading (always returns 0 on first call)
    while True:
        threading.Event().wait(2)
        _emit(_collect_stats())


def start_stats_broadcaster() -> None:
    """Start the background stats thread. Called once from server.py on startup."""
    t = threading.Thread(target=_stats_loop, daemon=True)
    t.start()


# ── Token usage counters ──────────────────────────────────────────────────────
# Cumulative totals for the current session — displayed in the UI sysinfo panel.

_tokens_local: int = 0       # estimated tokens sent to/from the local LLM
_tokens_cloud_in: int = 0    # input tokens billed to the Claude API
_tokens_cloud_out: int = 0   # output tokens billed to the Claude API


def add_local_tokens(n: int) -> None:
    """Add n tokens to the local LLM counter and broadcast the updated totals."""
    global _tokens_local
    _tokens_local += n
    _emit({"type": "tokens", "local": _tokens_local, "cloud_in": _tokens_cloud_in, "cloud_out": _tokens_cloud_out})


def add_cloud_tokens(input_tokens: int, output_tokens: int) -> None:
    """Add Claude API token counts and broadcast the updated totals."""
    global _tokens_cloud_in, _tokens_cloud_out
    _tokens_cloud_in  += input_tokens
    _tokens_cloud_out += output_tokens
    _emit({"type": "tokens", "local": _tokens_local, "cloud_in": _tokens_cloud_in, "cloud_out": _tokens_cloud_out})
