from agents import briefing as _briefing
from agents import home_assistant as _ha

AGENT_TOOLS: list[dict] = [
    _briefing.TOOL_SCHEMA,
    _ha.TOOL_SCHEMA,
]

_DISPATCH: dict[str, callable] = {
    "get_briefing": lambda **_: _briefing.get_briefing(agent_count=len(AGENT_TOOLS)),
    **_ha.DISPATCH,
}


def dispatch_tool(name: str, inputs: dict) -> str:
    handler = _DISPATCH.get(name)
    if handler is None:
        return f"[Error] Unknown tool: {name}"
    try:
        return handler(**inputs)
    except Exception as exc:
        return f"[Error] Tool '{name}' failed: {exc}"
