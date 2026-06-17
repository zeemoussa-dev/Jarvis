"""
FastAPI server that serves the Jarvis UI and streams state via WebSocket.
Runs in a background thread alongside the main audio loop.
"""

import asyncio
import json
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from core import state as jarvis_state
from agents import AGENT_TOOLS

app = FastAPI()

UI_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(UI_DIR / "index.html")


@app.get("/state")
async def current_state():
    return {"state": jarvis_state.get_state().value}


@app.get("/version")
async def version():
    return {"version": config.VERSION}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    q = jarvis_state.subscribe()
    # Send current state + agent list + tokens immediately on connect
    await websocket.send_text(json.dumps({"type": "state", "state": jarvis_state.get_state().value}))
    agent_names = [t["name"] for t in AGENT_TOOLS]
    await websocket.send_text(json.dumps({"type": "agents", "agents": agent_names}))
    from core.mood import get_mood
    await websocket.send_text(json.dumps({"type": "mood", "mood": get_mood().value}))
    await websocket.send_text(json.dumps({
        "type": "tokens",
        "local": jarvis_state._tokens_local,
        "cloud_in": jarvis_state._tokens_cloud_in,
        "cloud_out": jarvis_state._tokens_cloud_out,
    }))
    from core.tts import _xtts_available
    from core.stt import _parakeet_available, _parakeet_checked
    await websocket.send_text(json.dumps({
        "type": "sysinfo",
        "tts_engine": "XTTS V2" if _xtts_available else "EDGE TTS",
        "stt_engine": ("PARAKEET TDT 1.1B (GPU)" if _parakeet_available
                       else ("WHISPER BASE.EN" if _parakeet_checked else "CHECKING...")),
        "ai_core": "CLAUDE SONNET",
        "version": config.VERSION,
    }))
    try:
        while True:
            payload = await q.get()
            await websocket.send_text(payload)
    except WebSocketDisconnect:
        jarvis_state.unsubscribe(q)
    except Exception:
        jarvis_state.unsubscribe(q)


def _kill_port(port: int) -> None:
    """Kill any process already holding the given port before we bind to it."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return  # port is free
    import psutil, time
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    print(f"[Server] Port {port} held by PID {conn.pid} ({proc.name()}) — terminating.")
                    proc.terminate()
                    proc.wait(timeout=3)
                    time.sleep(0.5)  # give the OS a moment to release the port
                    return
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    print(f"[Server] Could not terminate PID {conn.pid}: {e}")
    except psutil.AccessDenied:
        # Fall back to netstat via subprocess on Windows
        import subprocess, os
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                print(f"[Server] Port {port} held by PID {pid} (via netstat) — terminating.")
                os.system(f"taskkill /F /PID {pid}")
                time.sleep(0.5)
                return


def start(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Kill any stale Jarvis process on the port, then start the UI server."""
    _kill_port(port)
    import time; time.sleep(1.0)  # let OS release the port before binding

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        jarvis_state.set_loop(loop)
        config = uvicorn.Config(app, host=host, port=port, log_level="warning", loop="asyncio")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())

    jarvis_state.start_stats_broadcaster()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
