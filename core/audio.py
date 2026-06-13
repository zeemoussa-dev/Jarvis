import io
import numpy as np
import sounddevice as sd
import soundfile as sf
import pyaudio

_pyaudio = None


def get_pyaudio() -> pyaudio.PyAudio:
    global _pyaudio
    if _pyaudio is None:
        _pyaudio = pyaudio.PyAudio()
    return _pyaudio


def play_audio_bytes(audio_bytes: bytes) -> None:
    """Play raw audio bytes (MP3 or WAV) through the default speaker."""
    buf = io.BytesIO(audio_bytes)
    data, sample_rate = sf.read(buf, dtype="float32")
    sd.play(data, sample_rate, blocking=True)


def record_until_silence(
    sample_rate: int = 16000,
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    max_duration: float = 15.0,
) -> np.ndarray:
    """Record from mic until silence is detected or max_duration is reached."""
    chunk = int(sample_rate * 0.1)  # 100ms chunks
    max_chunks = int(max_duration / 0.1)
    silence_chunks = int(silence_duration / 0.1)

    recorded = []
    silent_count = 0

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        for _ in range(max_chunks):
            data, _ = stream.read(chunk)
            recorded.append(data.copy())
            rms = float(np.sqrt(np.mean(data ** 2)))
            if rms < silence_threshold:
                silent_count += 1
                if silent_count >= silence_chunks and len(recorded) > silence_chunks:
                    break
            else:
                silent_count = 0

    return np.concatenate(recorded, axis=0).flatten()
