"""
Parakeet TDT 1.1B ASR service — runs on Python 3.11 with CUDA
Start:  start.bat
Port:   http://localhost:8003
"""

import io
import numpy as np
import torch
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
import soundfile as sf

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_ID = "nvidia/parakeet-tdt-1.1b"

app = FastAPI(title="Jarvis STT — Parakeet TDT 1.1B")
asr_model = None


@app.on_event("startup")
def load_model():
    global asr_model
    print(f"[STT] Loading {MODEL_ID} on {DEVICE}...")
    import nemo.collections.asr as nemo_asr
    asr_model = nemo_asr.models.ASRModel.from_pretrained(MODEL_ID)
    asr_model = asr_model.to(DEVICE)
    asr_model.eval()
    print("[STT] Parakeet model ready.")


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Accept raw WAV audio, return transcription."""
    raw = await audio.read()
    data, sample_rate = sf.read(io.BytesIO(raw), dtype="float32")

    # Parakeet expects 16kHz mono
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sample_rate != 16000:
        import librosa
        data = librosa.resample(data, orig_sr=sample_rate, target_sr=16000)

    with torch.no_grad():
        transcriptions = asr_model.transcribe([data])

    raw_text = transcriptions[0] if transcriptions else ""
    # NeMo returns a Hypothesis object for TDT models; extract .text if needed
    text = raw_text.text if hasattr(raw_text, "text") else str(raw_text)
    return {"text": text.strip()}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "device": DEVICE}


if __name__ == "__main__":
    uvicorn.run("service:app", host="0.0.0.0", port=8003, reload=False)
