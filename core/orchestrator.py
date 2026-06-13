from anthropic import Anthropic

import config
from agents import AGENT_TOOLS, dispatch_tool

_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

MAX_TOOL_ROUNDS = 5      # hard cap on back-and-forth tool loops
MAX_HISTORY = 20         # keep only the last N messages to avoid runaway context


class Orchestrator:
    def __init__(self) -> None:
        self.history: list[dict] = []

    def process(self, user_input: str) -> str:
        """Send user input to Claude, handle tool calls, return final text response."""
        self.history.append({"role": "user", "content": user_input})
        self._trim_history()

        tool_retry_counts: dict[str, int] = {}

        for _ in range(MAX_TOOL_ROUNDS):
            response = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=config.SYSTEM_PROMPT,
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

            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn" or not tool_uses:
                return " ".join(text_parts).strip()

            tool_results = []
            for tool_use in tool_uses:
                retries = tool_retry_counts.get(tool_use.name, 0)

                if retries >= 1:
                    # Already failed once — give up on this tool and tell Claude
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
            system=config.SYSTEM_PROMPT,
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
        """Keep history bounded; always preserve the last user message."""
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
