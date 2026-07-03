"""
memory_agent.py — Claude-callable tool for managing persistent memory

Exposes four actions to Claude via TOOL_SCHEMA:
  store  — save a fact, preference, or reminder to ChromaDB
  recall — semantic search over stored memories
  forget — delete the closest matching memory
  list   — return all memories (optionally filtered by category)

The actual ChromaDB operations live in core/memory.py.
This file is the Claude-facing interface — it defines the tool schema
and translates Claude's structured input into memory operations.

Triggered by voice patterns like:
  "Remember that my gym is at 6am"
  "What do you know about Karma?"
  "Forget that I told you about my car"
  "Show me all my memories"
"""

from __future__ import annotations
from core import memory as mem

# ── Tool schema (sent to Claude as part of AGENT_TOOLS) ──────────────────────
# Claude reads this to know when and how to call this tool.

TOOL_SCHEMA: dict = {
    "name": "memory_manager",
    "description": (
        "Manage persistent memory about the user across sessions. "
        "Use 'store' when the user asks you to remember something. "
        "Use 'recall' to search memories by meaning. "
        "Use 'forget' to delete a specific memory. "
        "Use 'list' to show all stored memories."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["store", "recall", "forget", "list"],
                "description": "Operation to perform.",
            },
            "text": {
                "type": "string",
                "description": "The memory text to store/recall/forget. Required for store, recall, forget.",
            },
            "category": {
                "type": "string",
                "enum": ["fact", "preference", "reminder"],
                "description": "Category for store action. Default: fact.",
            },
        },
        "required": ["action"],
    },
}


def _handle(action: str, text: str = "", category: str = "fact") -> str:
    """
    Dispatch a memory action called by Claude.
    Returns a plain-text string that Claude uses to formulate its spoken response.
    """

    if action == "store":
        if not text:
            return "[Error] 'text' is required for store."
        return mem.store(text, category=category)

    elif action == "recall":
        if not text:
            return "[Error] 'text' is required for recall."
        results = mem.recall(text)
        if not results:
            return "No relevant memories found."
        return "Here is what I remember:\n" + "\n".join(f"- {r}" for r in results)

    elif action == "forget":
        if not text:
            return "[Error] 'text' is required for forget."
        return mem.forget(text)

    elif action == "list":
        # When listing, only filter by category if a non-default category was given
        filter_cat = category if category != "fact" else None
        results = mem.list_all(category=filter_cat)
        if not results:
            return "No memories stored yet."
        return f"Stored memories ({len(results)}):\n" + "\n".join(f"- {r}" for r in results)

    return f"[Error] Unknown action: {action}"


# ── Dispatch table (registered in agents/__init__.py) ────────────────────────

DISPATCH: dict = {
    "memory_manager": lambda **kwargs: _handle(**kwargs),
}
