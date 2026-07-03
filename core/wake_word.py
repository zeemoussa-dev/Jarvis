"""
wake_word.py — Always-on wake word detector

Uses openwakeword (ONNX runtime) to listen for "Hey Jarvis" on the microphone.
Runs in a blocking loop inside WakeWordDetector.listen() — the main thread
sits here until the wake word is detected, then returns so the command can be recorded.

openwakeword processes 80ms audio chunks (1280 samples at 16kHz) and scores each
against the loaded model. When the score exceeds WAKE_WORD_THRESHOLD, we return.

Model download happens automatically on first run via openwakeword.utils.download_models().
"""

import queue

import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model

import config


class WakeWordDetector:
    def __init__(self) -> None:
        # Download the "hey_jarvis" ONNX model if not already cached locally
        openwakeword.utils.download_models()
        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",  # faster and Python-version-agnostic vs torch
        )

    def listen(self) -> None:
        """
        Block until "Hey Jarvis" is detected on the microphone.

        Audio is captured in 80ms chunks (required by openwakeword's model).
        A queue decouples the sounddevice callback (which runs in a separate thread)
        from the model inference (which runs on the main thread here).
        """
        q: queue.Queue = queue.Queue()

        def _callback(indata, frames, time, status):
            # Called by sounddevice on a background thread every 80ms.
            # Just enqueue the chunk — never do processing in here.
            q.put(indata.copy())

        print("[Jarvis] Listening for wake word...")
        with sd.InputStream(
            samplerate=config.MIC_SAMPLE_RATE,   # 16000 Hz
            channels=1,
            dtype="int16",
            blocksize=config.MIC_CHUNK_SIZE,      # 1280 samples = 80ms
            callback=_callback,
        ):
            while True:
                chunk = q.get()
                audio_chunk = chunk.flatten()
                self.model.predict(audio_chunk)

                # prediction_buffer holds a rolling window of recent scores per model
                for name, score in self.model.prediction_buffer.items():
                    if score[-1] >= config.WAKE_WORD_THRESHOLD:
                        print(f"[Jarvis] Wake word detected (score={score[-1]:.2f})")
                        return  # exit — main loop takes over

    def close(self) -> None:
        # sounddevice streams are managed by the 'with' context manager in listen(),
        # so there's nothing to clean up here explicitly.
        pass
