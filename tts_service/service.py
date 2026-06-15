"""
XTTS v2 TTS service — runs on Python 3.11 with CUDA
Start:  python service.py
Listens on: http://localhost:8002
"""

import io
import os
import torch
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from TTS.api import TTS
import uvicorn

SPEAKER_WAV = os.path.join(os.path.dirname(__file__), "..", "assets", "Jarvis.mp3")
LANGUAGE    = "en"
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI(title="Jarvis TTS")
tts_model = None


@app.on_event("startup")
def load_model():
    global tts_model
    print(f"[TTS] Loading XTTS v2 on {DEVICE}...")
    tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
    print("[TTS] Model ready.")


class SpeakRequest(BaseModel):
    text: str


@app.post("/speak")
def speak(req: SpeakRequest):
    wav = tts_model.tts(
        text=req.text,
        speaker_wav=SPEAKER_WAV,
        language=LANGUAGE,
    )
    # Convert float list to WAV bytes
    import numpy as np
    import scipy.io.wavfile as wavfile
    arr = np.array(wav, dtype=np.float32)
    buf = io.BytesIO()
    wavfile.write(buf, 24000, arr)
    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")


@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "model": "xtts_v2"}


if __name__ == "__main__":
    uvicorn.run("service:app", host="0.0.0.0", port=8002, reload=False)
