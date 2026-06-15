import re
import io
import asyncio
import tempfile
import os

import httpx
import numpy as np
import sounddevice as sd
import soundfile as sf
import edge_tts

VOICE = "en-GB-RyanNeural"      # Edge TTS fallback voice
XTTS_URL = "http://localhost:8002"
_xtts_available: bool = False
_xtts_checked: bool = False  # check once per session after first speak


def _clean(text: str) -> str:
    text = re.sub(r"J\.A\.R\.V\.I\.S\.", "JARVIS", text, flags=re.IGNORECASE)
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"[#>~|]", "", text)
    return text.strip()


def _check_xtts() -> bool:
    global _xtts_available, _xtts_checked
    if not _xtts_checked:
        try:
            r = httpx.get(f"{XTTS_URL}/health", timeout=3)
            _xtts_available = r.status_code == 200
        except Exception:
            _xtts_available = False
        _xtts_checked = True
        label = "XTTS V2" if _xtts_available else "EDGE TTS"
        print(f"[TTS] XTTS service {'online' if _xtts_available else 'offline — using Edge TTS fallback'}")
        from core.state import _emit
        _emit({"type": "sysinfo", "tts_engine": label})
    return _xtts_available


def _speak_xtts(text: str) -> bool:
    """Send text to XTTS service and play returned WAV. Returns False on failure."""
    try:
        r = httpx.post(f"{XTTS_URL}/speak", json={"text": text}, timeout=30)
        r.raise_for_status()
        data, sample_rate = sf.read(io.BytesIO(r.content), dtype="float32")
        sd.play(data, sample_rate, blocking=True)
        return True
    except Exception as e:
        print(f"[TTS] XTTS error: {e} — falling back to Edge TTS")
        global _xtts_available
        _xtts_available = False  # stop trying this session
        return False


async def _synthesize_edge(text: str) -> bytes:
    communicate = edge_tts.Communicate(text, VOICE)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def _speak_edge(text: str) -> None:
    audio_bytes = asyncio.run(_synthesize_edge(text))
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name
    try:
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        data, sample_rate = sf.read(tmp_path, dtype="float32")
        sd.play(data, sample_rate, blocking=True)
    finally:
        os.unlink(tmp_path)


def speak(text: str) -> None:
    text = _clean(text)
    print(f"[JARVIS] {text}")

    if _check_xtts():
        if _speak_xtts(text):
            return

    _speak_edge(text)
