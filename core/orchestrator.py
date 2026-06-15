from anthropic import Anthropic
from datetime import datetime, timezone, timedelta

import config
from agents import AGENT_TOOLS, dispatch_tool
from core.router import needs_cloud
from core.state import add_local_tokens, add_cloud_tokens
from local_llm import client as local_llm

_DUBAI = timezone(timedelta(hours=4))


def _runtime_system_prompt() -> str:
    now = datetime.now(_DUBAI)
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%I:%M %p")
    return (
        config.SYSTEM_PROMPT
        + f"\n\nCURRENT DATE AND TIME (Dubai, UTC+4): {date_str}, {time_str}. "
        "Use this when resolving relative dates like 'today', 'tomorrow', 'next Friday', 'in an hour', etc. "
        "Always convert to ISO format YYYY-MM-DDTHH:MM:SS when calling create_event."
    )

_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

MAX_TOOL_ROUNDS = 5      # hard cap on back-and-forth tool loops
MAX_HISTORY = 20         # keep only the last N messages to avoid runaway context


class Orchestrator:
    def __init__(self) -> None:
        self.history: list[dict] = []
        self._local_available: bool | None = None  # cached at first call

    def _use_local(self) -> bool:
        """Return True if local LLM is running and this turn doesn't need tools."""
        if self._local_available is None:
            self._local_available = local_llm.is_available()
            if self._local_available:
                print("[Router] Local LLM is online.")
            else:
                print("[Router] Local LLM not detected — using Claude for all requests.")
        return self._local_available

    def process(self, user_input: str) -> str:
        """Route to local LLM or Claude, handle tool calls, return final text."""
        # ── Routing decision ──────────────────────────────────────────────────
        if self._use_local() and not needs_cloud(user_input):
            print("[Router] → Local LLM")
            add_cloud_tokens(0, 0)  # ensure sysinfo fires
            from core.state import _emit
            _emit({"type": "sysinfo", "ai_core": "LOCAL LLAMA"})
            # Build a plain history list for the local model
            plain_history = [
                {"role": m["role"], "content": m["content"]}
                for m in self.history
                if isinstance(m.get("content"), str)
            ]
            try:
                response = local_llm.chat(user_input, history=plain_history)
                add_local_tokens(len(user_input.split()) + len(response.split()))
                self.history.append({"role": "user", "content": user_input})
                self.history.append({"role": "assistant", "content": response})
                self._trim_history()
                return response
            except Exception as exc:
                print(f"[Router] Local LLM error ({exc}), falling back to Claude.")
                self._local_available = False  # stop trying local this session

        # ── Claude (cloud) path ───────────────────────────────────────────────
        print("[Router] → Claude (cloud)")
        from core.state import _emit
        _emit({"type": "sysinfo", "ai_core": "CLAUDE SONNET"})
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        tool_retry_counts: dict[str, int] = {}

        for _ in range(MAX_TOOL_ROUNDS):
            response = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=_runtime_system_prompt(),
                tools=AGENT_TOOLS,
                messages=self.history,
            )

            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            add_cloud_tokens(response.usage.input_tokens, response.usage.output_tokens)
            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn" or not tool_uses:
                return " ".join(text_parts).strip()

            tool_results = []
            for tool_use in tool_uses:
                retries = tool_retry_counts.get(tool_use.name, 0)

                if retries >= 1:
                    print(f"[Orchestrator] Tool '{tool_use.name}' failed twice, aborting.")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"[Unavailable] '{tool_use.name}' could not be completed after retrying. Please give the user a helpful conversational response instead of trying again.",
                        "is_error": True,
                    })
                    continue

                print(f"[Orchestrator] Calling tool: {tool_use.name}")
                result = dispatch_tool(tool_use.name, tool_use.input)

                if str(result).startswith("[Error]"):
                    tool_retry_counts[tool_use.name] = retries + 1
                    print(f"[Orchestrator] Tool '{tool_use.name}' failed, will retry once.")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result),
                })

            self.history.append({"role": "user", "content": tool_results})
            self._trim_history()

        # Exceeded max rounds — ask Claude to wrap up
        self.history.append({
            "role": "user",
            "content": "Please give a brief conversational response summarising what you were able to do.",
        })
        final = _client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=_runtime_system_prompt(),
            messages=self.history,
        )
        text = " ".join(
            b.text for b in final.content if hasattr(b, "text")
        ).strip()
        self.history.append({"role": "assistant", "content": final.content})
        return text

    def reset(self) -> None:
        self.history.clear()

    def _trim_history(self) -> None:
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
