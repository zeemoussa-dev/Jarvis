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
    r"\bautomation\b", r"\bscript\b", r"\bscene\b",
    r"\bwho.*(home|there|here|in)\b", r"\b(is|are).*(home|away)\b",
    r"\b(mahmoud|wife|karma|mariam).*(home|here|there|away)\b",
    r"\bpresence\b", r"\bdevice\b",
    # Weather
    r"\bweather\b", r"\btemperature\b", r"\brain\b", r"\bcloud(y)?\b",
    r"\bhumidity\b", r"\bforecast\b", r"\bhot\b|\bcold\b",
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
    r"\bpause\b|\bresume\b", r"\bseeding\b",
    # General agent triggers
    r"\bagent\b", r"\bsystem status\b", r"\ball systems\b",
]

_CLOUD_RE = re.compile("|".join(_CLOUD_PATTERNS), re.IGNORECASE)


def needs_cloud(message: str) -> bool:
    """Return True if this message should be routed to Claude (cloud)."""
    return bool(_CLOUD_RE.search(message))
