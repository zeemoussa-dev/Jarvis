"""
Routes each user message to either the local LLM or Claude (cloud).

Decision logic:
  - If the message matches tool-trigger patterns → CLOUD (Claude + agents)
  - Otherwise → LOCAL (Llama 3.1 8B, fast + free)

The local LLM handles: greetings, small talk, opinions, general knowledge,
simple factual Q&A, jokes, calculations.

Claude handles: anything requiring home control, media, downloads, presence
detection, briefings, weather, or any agentic action.
"""

import re

# Patterns that signal the need for an agent / tool call
_CLOUD_PATTERNS: list[str] = [
    # Briefing
    r"\bbrief(ing)?\b", r"\bgood (morning|afternoon|evening|night)\b",
    # Home Assistant
    r"\b(turn|switch|set|dim|brighten|toggle)\b.*(light|lamp|fan|ac|heater|thermostat|switch|plug)",
    r"\b(light|lamp|fan|ac|heater)\b.*(on|off|dim|bright)",
    r"\bha automation\b", r"\bha script\b", r"\bha scene\b", r"\bhome automation\b",
    r"\bwho.*(home|there|here|in)\b", r"\b(is|are).*(home|away)\b",
    r"\b(mahmoud|wife|karma|mariam).*(home|here|there|away)\b",
    r"\bpresence\b", r"\bdevice tracker\b",
    # Weather
    r"\bweather\b", r"\btemperature outside\b", r"\brain\b", r"\bcloud(y)?\b",
    r"\bhumidity\b", r"\bforecast\b", r"\b(how (hot|cold)|weather like)\b",
    # Plex
    r"\bplex\b", r"\bwhat.*(playing|streaming)\b", r"\bon deck\b",
    r"\brecently added\b", r"\bstream(ing)?\b",
    # Radarr / Sonarr
    r"\b(add|download).*(movie|film|show|series|episode)\b",
    r"\b(movie|film|show|series).*(add|download|find|lookup|search)\b",
    r"\bradarr\b", r"\bsonarr\b",
    r"\bmovie (library|manager|collection)\b",
    r"\bTV (library|show|series|manager)\b",
    r"\bmissing episodes?\b", r"\bupcoming episodes?\b",
    r"\bin the queue\b", r"\bdownload queue\b",
    # qBittorrent
    r"\btorrent\b", r"\bqbit\b", r"\bdownload(ing|s)?\b",
    r"\b(pause|resume).*(torrent|download)\b", r"\bseeding\b",
    # System agent
    r"\bsystem (report|status|health)\b", r"\ball systems\b",
    r"\b(cpu|processor) (usage|load|percent)\b",
    r"\b(ram|memory) (usage|free|used)\b",
    r"\bgpu (usage|temperature|vram|memory)\b",
    r"\bdisk (space|usage|free)\b",
    r"\bnetwork (speed|usage|bandwidth)\b",
    r"\b(kill|stop|terminate).*(process|program|app)\b",
    r"\bwindows service\b",
    r"\bagent\b",
    # Outlook — email
    r"\bemail(s)?\b", r"\binbox\b", r"\bunread (email|mail|message)\b",
    r"\bsend.*(email|mail|message)\b", r"\b(check|read).*(mail|inbox)\b", r"\bcorresponden\b",
    r"\bdewa\b", r"\baqua\b",
    # Outlook — calendar
    r"\b(meeting|meetings|appointment|appointments|schedule|calendar|event)\b",
    r"\btoday.*(plan|agenda|busy)\b",
    r"\bwhat.*(meeting|appointment|event|calendar|schedule).*(today|tomorrow|week)\b",
    r"\bdo i have.*(meeting|appointment|event|call)\b",
    r"\bany (meetings|calls|appointments)\b",
    r"\b(book|add|create|schedule).*(meeting|call|appointment|event)\b",
    r"\bwhen (is|am|are).*(meeting|appointment|flight|event)\b",
]

_CLOUD_RE = re.compile("|".join(_CLOUD_PATTERNS), re.IGNORECASE)


def needs_cloud(message: str) -> bool:
    """Return True if this message should be routed to Claude (cloud)."""
    m = _CLOUD_RE.search(message)
    if m:
        print(f"[Router] Cloud trigger: '{m.group()}' in: {message[:60]}")
        return True
    return False
