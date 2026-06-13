"""
Jarvis — Voice-activated AI orchestrator
Run:  python main.py
"""

import sys
import time

from core.wake_word import WakeWordDetector
from core.stt import transcribe
from core.tts import speak
from core.audio import record_until_silence
from core.orchestrator import Orchestrator
from core.state import JarvisState, set_state, broadcast_text
from ui.server import start as start_ui

# Silence after TTS playback before the mic re-opens (prevents echo re-trigger)
POST_SPEAK_DELAY = 0.6

BOOT_MESSAGE = (
    "J.A.R.V.I.S. online. All systems nominal. How may I assist you, sir?"
)


def main() -> None:
    start_ui()

    orchestrator = Orchestrator()
    detector = WakeWordDetector()

    set_state(JarvisState.SPEAKING)
    speak(BOOT_MESSAGE)
    time.sleep(POST_SPEAK_DELAY)
    set_state(JarvisState.IDLE)

    try:
        missed = 0
        while True:
            set_state(JarvisState.IDLE)
            detector.listen()

            # Record the user's command immediately — no "Yes, sir?" to echo back
            set_state(JarvisState.LISTENING)
            print("[Jarvis] Recording command...")
            audio = record_until_silence()

            set_state(JarvisState.THINKING)
            user_text = transcribe(audio)
            if not user_text:
                if missed == 0:
                    set_state(JarvisState.SPEAKING)
                    speak("I didn't catch that, sir.")
                    time.sleep(POST_SPEAK_DELAY)
                missed += 1
                continue

            missed = 0

            print(f"[User] {user_text}")
            broadcast_text("user", user_text)

            if any(w in user_text.lower() for w in ("goodbye", "shut down", "power off")):
                set_state(JarvisState.SPEAKING)
                speak("Shutting down. Goodbye, sir.")
                break

            set_state(JarvisState.THINKING)
            response = orchestrator.process(user_text)

            broadcast_text("jarvis", response)
            set_state(JarvisState.SPEAKING)
            speak(response)
            time.sleep(POST_SPEAK_DELAY)

    except KeyboardInterrupt:
        print("\n[Jarvis] Interrupted.")
    finally:
        detector.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
