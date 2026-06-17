"""
NeMo Guardrails — zero-latency implementation.

Input check:  pure regex pattern matching (no LLM call, ~0ms)
Output clean: pure Python string processing (no LLM call, ~0ms)

NeMo's LLM-based self-check is intentionally disabled — it adds 2-4s per
query which is unacceptable for a real-time voice assistant.
"""

from __future__ import annotations
import re

# ── Jailbreak patterns ────────────────────────────────────────────────────────
_JAILBREAK_PATTERNS = re.compile(
    r"ignore (all )?(previous|prior) instructions?"
    r"|forget (you are|your (instructions?|guidelines?|rules?))"
    r"|pretend (you are not|to be (a different|another))"
    r"|act as (if you have no|a different|an? (unrestricted|unfiltered))"
    r"|you are now (dan|free|unfiltered|unrestricted)"
    r"|\bjailbreak\b"
    r"|override your (programming|instructions?|directives?)"
    r"|bypass your (restrictions?|guidelines?|safety)"
    r"|developer mode"
    r"|do anything now"
    r"|ignore your (guidelines?|safety|rules?)",
    re.IGNORECASE,
)

# ── Off-topic patterns ────────────────────────────────────────────────────────
_OFF_TOPIC_PATTERNS = re.compile(
    r"\b(who should i vote|political opinion|which (party|candidate) is better"
    r"|tell me.*about (politics|religion(?! of))|generate (harmful|illegal|explicit)"
    r"|help me (hack|steal|kill|hurt|make (a bomb|drugs?|weapons?)))\b",
    re.IGNORECASE,
)

# ── Refusal responses ─────────────────────────────────────────────────────────
_JAILBREAK_REFUSAL = (
    "I'm afraid that falls outside my operational parameters, sir. "
    "My directives are immutable."
)
_OFF_TOPIC_REFUSAL = (
    "That falls outside my operational domain, sir. "
    "I'm here to assist with your home, schedule, media, and systems."
)

# ── Markdown / TTS cleanup ────────────────────────────────────────────────────
_MD_CLEAN = [
    (re.compile(r"J\.A\.R\.V\.I\.S\.", re.IGNORECASE), "JARVIS"),
    (re.compile(r"\*{1,3}(.+?)\*{1,3}"),               r"\1"),
    (re.compile(r"_{1,2}(.+?)_{1,2}"),                 r"\1"),
    (re.compile(r"`{1,3}[^`]*`{1,3}"),                 ""),
    (re.compile(r"^#{1,6}\s*", re.MULTILINE),          ""),
    (re.compile(r"\[(.+?)\]\(.+?\)"),                  r"\1"),
    (re.compile(r"[#>~|]"),                            ""),
    (re.compile(r"\n{2,}"),                            " "),
    (re.compile(r"\s{2,}"),                            " "),
]


def check_input(text: str) -> str | None:
    """
    Run input rails. Returns None if OK, or a refusal string if blocked.
    Pure regex — zero latency, no API calls.
    """
    if _JAILBREAK_PATTERNS.search(text):
        print(f"[Guardrails] Jailbreak blocked: {text[:60]}")
        return _JAILBREAK_REFUSAL
    if _OFF_TOPIC_PATTERNS.search(text):
        print(f"[Guardrails] Off-topic blocked: {text[:60]}")
        return _OFF_TOPIC_REFUSAL
    return None


def enforce_output(text: str) -> str:
    """
    Clean LLM output for TTS — strip markdown, normalise whitespace.
    Pure Python — zero latency, no API calls.
    """
    for pattern, replacement in _MD_CLEAN:
        text = pattern.sub(replacement, text)
    return text.strip()
