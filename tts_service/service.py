"""
XTTS v2 TTS service — runs on Python 3.11 with CUDA
Start:  python service.py
Listens on: http://localhost:8002
"""

import io
import os
import re
import torch
import numpy as np
import scipy.io.wavfile as wavfile
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from TTS.api import TTS
import uvicorn

SPEAKER_WAV = os.path.join(os.path.dirname(__file__), "..", "assets", "Jarvis.mp3")
LANGUAGE    = "en"
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"
SAMPLE_RATE = 24000

app = FastAPI(title="Jarvis TTS")
tts_model = None


@app.on_event("startup")
def load_model():
    global tts_model
    print(f"[TTS] Loading XTTS v2 on {DEVICE}...")
    tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
    print("[TTS] Model ready.")


def _split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries, keeping chunks ≥ 3 words to avoid tiny fragments."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    merged, buf = [], ""
    for p in parts:
        buf = (buf + " " + p).strip() if buf else p
        if len(buf.split()) >= 6:
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged or [text]


class SpeakRequest(BaseModel):
    text: str


@app.post("/speak")
def speak(req: SpeakRequest):
    """Synthesise full text and return as a single WAV (low-latency for short responses)."""
    wav = tts_model.tts(
        text=req.text,
        speaker_wav=SPEAKER_WAV,
        language=LANGUAGE,
    )
    arr = np.array(wav, dtype=np.float32)
    buf = io.BytesIO()
    wavfile.write(buf, SAMPLE_RATE, arr)
    buf.seek(0)
    return Response(content=buf.read(), media_type="audio/wav")


@app.post("/speak_stream")
def speak_stream(req: SpeakRequest):
    """
    Synthesise sentence-by-sentence and stream WAV chunks so playback starts immediately.
    Client plays each chunk as it arrives rather than waiting for the full response.
    """
    sentences = _split_sentences(req.text)

    def generate():
        for sentence in sentences:
            if not sentence.strip():
                continue
            try:
                wav = tts_model.tts(
                    text=sentence,
                    speaker_wav=SPEAKER_WAV,
                    language=LANGUAGE,
                )
                arr = np.array(wav, dtype=np.float32)
                buf = io.BytesIO()
                wavfile.write(buf, SAMPLE_RATE, arr)
                yield buf.getvalue()
            except Exception as e:
                print(f"[TTS] Sentence synthesis error: {e}")

    return StreamingResponse(generate(), media_type="audio/wav")


@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "model": "xtts_v2"}


if __name__ == "__main__":
    uvicorn.run("service:app", host="0.0.0.0", port=8002, reload=False)
