"""
agents/__init__.py — Agent registry and dispatcher

Every agent in Jarvis follows the same pattern:
  1. A TOOL_SCHEMA dict that describes the tool to Claude (name, description, parameters)
  2. A DISPATCH dict mapping tool name → handler function

To add a new agent:
  1. Create agents/your_agent.py with TOOL_SCHEMA and DISPATCH
  2. Import it here and add to AGENT_TOOLS and _DISPATCH
  3. Add trigger patterns to core/router.py _CLOUD_PATTERNS

AGENT_TOOLS is sent to Claude on every API call so Claude knows which tools exist.
dispatch_tool() is called by the orchestrator when Claude requests a tool call.
"""

from agents import briefing      as _briefing
from agents import home_assistant as _ha
from agents import qbittorrent    as _qbit
from agents import radarr         as _radarr
from agents import sonarr         as _sonarr
from agents import plex           as _plex
from agents import outlook        as _outlook
from agents import system_agent   as _sys
from agents import memory_agent   as _mem

# ── Tool schemas sent to Claude ───────────────────────────────────────────────
# Claude reads these to decide which tool to call and with what parameters.
# Order doesn't affect routing — Claude picks based on description match.

AGENT_TOOLS: list[dict] = [
    _briefing.TOOL_SCHEMA,   # morning/evening briefing
    _ha.TOOL_SCHEMA,         # Home Assistant (lights, switches, scenes, presence)
    _qbit.TOOL_SCHEMA,       # qBittorrent (download management)
    _radarr.TOOL_SCHEMA,     # Radarr (movie management)
    _sonarr.TOOL_SCHEMA,     # Sonarr (TV show management)
    _plex.TOOL_SCHEMA,       # Plex (media server status)
    _outlook.TOOL_SCHEMA,    # Outlook (email + calendar)
    _sys.TOOL_SCHEMA,        # System metrics (CPU, RAM, GPU)
    _mem.TOOL_SCHEMA,        # Memory agent (ChromaDB persistent storage)
]

# ── Tool dispatch table ───────────────────────────────────────────────────────
# Maps tool name → handler function. Must match the "name" field in each TOOL_SCHEMA.

_DISPATCH: dict = {
    "get_briefing":   lambda **_: _briefing.get_briefing(agent_count=len(AGENT_TOOLS)),
    **_ha.DISPATCH,
    **_qbit.DISPATCH,
    **_radarr.DISPATCH,
    **_sonarr.DISPATCH,
    **_plex.DISPATCH,
    **_outlook.DISPATCH,
    **_sys.DISPATCH,
    **_mem.DISPATCH,
}


def dispatch_tool(name: str, inputs: dict) -> str:
    """
    Call the handler for a tool by name.

    Called by the orchestrator when Claude includes a tool_use block in its response.
    Returns a plain-text result string that gets fed back to Claude as a tool_result.
    Returns an [Error] string if the tool name is unknown or the handler raises.
    """
    handler = _DISPATCH.get(name)
    if handler is None:
        return f"[Error] Unknown tool: {name}"
    try:
        return handler(**inputs)
    except Exception as exc:
        return f"[Error] Tool '{name}' failed: {exc}"
