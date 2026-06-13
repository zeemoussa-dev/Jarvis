from datetime import datetime

from agents.weather import weather_summary


def get_briefing(agent_count: int) -> str:
    hour = datetime.now().hour

    if 5 <= hour < 12:
        greeting = "Good morning, sir."
    elif 12 <= hour < 17:
        greeting = "Good afternoon, sir."
    elif 17 <= hour < 21:
        greeting = "Good evening, sir."
    else:
        greeting = "Good evening, sir. Working late, I see."

    now = datetime.now().strftime("%I:%M %p").lstrip("0")
    weather = weather_summary()

    return (
        f"{greeting} The time is {now}. "
        f"{weather} "
        f"I currently have {agent_count} agent{'s' if agent_count != 1 else ''} standing by."
    )


TOOL_SCHEMA = {
    "name": "get_briefing",
    "description": (
        "Provide a short status briefing: time-of-day greeting, current time, "
        "live weather conditions, and number of active agents. Call this whenever "
        "the user asks for a briefing, status update, or says things like "
        "'what do we have', 'what's the situation', or 'give me a rundown'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
