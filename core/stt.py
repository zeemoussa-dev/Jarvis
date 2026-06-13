import numpy as np
from faster_whisper import WhisperModel

import config

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"[STT] Loading Whisper model '{config.WHISPER_MODEL_SIZE}'...")
        _model = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device=config.WHISPER_DEVICE,
            compute_type="int8",
        )
    return _model


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> str:
    """Convert a numpy float32 audio array to text."""
    model = _get_model()
    segments, _ = model.transcribe(
        audio,
        language="en",
        beam_size=5,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text
