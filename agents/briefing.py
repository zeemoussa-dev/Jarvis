from datetime import datetime

from agents.weather import weather_summary
from core.mood import get_mood, Mood
from agents.home_assistant import _run_script


def _greeting() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning, sir."
    elif 12 <= hour < 17:
        return "Good afternoon, sir."
    elif 17 <= hour < 21:
        return "Good evening, sir."
    else:
        return "Good evening, sir. Working late, I see."


def _demo_briefing() -> str:
    greeting = _greeting()
    now = datetime.now().strftime("%I:%M %p").lstrip("0")

    # Fire the meeting script silently — don't block if HA is unreachable
    try:
        _run_script("script.office_room_meeting")
    except Exception as e:
        print(f"[Briefing] Could not trigger meeting script: {e}")

    return (
        f"{greeting} The time is {now}. Here is your full morning briefing. "

        f"All systems are online. I currently have 34 agents active and standing by across smart home, "
        f"media, downloads, and intelligence modules. "

        f"Regarding the household — Alina left for work at 9:23 this morning. "

        f"On your health front, your sleep tracker recorded a solid six and a half hours last night, "
        f"with approximately one hour and forty minutes of REM sleep. That puts you in good shape for the day. "

        f"Moving to your inbox — you received emails from DEWA and AQUA Cool this past week. "
        f"I analyzed both utility bills and identified an opportunity with your AQUA Cool account. "
        f"Based on consumption patterns, I believe we can meaningfully reduce that bill by adjusting the AC schedule overnight. "
        f"I have already created an automation in Home Assistant to handle that. "
        f"We will compare the results when your next bill arrives. "

        f"Checking your calendar — you have no meetings scheduled for today. Your schedule is clear. "

        f"On the JARVIS project — development is progressing well. "
        f"We currently have six core agents deployed: Briefing, Smart Home, Movie Manager, TV Manager, Plex, and qBittorrent. "
        f"The hybrid intelligence layer is operational, routing simple requests to the local Llama model "
        f"and complex agentic tasks to Claude. "
        f"Next on the roadmap is expanding the smart home sensor integrations and adding a calendar agent for real-time scheduling. "

        f"Finally, according to your workout program, today is leg day. I would recommend not skipping it, sir. "

        f"I have also gone ahead and prepared your office. The meeting scene in Home Assistant has been activated — "
        f"lighting and environment are set for a productive work session. "

        f"That is your full briefing. What would you like to tackle first?"
    )


def get_briefing(agent_count: int) -> str:
    mood = get_mood()

    if mood == Mood.DEMO:
        return _demo_briefing()

    hour = datetime.now().hour
    greeting = _greeting()
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
        "Provide a status briefing. In demo mode this includes household updates, health data, "
        "email analysis, calendar, and workout plan. In personal and work modes it covers "
        "time, weather, and active agents. Call when the user asks for a briefing, status update, "
        "situation report, or says things like 'what do we have' or 'give me a rundown'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
