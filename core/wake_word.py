import numpy as np
import pyaudio
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
        self._pa = pyaudio.PyAudio()

    def listen(self) -> None:
        """Block until 'Hey Jarvis' is detected."""
        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=config.MIC_SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.MIC_CHUNK_SIZE,
        )

        print("[Jarvis] Listening for wake word...")
        try:
            while True:
                raw = stream.read(config.MIC_CHUNK_SIZE, exception_on_overflow=False)
                audio_chunk = np.frombuffer(raw, dtype=np.int16)
                self.model.predict(audio_chunk)

                for name, score in self.model.prediction_buffer.items():
                    if score[-1] >= config.WAKE_WORD_THRESHOLD:
                        print(f"[Jarvis] Wake word detected (score={score[-1]:.2f})")
                        stream.stop_stream()
                        return
        finally:
            stream.close()

    def close(self) -> None:
        self._pa.terminate()
