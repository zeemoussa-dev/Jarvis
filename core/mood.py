from enum import Enum


class Mood(str, Enum):
    PERSONAL = "personal"
    WORK = "work"
    DEMO = "demo"


_current: Mood = Mood.PERSONAL


def get_mood() -> Mood:
    return _current


def set_mood(mood: Mood) -> None:
    global _current
    _current = mood
    print(f"[Mood] Switched to {mood.value.upper()} mode.")
    # Broadcast to UI — import here to avoid circular imports
    from core.state import _emit
    _emit({"type": "mood", "mood": mood.value})
