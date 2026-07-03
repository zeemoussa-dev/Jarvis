"""
orchestrator.py — The brain of Jarvis

Every user message goes through here in order:
  1. Guardrails input check  — block jailbreaks / off-topic requests instantly (regex, 0ms)
  2. Routing decision        — local LLM (Nemotron 4B) or Claude Sonnet?
  3. Tool loop (Claude only) — Claude can call agents up to MAX_TOOL_ROUNDS times
  4. Guardrails output clean — strip markdown before TTS reads it aloud

Routing logic (core/router.py decides):
  - Matches a tool-trigger pattern → Claude + agents (home, calendar, media, etc.)
  - No match → Nemotron 4B local LLM (offline, fast, free)
"""

from anthropic import Anthropic
from datetime import datetime, timezone, timedelta
import re
import time

import config
from agents import AGENT_TOOLS, dispatch_tool
from core.router import needs_cloud
from core.state import add_local_tokens, add_cloud_tokens
from core.guardrails import check_input, enforce_output
from local_llm import client as local_llm

# Regex to find sentence boundaries: split after . ! ? when followed by whitespace
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')

# Dubai is UTC+4 — all date/time injection uses this timezone
_DUBAI = timezone(timedelta(hours=4))


def _runtime_system_prompt(user_input: str = "") -> str:
    """
    Build the Claude system prompt for this specific turn.

    Appends two dynamic sections to the static SYSTEM_PROMPT from config.py:
      1. Current Dubai date/time — so 'tomorrow' and 'next Friday' resolve correctly
      2. Relevant memories      — ChromaDB semantic search injects personal context
                                   (e.g. user's preferences, stored facts)
    """
    from core.memory import get_relevant_memories
    now = datetime.now(_DUBAI)
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%I:%M %p")

    prompt = (
        config.SYSTEM_PROMPT
        + f"\n\nCURRENT DATE AND TIME (Dubai, UTC+4): {date_str}, {time_str}. "
        "Use this when resolving relative dates like 'today', 'tomorrow', 'next Friday', 'in an hour', etc. "
        "Always convert to ISO format YYYY-MM-DDTHH:MM:SS when calling create_event."
    )

    # Inject relevant memories from ChromaDB into the prompt so Claude can
    # reference personal facts without the user having to repeat them every session.
    if user_input:
        memories = get_relevant_memories(user_input)
        if memories:
            prompt += f"\n\n{memories}"

    return prompt


# Anthropic client — used for all Claude API calls
_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Maximum number of tool call rounds per user message.
# Prevents runaway loops if Claude keeps calling tools without finishing.
MAX_TOOL_ROUNDS = 5

# How many messages to keep in conversation history.
# Older messages are trimmed to avoid runaway token costs.
MAX_HISTORY = 20


class Orchestrator:
    def __init__(self) -> None:
        # Conversation history shared across turns — Claude needs this for context
        self.history: list[dict] = []

        # Cache whether the local LLM is reachable. Set on first call, reset on error.
        # None = not checked yet, True = online, False = offline or errored
        self._local_available: bool | None = None

    def _use_local(self) -> bool:
        """
        Return True if the local Nemotron 4B service is running and healthy.

        Result is cached after the first check to avoid hitting localhost:8001/health
        on every single message. If the local LLM errors mid-session, the flag is
        set to False and all remaining queries go to Claude for the rest of that session.
        """
        if self._local_available is None:
            self._local_available = local_llm.is_available()
            if self._local_available:
                print("[Router] Local LLM is online.")
                # Broadcast which backend is active to the UI sysinfo panel
                try:
                    import httpx
                    r = httpx.get("http://localhost:8001/health", timeout=3)
                    backend = r.json().get("backend", "transformers")
                    from core.state import _emit
                    _emit({"type": "sysinfo", "llm_backend": backend})
                except Exception:
                    pass
            else:
                print("[Router] Local LLM not detected — using Claude for all requests.")
        return self._local_available

    def _stream_local_with_tts(self, user_input: str, plain_history: list, speak_fn) -> str:
        """
        Stream tokens from the local LLM's /chat_stream SSE endpoint.
        Speak each complete sentence immediately as it forms, so the first word
        of audio plays while the LLM is still generating the rest of the response.
        Returns the full assembled text for history / UI display.
        """
        import httpx
        from core.state import _emit

        buf = ""
        full_text = ""
        first_sentence_logged = False

        t0 = time.time()
        try:
            with httpx.Client(timeout=90) as client:
                with client.stream(
                    "POST",
                    "http://localhost:8001/chat_stream",
                    json={"message": user_input, "history": plain_history, "max_new_tokens": 256},
                    timeout=90,
                ) as resp:
                    resp.raise_for_status()
                    for raw_line in resp.iter_lines():
                        if not raw_line.startswith("data: "):
                            continue
                        token = raw_line[6:].replace("\\n", "\n")
                        if token == "[DONE]":
                            break

                        buf += token
                        full_text += token

                        # Broadcast each token to the UI for live text display
                        _emit({"type": "stream_token", "text": token})

                        # Split on sentence boundaries (.  !  ?) followed by whitespace
                        parts = _SENT_SPLIT.split(buf)
                        if len(parts) > 1:
                            # Speak all complete sentences, keep the trailing fragment
                            for sentence in parts[:-1]:
                                s = enforce_output(sentence.strip())
                                if s and len(s.split()) >= 3:
                                    if not first_sentence_logged:
                                        print(f"[Router] First sentence ready in {time.time()-t0:.1f}s — speaking...")
                                        first_sentence_logged = True
                                    speak_fn(s)
                            buf = parts[-1]  # leftover after last sentence boundary

        except Exception as exc:
            print(f"[Router] Streaming error: {exc}")
            raise

        # Speak any remaining text (last sentence without terminal punctuation)
        if buf.strip():
            s = enforce_output(buf.strip())
            if s:
                speak_fn(s)

        print(f"[Router] Local LLM stream complete in {time.time()-t0:.1f}s")
        return full_text.strip()

    def process(self, user_input: str, speak_fn=None) -> tuple[str, bool]:
        """
        Main entry point — takes raw user text, returns (response_text, speech_done).

        speech_done is True when the local LLM streaming path was used and TTS was
        already called sentence-by-sentence inside this method; main.py should skip
        its outer speak() call in that case.

        Flow:
          guardrails check → route → generate → guardrails clean → return
        """

        # ── 1. Guardrails: block harmful or off-topic inputs ──────────────────
        blocked = check_input(user_input)
        if blocked:
            return enforce_output(blocked), False

        # ── 2. Routing decision ───────────────────────────────────────────────
        _t0 = time.time()

        if self._use_local() and not needs_cloud(user_input):
            # ── Local path: Nemotron 4B (offline, GPU) ────────────────────────
            print("[Router] → Local LLM")
            add_cloud_tokens(0, 0)  # trigger a UI token refresh even on local calls
            from core.state import _emit
            _emit({"type": "sysinfo", "ai_core": "LOCAL NEMOTRON 4B"})

            # Only pass turns with simple string content to the local model —
            # tool-result messages have list content and would confuse it.
            plain_history = [
                {"role": m["role"], "content": m["content"]}
                for m in self.history
                if isinstance(m.get("content"), str)
            ]
            try:
                if speak_fn is not None:
                    # Streaming path — speak each sentence as it arrives
                    response = self._stream_local_with_tts(user_input, plain_history, speak_fn)
                    speech_done = True
                else:
                    response = local_llm.chat(user_input, history=plain_history)
                    speech_done = False

                print(f"[Router] Local LLM responded in {time.time()-_t0:.1f}s — raw: {repr(response[:80])}")
                add_local_tokens(len(user_input.split()) + len(response.split()))
                self.history.append({"role": "user", "content": user_input})
                self.history.append({"role": "assistant", "content": response})
                self._trim_history()
                return enforce_output(response), speech_done
            except Exception as exc:
                # Local LLM timed out or crashed — fall through to Claude for this turn
                print(f"[Router] Local LLM error after {time.time()-_t0:.1f}s ({exc}), falling back to Claude.")
                self._local_available = False

        # ── 3. Claude (cloud) path ────────────────────────────────────────────
        _t0 = time.time()
        print("[Router] → Claude (cloud)")
        from core.state import _emit
        _emit({"type": "sysinfo", "ai_core": "CLAUDE SONNET"})

        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        # Track how many times each tool has been retried.
        # If a tool fails twice, we give Claude a "tool unavailable" result so it
        # can still give the user a helpful answer instead of looping endlessly.
        tool_retry_counts: dict[str, int] = {}

        for _ in range(MAX_TOOL_ROUNDS):
            response = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=_runtime_system_prompt(user_input),
                tools=AGENT_TOOLS,
                messages=self.history,
            )

            # Separate text content from tool call requests in Claude's response
            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            add_cloud_tokens(response.usage.input_tokens, response.usage.output_tokens)
            self.history.append({"role": "assistant", "content": response.content})

            # If Claude finished (no tool calls), return the text response
            if response.stop_reason == "end_turn" or not tool_uses:
                print(f"[Router] Claude responded in {time.time()-_t0:.1f}s")
                return enforce_output(" ".join(text_parts).strip()), False

            # ── Tool call loop ────────────────────────────────────────────────
            tool_results = []
            for tool_use in tool_uses:
                retries = tool_retry_counts.get(tool_use.name, 0)

                if retries >= 1:
                    # Already failed once — give Claude a graceful error so it can wrap up
                    print(f"[Orchestrator] Tool '{tool_use.name}' failed twice, aborting.")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"[Unavailable] '{tool_use.name}' could not be completed after retrying. Please give the user a helpful conversational response instead of trying again.",
                        "is_error": True,
                    })
                    continue

                _tt = time.time()
                print(f"[Orchestrator] Calling tool: {tool_use.name}")
                result = dispatch_tool(tool_use.name, tool_use.input)
                print(f"[Orchestrator] Tool '{tool_use.name}' returned in {time.time()-_tt:.1f}s")

                # If the tool returned an error, mark it for retry on the next round
                if str(result).startswith("[Error]"):
                    tool_retry_counts[tool_use.name] = retries + 1
                    print(f"[Orchestrator] Tool '{tool_use.name}' failed, will retry once.")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result),
                })

            # Feed all tool results back to Claude for the next round
            self.history.append({"role": "user", "content": tool_results})
            self._trim_history()

        # ── MAX_TOOL_ROUNDS exceeded — ask Claude to summarise ────────────────
        # This is a safety net — in practice 5 rounds is enough for any query.
        self.history.append({
            "role": "user",
            "content": "Please give a brief conversational response summarising what you were able to do.",
        })
        final = _client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=_runtime_system_prompt(user_input),
            messages=self.history,
        )
        text = " ".join(
            b.text for b in final.content if hasattr(b, "text")
        ).strip()
        self.history.append({"role": "assistant", "content": final.content})
        return text, False

    def reset(self) -> None:
        """Clear conversation history — called between sessions if needed."""
        self.history.clear()

    def _trim_history(self) -> None:
        """
        Keep only the last MAX_HISTORY messages.
        Prevents conversation context from growing indefinitely and driving up token costs.
        """
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
