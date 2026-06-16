from agents import briefing as _briefing
from agents import home_assistant as _ha
from agents import qbittorrent as _qbit
from agents import radarr as _radarr
from agents import sonarr as _sonarr
from agents import plex as _plex
from agents import outlook as _outlook
from agents import system_agent as _sys

AGENT_TOOLS: list[dict] = [
    _briefing.TOOL_SCHEMA,
    _ha.TOOL_SCHEMA,
    _qbit.TOOL_SCHEMA,
    _radarr.TOOL_SCHEMA,
    _sonarr.TOOL_SCHEMA,
    _plex.TOOL_SCHEMA,
    _outlook.TOOL_SCHEMA,
    _sys.TOOL_SCHEMA,
]

_DISPATCH: dict[str, callable] = {
    "get_briefing": lambda **_: _briefing.get_briefing(agent_count=len(AGENT_TOOLS)),
    **_ha.DISPATCH,
    **_qbit.DISPATCH,
    **_radarr.DISPATCH,
    **_sonarr.DISPATCH,
    **_plex.DISPATCH,
    **_outlook.DISPATCH,
    **_sys.DISPATCH,
}


def dispatch_tool(name: str, inputs: dict) -> str:
    handler = _DISPATCH.get(name)
    if handler is None:
        return f"[Error] Unknown tool: {name}"
    try:
        return handler(**inputs)
    except Exception as exc:
        return f"[Error] Tool '{name}' failed: {exc}"
