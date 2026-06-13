import queue

import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model

import config


class WakeWordDetector:
    def __init__(self) -> None:
        openwakeword.utils.download_models()
        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",
        )

    def listen(self) -> None:
        """Block until 'Hey Jarvis' is detected."""
        q: queue.Queue = queue.Queue()

        def _callback(indata, frames, time, status):
            q.put(indata.copy())

        print("[Jarvis] Listening for wake word...")
        with sd.InputStream(
            samplerate=config.MIC_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=config.MIC_CHUNK_SIZE,
            callback=_callback,
        ):
            while True:
                chunk = q.get()
                audio_chunk = chunk.flatten()
                self.model.predict(audio_chunk)

                for name, score in self.model.prediction_buffer.items():
                    if score[-1] >= config.WAKE_WORD_THRESHOLD:
                        print(f"[Jarvis] Wake word detected (score={score[-1]:.2f})")
                        return

    def close(self) -> None:
        pass  # sounddevice streams are managed via context manager
