"""
router.py — Decides whether a user message needs Claude (cloud) or Nemotron (local).

How it works:
  - A list of regex patterns covers every query that requires a tool/agent call.
  - If any pattern matches → route to Claude + agents (home, email, media, etc.)
  - If nothing matches   → route to local Nemotron 4B (offline, instant, free)

Design goal: cast the net wide enough that tool-requiring queries always hit Claude,
but narrow enough that casual conversation (jokes, general knowledge, small talk)
stays on the local model and never touches the cloud.

To add a new agent: add its trigger patterns to _CLOUD_PATTERNS below, then register
the agent in agents/__init__.py.
"""

import re

# ── Cloud-trigger patterns ────────────────────────────────────────────────────
# Any message matching one of these goes to Claude + the agent tool loop.
# Ordered loosely by agent, but order doesn't matter — all are OR'd together.

_CLOUD_PATTERNS: list[str] = [

    # ── Home Assistant ────────────────────────────────────────────────────────
    # Explicit memory commands: "remember that...", "note that...", "don't forget..."
    r"\b(remember|don't forget|note that|store|save)\b.{0,20}\bthat\b",
    r"\bremember (my|that|this|when|how|where|what)\b",
    # Memory recall/query: "what do you know about me", "do you remember..."
    r"\b(what do you know|what do you remember|what have i told you)\b",
    r"\b(do you remember|have you stored|recall)\b",
    # Forget/delete a memory
    r"\b(forget|delete|remove).*(memory|remember|that i|that my)\b",
    r"\bshow.*m(y|e).*(memories|memory|what you know)\b",

    # ── Briefing Agent ────────────────────────────────────────────────────────
    # Morning/evening briefing: "brief me", "good morning"
    r"\bbrief(ing)?\b",
    r"\bgood (morning|afternoon|evening|night)\b",

    # ── Memory Agent ──────────────────────────────────────────────────────────
    r"\b(remember|don't forget|note that|store|save)\b.{0,20}\bthat\b",
    r"\bremember (my|that|this|when|how|where|what)\b",
    r"\b(what do you know|what do you remember|what have i told you)\b",
    r"\b(do you remember|have you stored|recall)\b",
    r"\b(forget|delete|remove).*(memory|remember|that i|that my)\b",
    r"\bshow.*m(y|e).*(memories|memory|what you know)\b",

    # ── Briefing Agent ────────────────────────────────────────────────────────
    r"\bbrief(ing)?\b",
    r"\bgood (morning|afternoon|evening|night)\b",

    # ── Home Assistant ────────────────────────────────────────────────────────
    # Light/device control: "turn on the lights", "dim the bedroom lamp"
    r"\b(turn|switch|set|dim|brighten|toggle)\b.*(light|lamp|fan|ac|heater|thermostat|switch|plug)",
    r"\b(light|lamp|fan|ac|heater)\b.*(on|off|dim|bright)",
    # HA automations/scenes (using 'ha' prefix to avoid matching casual 'script' or 'scene')
    r"\bha automation\b", r"\bha script\b", r"\bha scene\b", r"\bhome automation\b",
    # Presence detection: "is Mahmoud home?", "who's there?"
    r"\bwho.*(home|there|here|in)\b",
    r"\b(is|are).*(home|away)\b",
    r"\b(mahmoud|wife|karma|mariam).*(home|here|there|away)\b",
    r"\bpresence\b", r"\bdevice tracker\b",

    # ── Weather ───────────────────────────────────────────────────────────────
    r"\bweather\b", r"\btemperature outside\b",
    r"\b(will it|is it going to) rain\b", r"\bweather (today|tomorrow|forecast)\b",
    r"\bhumidity (outside|today)\b", r"\bforecast\b",
    r"\b(how (hot|cold) is it|weather like)\b",

    # ── Plex ─────────────────────────────────────────────────────────────────
    r"\bplex\b",
    r"\bwhat.*(playing|on plex)\b",
    r"\bon deck\b", r"\brecently added\b",
    r"\b(play|watch).*(plex|on tv|on screen)\b",

    # ── Radarr (movies) ───────────────────────────────────────────────────────
    r"\b(add|download).*(movie|film|show|series|episode)\b",
    r"\b(movie|film|show|series).*(add|download|find|lookup|search)\b",
    r"\bradarr\b",
    r"\bmovie (library|manager|collection)\b",
    r"\bget (the movie|the film|the show|the series)\b",

    # ── Sonarr (TV shows) ────────────────────────────────────────────────────
    r"\bsonarr\b",
    r"\bTV (library|show|series|manager)\b",
    r"\bmissing episodes?\b", r"\bupcoming episodes?\b",

    # ── qBittorrent ───────────────────────────────────────────────────────────
    r"\btorrent\b", r"\bqbit\b",
    r"\b(pause|resume).*(torrent|download)\b",
    r"\bseeding\b", r"\bdownload queue\b",
    r"\bhow (much|many).*(download|torrent)\b",

    # ── System Agent ─────────────────────────────────────────────────────────
    r"\bsystem (report|status|health)\b", r"\ball systems\b",
    r"\b(cpu|processor) (usage|load|percent)\b",
    r"\b(ram|memory) (usage|free|used)\b",
    r"\bgpu (usage|temperature|vram|memory)\b",
    r"\bdisk (space|usage|free)\b",
    r"\bnetwork (speed|usage|bandwidth)\b",
    r"\b(kill|stop|terminate).*(process|program|app)\b",
    r"\bwindows service\b",

    # ── Outlook — Email ───────────────────────────────────────────────────────
    r"\bemail(s)?\b", r"\binbox\b", r"\bunread (email|mail|message)\b",
    r"\bsend.*(email|mail)\b",
    r"\b(check|read|any).*(mail|inbox|emails)\b",
    r"\bdewa\b", r"\baqua\b",  # specific senders

    # ── Outlook — Calendar ────────────────────────────────────────────────────
    r"\b(meeting|meetings|appointment|appointments|schedule|calendar|event)\b",
    r"\btoday.*(plan|agenda|busy)\b",
    # "what meetings do I have today/tomorrow" — requires meeting context word to avoid
    # catching generic "what are we doing this week" (which Nemotron handles fine)
    r"\bwhat.*(meeting|appointment|event|calendar|schedule).*(today|tomorrow|week)\b",
    r"\bdo i have.*(meeting|appointment|event|call)\b",
    r"\bany (meetings|calls|appointments)\b",
    r"\b(book|add|create|schedule).*(meeting|call|appointment|event)\b",
    r"\bwhen (is|am|are).*(meeting|appointment|flight|event)\b",
]

# Compile once at import time for maximum runtime speed
_CLOUD_RE = re.compile("|".join(_CLOUD_PATTERNS), re.IGNORECASE)


def needs_cloud(message: str) -> bool:
    """
    Return True if this message requires Claude + agents, False for local Nemotron.

    Logs which pattern triggered the cloud route — useful for debugging when
    a conversational message unexpectedly hits Claude.
    """
    m = _CLOUD_RE.search(message)
    if m:
        print(f"[Router] Cloud trigger: '{m.group()}' in: {message[:60]}")
        return True
    return False
