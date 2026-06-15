"""
Jarvis — Voice-activated AI orchestrator
Run:  python main.py
"""

import sys
import time
import subprocess
import os
import urllib.request

from core.wake_word import WakeWordDetector
from core.stt import transcribe
from core.tts import speak
from core.audio import record_until_silence
from core.orchestrator import Orchestrator
from core.state import JarvisState, set_state, broadcast_text
from core.mood import Mood, set_mood, get_mood
from ui.server import start as start_ui

# Silence after TTS playback before the mic re-opens (prevents echo re-trigger)
POST_SPEAK_DELAY = 0.6

ELECTRON_DIR = os.path.join(os.path.dirname(__file__), "electron")
ELECTRON_EXE = r"C:\Program Files\nodejs\node_modules\.bin\electron.cmd"

BOOT_MESSAGE = (
    "JARVIS online. All systems nominal. How may I assist you, sir?"
)


def main() -> None:
    start_ui()

    orchestrator = Orchestrator()
    detector = WakeWordDetector()

    # Launch the Electron UI immediately on boot
    try:
        electron_bin = os.path.join(ELECTRON_DIR, "node_modules", ".bin", "electron.cmd")
        env = os.environ.copy()
        env["PATH"] = r"C:\Program Files\nodejs" + os.pathsep + env.get("PATH", "")
        subprocess.Popen([electron_bin, "."], cwd=ELECTRON_DIR, env=env)
        print("[Jarvis] Electron app launched.")
    except Exception as e:
        print(f"[Jarvis] Could not launch Electron app: {e}")

    set_state(JarvisState.SPEAKING)
    speak(BOOT_MESSAGE)
    time.sleep(POST_SPEAK_DELAY)
    set_state(JarvisState.IDLE)

    try:
        while True:
            set_state(JarvisState.IDLE)
            detector.listen()

            # Bring the Electron window to focus on every wake word
            try:
                urllib.request.urlopen("http://127.0.0.1:8766/focus", timeout=1)
            except Exception:
                pass

            # Record the user's command immediately — no "Yes, sir?" to echo back
            set_state(JarvisState.LISTENING)
            print("[Jarvis] Recording command...")
            audio = record_until_silence()

            set_state(JarvisState.THINKING)
            user_text = transcribe(audio)
            if not user_text:
                continue

            print(f"[User] {user_text}")
            broadcast_text("user", user_text)

            if any(w in user_text.lower() for w in ("goodbye", "shut down", "power off")):
                set_state(JarvisState.SPEAKING)
                speak("Shutting down. Goodbye, sir.")
                break

            # Mood switching — handled before orchestrator
            lower = user_text.lower()
            if "demo mode" in lower or "switch to demo" in lower:
                set_mood(Mood.DEMO)
                set_state(JarvisState.SPEAKING)
                speak("Switching to demo mode, sir. All systems ready for presentation.")
                time.sleep(POST_SPEAK_DELAY)
                continue
            elif "personal mode" in lower or "switch to personal" in lower:
                set_mood(Mood.PERSONAL)
                set_state(JarvisState.SPEAKING)
                speak("Switching to personal mode, sir.")
                time.sleep(POST_SPEAK_DELAY)
                continue
            elif "work mode" in lower or "switch to work" in lower:
                set_mood(Mood.WORK)
                set_state(JarvisState.SPEAKING)
                speak("Switching to work mode, sir.")
                time.sleep(POST_SPEAK_DELAY)
                continue

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
