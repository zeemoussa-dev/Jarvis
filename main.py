"""
main.py — Jarvis entry point

Startup sequence:
  1. Fire XTTS and Parakeet STT microservices (non-blocking)
  2. Start the FastAPI/WebSocket UI server
  3. Launch the Electron desktop window
  4. Wait for XTTS and Parakeet to finish loading their GPU models
  5. Speak the boot message, then enter the main voice loop

Main voice loop:
  wake word → record → transcribe → orchestrate → speak → repeat
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

# ── Timing constants ──────────────────────────────────────────────────────────

# How long to wait after speaking before the mic reopens.
# Prevents the mic from picking up JARVIS's own voice as a new command (echo re-trigger).
POST_SPEAK_DELAY = 0.6

# ── Service paths & URLs ─────────────────────────────────────────────────────

ELECTRON_DIR    = os.path.join(os.path.dirname(__file__), "electron")
TTS_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "tts_service")
STT_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "stt_service")

# Health-check endpoints — Jarvis polls these to know when the models are ready
TTS_HEALTH_URL = "http://localhost:8002/health"
STT_HEALTH_URL = "http://localhost:8003/health"

# Maximum seconds to wait for each GPU service to load its model at startup.
# XTTS v2 takes ~45s; Parakeet TDT 1.1B takes ~60-90s on first cold start.
TTS_STARTUP_TIMEOUT = 60
STT_STARTUP_TIMEOUT = 90

BOOT_MESSAGE = "JARVIS online. All systems nominal. How may I assist you, sir?"

# ── Noise filter ─────────────────────────────────────────────────────────────

# Short words that the STT model picks up from background noise, mic hiss, or
# the tail end of JARVIS speaking. Silently ignored — nothing is sent to the orchestrator.
_NOISE_WORDS = {
    "mm", "hmm", "uh", "um", "ah", "oh", "hm", "mhm", "mmm", "huh",
    "yeah", "yep", "okay", "ok", "yes", "no", "bye", "hi", "hey",
    "thank you", "thanks", "you", "the", "a", "i",
}


def _is_noise(text: str) -> bool:
    """
    Return True if the transcribed text is a noise artifact that should be ignored.

    Catches two classes of false positives:
      - Ultra-short strings (< 3 chars): almost never a real command
      - Known filler/noise words: 'mm', 'hmm', 'uh', etc.
    """
    cleaned = text.strip().lower().rstrip(".,!?")

    # Anything under 3 characters is definitely not a command
    if len(cleaned) < 3:
        return True

    # Short single-word noise artifacts
    if cleaned in _NOISE_WORDS:
        print(f"[Jarvis] Ignored noise transcription: '{text}'")
        return True

    return False


# ── Service launchers ─────────────────────────────────────────────────────────

def _launch_xtts() -> None:
    """
    Start the XTTS v2 TTS microservice in a new console window.
    Fire-and-forget — does not block. The main thread waits later via _wait_for_xtts().
    Skips launch if the service is already running (safe to call on warm restart).
    """
    try:
        urllib.request.urlopen(TTS_HEALTH_URL, timeout=2)
        print("[Jarvis] XTTS service already running.")
        return
    except Exception:
        pass  # not running — launch it below

    print("[Jarvis] Starting XTTS service...")
    bat = os.path.join(TTS_SERVICE_DIR, "start.bat")
    subprocess.Popen(
        ["cmd.exe", "/c", bat],
        cwd=TTS_SERVICE_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def _launch_stt() -> bool:
    """
    Start the Parakeet TDT 1.1B STT microservice in a new console window.
    Returns True if the service was launched (or already running), False if the
    venv doesn't exist yet (user needs to run stt_service\\setup.bat first).
    """
    try:
        urllib.request.urlopen(STT_HEALTH_URL, timeout=2)
        print("[Jarvis] Parakeet STT service already running.")
        return True
    except Exception:
        pass  # not running — check venv before launching

    bat = os.path.join(STT_SERVICE_DIR, "start.bat")
    if not os.path.exists(os.path.join(STT_SERVICE_DIR, "venv")):
        print("[Jarvis] Parakeet STT venv not found — run stt_service\\setup.bat first. Using Whisper fallback.")
        return False

    print("[Jarvis] Starting Parakeet STT service...")
    subprocess.Popen(
        ["cmd.exe", "/c", bat],
        cwd=STT_SERVICE_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    return True


def _wait_for_xtts() -> None:
    """
    Block until the XTTS service is ready, then reset the TTS health-check flag
    so the next speak() call gets a fresh confirmation.

    Called just before the first speak() — this way the UI starts immediately
    but we don't try to synthesise audio before the GPU model is loaded.
    """
    from core.tts import reset_xtts_check
    deadline = time.time() + TTS_STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            urllib.request.urlopen(TTS_HEALTH_URL, timeout=2)
            print("[Jarvis] XTTS service ready.")
            reset_xtts_check()
            return
        except Exception:
            time.sleep(2)
    print("[Jarvis] XTTS did not respond in time — using Edge TTS fallback.")


def _wait_for_stt() -> None:
    """
    Block until Parakeet is ready, then reset the STT health-check flag.
    Only called when _launch_stt() returned True (i.e. the service was actually started).
    """
    from core.stt import reset_parakeet_check
    deadline = time.time() + STT_STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            urllib.request.urlopen(STT_HEALTH_URL, timeout=2)
            print("[Jarvis] Parakeet STT service ready.")
            reset_parakeet_check()
            return
        except Exception:
            time.sleep(3)
    print("[Jarvis] Parakeet STT did not respond — using Whisper fallback.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Step 1: Start GPU microservices (non-blocking) ────────────────────────
    # Both services open in their own console windows and load models in the background.
    _launch_xtts()
    _stt_launched = _launch_stt()

    # ── Step 2: Start the UI server and Electron window immediately ───────────
    # The UI doesn't need the GPU services to be ready — it shows "CHECKING..."
    # until the health-check confirms which engine is active.
    start_ui()

    orchestrator = Orchestrator()
    detector = WakeWordDetector()

    # Launch Electron in a separate process using the local node_modules binary
    try:
        electron_bin = os.path.join(ELECTRON_DIR, "node_modules", ".bin", "electron.cmd")
        env = os.environ.copy()
        env["PATH"] = r"C:\Program Files\nodejs" + os.pathsep + env.get("PATH", "")
        subprocess.Popen([electron_bin, "."], cwd=ELECTRON_DIR, env=env)
        print("[Jarvis] Electron app launched.")
    except Exception as e:
        print(f"[Jarvis] Could not launch Electron app: {e}")

    # ── Step 3: Wait for GPU services before the first voice response ─────────
    # We deliberately wait here so the boot message uses the correct TTS voice.
    # If we didn't wait, Edge TTS would be used as a fallback on the first greeting.
    _wait_for_xtts()
    if _stt_launched:
        _wait_for_stt()
        from core.stt import _check_parakeet
        _check_parakeet()  # set the flag so the UI shows the correct STT engine on first connect

    # ── Step 4: Speak the boot message ───────────────────────────────────────
    set_state(JarvisState.SPEAKING)
    speak(BOOT_MESSAGE)
    time.sleep(POST_SPEAK_DELAY)
    set_state(JarvisState.IDLE)

    # ── Step 5: Main voice loop ───────────────────────────────────────────────
    try:
        while True:
            set_state(JarvisState.IDLE)

            # Block here until "Hey Jarvis" is detected on the microphone
            detector.listen()

            # Bring the Electron window to the front on every wake word
            try:
                urllib.request.urlopen("http://127.0.0.1:8766/focus", timeout=1)
            except Exception:
                pass  # Electron may not be running — that's fine

            # Record the user's command immediately after wake word
            set_state(JarvisState.LISTENING)
            print("[Jarvis] Recording command...")
            audio = record_until_silence()

            # Transcribe the audio to text
            set_state(JarvisState.THINKING)
            user_text = transcribe(audio)

            # Skip empty transcriptions and known noise artifacts
            if not user_text or _is_noise(user_text):
                continue

            print(f"[User] {user_text}")
            broadcast_text("user", user_text)

            # ── Shutdown command ──────────────────────────────────────────────
            if any(w in user_text.lower() for w in ("goodbye", "shut down", "power off")):
                set_state(JarvisState.SPEAKING)
                speak("Shutting down. Goodbye, sir.")
                break

            # ── Mood switching ────────────────────────────────────────────────
            # Mood changes the briefing style and is broadcast to the UI.
            # Handled before the orchestrator so no API call is made for these.
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

            # ── Orchestrate and respond ───────────────────────────────────────
            # process() returns (text, speech_done). When the local LLM streaming
            # path is used, TTS is called sentence-by-sentence inside process()
            # and speech_done=True — we skip the outer speak() to avoid replaying.
            set_state(JarvisState.THINKING)
            set_state(JarvisState.SPEAKING)  # set early so UI shows SPEAKING during streaming TTS
            response, speech_done = orchestrator.process(user_text, speak_fn=speak)

            broadcast_text("jarvis", response)
            if not speech_done:
                speak(response)
            time.sleep(POST_SPEAK_DELAY)

    except KeyboardInterrupt:
        print("\n[Jarvis] Interrupted by user.")
    finally:
        detector.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
