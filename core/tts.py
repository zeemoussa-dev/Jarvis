import re
import io
import asyncio
import tempfile
import os
import time

import httpx
import numpy as np
import sounddevice as sd
import soundfile as sf
import edge_tts

VOICE = "en-GB-RyanNeural"      # Edge TTS fallback voice
XTTS_URL = "http://localhost:8002"
_xtts_available: bool = False
_xtts_checked: bool = False


def reset_xtts_check() -> None:
    global _xtts_checked, _xtts_available
    _xtts_checked = False
    _xtts_available = False


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
    """
    Stream XTTS audio sentence-by-sentence — playback starts after the first sentence
    is synthesised instead of waiting for the full response.
    Falls back to /speak (non-streaming) on error.
    """
    try:
        t0 = time.time()
        first_chunk = True
        with httpx.Client(timeout=60) as client:
            with client.stream("POST", f"{XTTS_URL}/speak_stream", json={"text": text}) as r:
                r.raise_for_status()
                buf = b""
                for chunk in r.iter_bytes(chunk_size=8192):
                    buf += chunk
                # Each yielded chunk from /speak_stream is a complete WAV file
                # We need to collect and play them — but since the server streams
                # individual WAV blobs, we detect WAV boundaries by RIFF header
                pos = 0
                while pos < len(buf):
                    if buf[pos:pos+4] != b"RIFF":
                        pos += 1
                        continue
                    # Read chunk size from WAV header (bytes 4-8, little-endian + 8)
                    if pos + 8 > len(buf):
                        break
                    chunk_size = int.from_bytes(buf[pos+4:pos+8], "little") + 8
                    wav_bytes = buf[pos:pos+chunk_size]
                    if len(wav_bytes) < chunk_size:
                        break
                    if first_chunk:
                        print(f"[TTS] First audio chunk ready in {time.time()-t0:.1f}s")
                        first_chunk = False
                    try:
                        data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
                        sd.play(data, sr, blocking=True)
                    except Exception as e:
                        print(f"[TTS] Playback error: {e}")
                    pos += chunk_size
        return True
    except Exception as e:
        print(f"[TTS] XTTS stream error: {e} — trying /speak fallback")
        return _speak_xtts_full(text)


def _speak_xtts_full(text: str) -> bool:
    """Non-streaming fallback — returns complete WAV in one shot."""
    try:
        r = httpx.post(f"{XTTS_URL}/speak", json={"text": text}, timeout=30)
        r.raise_for_status()
        data, sample_rate = sf.read(io.BytesIO(r.content), dtype="float32")
        sd.play(data, sample_rate, blocking=True)
        return True
    except Exception as e:
        print(f"[TTS] XTTS error: {e} — falling back to Edge TTS")
        global _xtts_available
        _xtts_available = False
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


async def synthesize_bytes(text: str) -> bytes:
    """Return raw MP3 bytes for the given text — used by the mobile API."""
    text = _clean(text)
    if not text:
        return b""
    return await _synthesize_edge(text)


def speak(text: str) -> None:
    text = _clean(text)
    if not text:
        print("[TTS] Empty text after cleaning — skipping.")
        return
    print(f"[JARVIS] {text}")

    if _check_xtts():
        if _speak_xtts(text):
            return

    _speak_edge(text)
