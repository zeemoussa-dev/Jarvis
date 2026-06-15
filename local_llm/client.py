"""
Client for the local Llama 3.1 8B service (http://localhost:8001).
Falls back gracefully if the service is not running.
"""

import httpx

LOCAL_LLM_URL = "http://localhost:8001"
_TIMEOUT = 60


def is_available() -> bool:
    try:
        r = httpx.get(f"{LOCAL_LLM_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def chat(message: str, history: list[dict] | None = None) -> str:
    payload = {
        "message": message,
        "history": history or [],
        "max_new_tokens": 256,
    }
    r = httpx.post(f"{LOCAL_LLM_URL}/chat", json=payload, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["response"]
