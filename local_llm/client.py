"""
Client for Ollama local LLM service (http://localhost:11434).
Falls back gracefully if Ollama is not running.
"""

import httpx

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.1"
_TIMEOUT = 60

SYSTEM_PROMPT = (
    "You are JARVIS, a sophisticated AI assistant inspired by Iron Man. "
    "Be concise. Speak in plain sentences — no markdown, no asterisks, no bullet points, no headers. "
    "Address the user as sir."
)


def is_available() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def chat(message: str, history: list[dict] | None = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in (history or [])[-6:]:
        if isinstance(m.get("content"), str):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    r = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()
