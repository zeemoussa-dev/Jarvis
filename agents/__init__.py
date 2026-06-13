"""
Agent registry.

To add a new agent:
1. Create a new file in this directory (e.g., agents/weather.py)
2. Define your tool schema and handler function
3. Import and register them here following the pattern below.
"""

# Tool schemas exposed to the Claude orchestrator
AGENT_TOOLS: list[dict] = [
    # Example (uncomment and fill in when adding agents):
    # {
    #     "name": "get_weather",
    #     "description": "Get the current weather for a given location.",
    #     "input_schema": {
    #         "type": "object",
    #         "properties": {
    #             "location": {"type": "string", "description": "City name or coordinates"},
    #         },
    #         "required": ["location"],
    #     },
    # },
]

# Map tool name → handler function
_DISPATCH: dict[str, callable] = {
    # "get_weather": weather_agent.run,
}


def dispatch_tool(name: str, inputs: dict) -> str:
    handler = _DISPATCH.get(name)
    if handler is None:
        return f"[Error] Unknown tool: {name}"
    try:
        return handler(**inputs)
    except Exception as exc:
        return f"[Error] Tool '{name}' failed: {exc}"
