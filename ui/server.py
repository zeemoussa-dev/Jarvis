"""
FastAPI server that serves the Jarvis UI and streams state via WebSocket.
Runs in a background thread alongside the main audio loop.
"""

import asyncio
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import state as jarvis_state

app = FastAPI()

UI_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(UI_DIR / "index.html")


@app.get("/state")
async def current_state():
    return {"state": jarvis_state.get_state().value}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    q = jarvis_state.subscribe()
    # Send current state immediately on connect
    await websocket.send_text(f'{{"state": "{jarvis_state.get_state().value}"}}')
    try:
        while True:
            payload = await q.get()
            await websocket.send_text(payload)
    except WebSocketDisconnect:
        jarvis_state.unsubscribe(q)
    except Exception:
        jarvis_state.unsubscribe(q)


def start(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the UI server in a daemon thread and open the browser."""

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        jarvis_state.set_loop(loop)
        config = uvicorn.Config(app, host=host, port=port, log_level="warning", loop="asyncio")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Give the server a moment then open the browser
    import time
    time.sleep(1.2)
    webbrowser.open(f"http://{host}:{port}")
