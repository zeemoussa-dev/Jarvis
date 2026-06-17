"""
STT — Parakeet TDT 1.1B (GPU microservice) with faster-whisper CPU fallback.

Priority:
  1. Parakeet service (localhost:8003) — GPU, ~5x faster, better accuracy
  2. faster-whisper base.en (CPU) — always available as fallback
"""

import io
import numpy as np
import soundfile as sf
import httpx

import config

PARAKEET_URL = "http://localhost:8003"
_parakeet_available: bool = False
_parakeet_checked: bool = False

# Lazy-loaded Whisper fallback
_whisper_model = None


def reset_parakeet_check() -> None:
    global _parakeet_checked, _parakeet_available
    _parakeet_checked = False
    _parakeet_available = False


def _check_parakeet() -> bool:
    global _parakeet_available, _parakeet_checked
    if not _parakeet_checked:
        try:
            r = httpx.get(f"{PARAKEET_URL}/health", timeout=3)
            _parakeet_available = r.status_code == 200
        except Exception:
            _parakeet_available = False
        _parakeet_checked = True
        label = "PARAKEET TDT 1.1B (GPU)" if _parakeet_available else "WHISPER base.en (CPU)"
        print(f"[STT] Using {label}")
        from core.state import _emit
        _emit({"type": "sysinfo", "stt_engine": label})
    return _parakeet_available


def _transcribe_parakeet(audio: np.ndarray, sample_rate: int) -> str | None:
    try:
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV")
        buf.seek(0)
        r = httpx.post(
            f"{PARAKEET_URL}/transcribe",
            files={"audio": ("audio.wav", buf, "audio/wav")},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("text", "").strip()
    except Exception as e:
        print(f"[STT] Parakeet error: {e} — falling back to Whisper")
        global _parakeet_available
        _parakeet_available = False
        return None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print(f"[STT] Loading Whisper '{config.WHISPER_MODEL_SIZE}'...")
        _whisper_model = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device=config.WHISPER_DEVICE,
            compute_type="int8",
        )
    return _whisper_model


def _transcribe_whisper(audio: np.ndarray) -> str:
    model = _get_whisper()
    segments, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> str:
    if _check_parakeet():
        result = _transcribe_parakeet(audio, sample_rate)
        if result is not None:
            return result
    return _transcribe_whisper(audio)
