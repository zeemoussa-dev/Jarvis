from anthropic import Anthropic

import config
from agents import AGENT_TOOLS, dispatch_tool

_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)


class Orchestrator:
    def __init__(self) -> None:
        self.history: list[dict] = []

    def process(self, user_input: str) -> str:
        """Send user input to Claude, handle tool calls, return final text response."""
        self.history.append({"role": "user", "content": user_input})

        while True:
            response = _client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=config.SYSTEM_PROMPT,
                tools=AGENT_TOOLS,
                messages=self.history,
            )

            # Collect text and tool uses from the response
            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # Add assistant turn to history
            self.history.append({"role": "assistant", "content": response.content})

            # No tool calls — we have the final answer
            if response.stop_reason == "end_turn" or not tool_uses:
                return " ".join(text_parts).strip()

            # Execute each tool and collect results
            tool_results = []
            for tool_use in tool_uses:
                print(f"[Orchestrator] Calling tool: {tool_use.name}")
                result = dispatch_tool(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result),
                })

            self.history.append({"role": "user", "content": tool_results})

    def reset(self) -> None:
        """Clear conversation history."""
        self.history.clear()
