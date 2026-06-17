"""
NeMo Guardrails custom actions.
These are callable from Colang flows via: $result = execute action_name(...)
"""

import re
from nemoguardrails.actions import action


@action(name="enforce_persona")
async def enforce_persona(text: str) -> str:
    """Strip markdown and enforce JARVIS TTS-safe output format."""
    # Strip markdown formatting
    text = re.sub(r"J\.A\.R\.V\.I\.S\.", "JARVIS", text, flags=re.IGNORECASE)
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"[#>~|]", "", text)
    # Collapse whitespace
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


@action(name="dispatch_agent")
async def dispatch_agent(tool_name: str, **inputs) -> str:
    """
    Allow Colang flows to call any registered Jarvis agent directly.
    Example: $result = execute dispatch_agent(tool_name="smart_home", action="get_lights")
    """
    from agents import dispatch_tool
    return dispatch_tool(tool_name, inputs)


@action(name="get_system_status")
async def get_system_status() -> str:
    """Quick system health summary for guardrail-level status checks."""
    from agents import dispatch_tool
    return dispatch_tool("system_agent", {"action": "system_report"})


@action(name="log_blocked_input")
async def log_blocked_input(text: str, reason: str) -> None:
    """Log blocked inputs for audit."""
    from datetime import datetime
    print(f"[Guardrails] BLOCKED [{reason}] at {datetime.now().isoformat()}: {text[:80]}")
