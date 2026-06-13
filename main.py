"""
Jarvis — Voice-activated AI orchestrator
Run:  python main.py
"""

import sys

from core.wake_word import WakeWordDetector
from core.stt import transcribe
from core.tts import speak
from core.audio import record_until_silence
from core.orchestrator import Orchestrator
from core.state import JarvisState, set_state
from ui.server import start as start_ui


BOOT_MESSAGE = (
    "J.A.R.V.I.S. online. All systems nominal. How may I assist you, sir?"
)


def main() -> None:
    # Start the UI server and open the browser
    start_ui()

    orchestrator = Orchestrator()
    detector = WakeWordDetector()

    set_state(JarvisState.SPEAKING)
    speak(BOOT_MESSAGE)
    set_state(JarvisState.IDLE)

    try:
        while True:
            # Wait for "Hey Jarvis"
            set_state(JarvisState.IDLE)
            detector.listen()

            set_state(JarvisState.SPEAKING)
            speak("Yes, sir?")

            # Record the user's command
            set_state(JarvisState.LISTENING)
            print("[Jarvis] Recording command...")
            audio = record_until_silence()

            # Transcribe speech to text
            set_state(JarvisState.THINKING)
            user_text = transcribe(audio)
            if not user_text:
                set_state(JarvisState.SPEAKING)
                speak("I didn't catch that, sir. Could you repeat?")
                continue

            print(f"[User] {user_text}")

            # Handle exit commands
            if any(w in user_text.lower() for w in ("goodbye", "shut down", "power off")):
                set_state(JarvisState.SPEAKING)
                speak("Shutting down. Goodbye, sir.")
                break

            # Get orchestrator response
            set_state(JarvisState.THINKING)
            response = orchestrator.process(user_text)

            set_state(JarvisState.SPEAKING)
            speak(response)

    except KeyboardInterrupt:
        print("\n[Jarvis] Interrupted.")
    finally:
        detector.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
