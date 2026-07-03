"""
stt.py — Speech-to-Text pipeline

Primary:  Parakeet TDT 1.1B (NVIDIA NeMo, GPU microservice on localhost:8003)
Fallback: faster-whisper base.en (CPU, loaded lazily on first use)

The Parakeet service is checked once per startup. If it's unreachable or returns
an error, we fall back to Whisper for that call and disable Parakeet for the rest
of the session to avoid repeated timeouts.
"""

import io
import numpy as np
import soundfile as sf
import httpx

import config

# ── Parakeet service config ───────────────────────────────────────────────────

PARAKEET_URL = "http://localhost:8003"

# These flags control which engine is used this session.
# reset_parakeet_check() is called after the service is confirmed ready at startup
# so the next transcribe() call gets a fresh health confirmation.
_parakeet_available: bool = False
_parakeet_checked: bool = False

# Whisper model is loaded lazily — only instantiated if Parakeet is down
_whisper_model = None


def reset_parakeet_check() -> None:
    """
    Force a fresh health-check on the next transcribe() call.
    Called by main.py after _wait_for_stt() confirms the service is ready,
    so the UI shows the correct engine label immediately.
    """
    global _parakeet_checked, _parakeet_available
    _parakeet_checked = False
    _parakeet_available = False


def _check_parakeet() -> bool:
    """
    Check if the Parakeet service is alive. Result is cached after the first call.
    Broadcasts the active engine label to the UI sysinfo panel.
    """
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

        # Push the engine name to the Electron UI
        from core.state import _emit
        _emit({"type": "sysinfo", "stt_engine": label})

    return _parakeet_available


def _transcribe_parakeet(audio: np.ndarray, sample_rate: int) -> str | None:
    """
    Send audio to the Parakeet microservice and return the transcribed text.
    Returns None on any error, which causes the caller to fall back to Whisper.
    """
    try:
        # Encode audio as WAV in memory — no temp files needed
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV")
        buf.seek(0)

        r = httpx.post(
            f"{PARAKEET_URL}/transcribe",
            files={"audio": ("audio.wav", buf, "audio/wav")},
            timeout=15,  # Parakeet is fast on GPU; 15s is a generous limit
        )
        r.raise_for_status()
        return r.json().get("text", "").strip()

    except Exception as e:
        print(f"[STT] Parakeet error: {e} — falling back to Whisper")
        global _parakeet_available
        _parakeet_available = False  # stop hitting Parakeet for the rest of this session
        return None


def _get_whisper():
    """
    Lazy-load the faster-whisper model on first use.
    int8 compute type keeps memory usage low on CPU.
    """
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
    """
    Transcribe audio using faster-whisper locally.
    vad_filter=True suppresses silent segments to reduce hallucinated words.
    """
    model = _get_whisper()
    segments, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> str:
    """
    Main entry point — transcribe audio to text.
    Tries Parakeet first; falls back to Whisper automatically if needed.
    """
    if _check_parakeet():
        result = _transcribe_parakeet(audio, sample_rate)
        if result is not None:
            return result

    # Parakeet unavailable or errored — use local Whisper
    return _transcribe_whisper(audio)
