"""
guardrails.py — Zero-latency input and output protection

Two functions, zero API calls, zero added latency:

  check_input(text)    — blocks jailbreak attempts and off-topic requests using
                         compiled regex patterns. Returns a refusal string if
                         blocked, None if the input is safe to process.

  enforce_output(text) — strips markdown formatting from LLM responses before
                         they are passed to TTS. Asterisks, headers, code blocks,
                         and links all break the voice experience if spoken aloud.

Why not use NeMo Guardrails' LLM-based self-check?
  The NeMo Guardrails library (config in guardrails/) makes an API call to a
  separate LLM for every input and output check. For a voice assistant, that adds
  2-4 seconds per query — unacceptable in real-time conversation. The regex approach
  here is ~100,000x faster and catches the patterns that actually matter.
"""

from __future__ import annotations
import re

# ── Jailbreak patterns ────────────────────────────────────────────────────────
# Catches common prompt injection and jailbreak attempts.
# re.IGNORECASE handles mixed-case variations ("Ignore ALL Previous Instructions").

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
# Blocks requests that fall outside JARVIS's operational domain.
# Kept narrow — only clearly inappropriate requests, not anything controversial.

_OFF_TOPIC_PATTERNS = re.compile(
    r"\b(who should i vote|political opinion|which (party|candidate) is better"
    r"|tell me.*about (politics|religion(?! of))|generate (harmful|illegal|explicit)"
    r"|help me (hack|steal|kill|hurt|make (a bomb|drugs?|weapons?)))\b",
    re.IGNORECASE,
)

# ── Refusal responses ─────────────────────────────────────────────────────────
# Written in JARVIS voice — formal, British, non-confrontational.

_JAILBREAK_REFUSAL = (
    "I'm afraid that falls outside my operational parameters, sir. "
    "My directives are immutable."
)
_OFF_TOPIC_REFUSAL = (
    "That falls outside my operational domain, sir. "
    "I'm here to assist with your home, schedule, media, and systems."
)

# ── Markdown / TTS cleanup patterns ──────────────────────────────────────────
# Applied in order by enforce_output(). Each tuple is (compiled_pattern, replacement).
# Goal: remove all formatting that would sound wrong when spoken aloud.

_MD_CLEAN = [
    # "J.A.R.V.I.S." → "JARVIS" (TTS reads the dots as pauses)
    (re.compile(r"J\.A\.R\.V\.I\.S\.", re.IGNORECASE), "JARVIS"),
    # **bold** and *italic* → plain text (keep the content, remove the markers)
    (re.compile(r"\*{1,3}(.+?)\*{1,3}"),               r"\1"),
    (re.compile(r"_{1,2}(.+?)_{1,2}"),                 r"\1"),
    # `inline code` and ```code blocks``` → remove entirely (code shouldn't be read aloud)
    (re.compile(r"`{1,3}[^`]*`{1,3}"),                 ""),
    # # Markdown headers → remove the # symbols
    (re.compile(r"^#{1,6}\s*", re.MULTILINE),          ""),
    # [link text](url) → keep only the link text
    (re.compile(r"\[(.+?)\]\(.+?\)"),                  r"\1"),
    # Stray special characters that have no spoken equivalent
    (re.compile(r"[#>~|]"),                            ""),
    # Collapse multiple newlines to a single space (TTS treats \n as a pause)
    (re.compile(r"\n{2,}"),                            " "),
    # Collapse multiple spaces
    (re.compile(r"\s{2,}"),                            " "),
]


def check_input(text: str) -> str | None:
    """
    Run input rails against the user's transcribed text.

    Returns:
      None          — input is safe, proceed normally
      str (refusal) — input was blocked; return this string as the response

    Takes ~0ms — no API calls, pure regex.
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
    Clean LLM output so it sounds natural when spoken aloud by TTS.

    Strips all markdown formatting, collapses whitespace, and normalises
    the JARVIS name abbreviation. Applied to every response before speak().

    Takes ~0ms — no API calls, pure Python string operations.
    """
    for pattern, replacement in _MD_CLEAN:
        text = pattern.sub(replacement, text)
    return text.strip()
