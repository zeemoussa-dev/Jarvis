"""
memory.py — Persistent memory layer using ChromaDB

Stores facts, preferences, and reminders as vector embeddings so Jarvis can
recall them semantically — "what do you know about my gym?" finds the memory
"gym session every day at 6am" even without exact word matches.

Storage: data/chroma/ (SQLite-backed, persists across restarts)
Embeddings: ChromaDB DefaultEmbeddingFunction (onnxruntime, no torch needed)

Two usage modes:
  1. Explicit — user says "remember that X" → memory_agent stores it
  2. Passive  — get_relevant_memories(query) is called on every orchestrator turn
               and injects the top matching memories into Claude's system prompt
               so Jarvis has personal context without the user repeating themselves
"""

from __future__ import annotations
import os
import time
import chromadb
from chromadb.utils import embedding_functions

# ChromaDB persists to disk at this path — survives restarts
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma")

# Lazy-initialised — created on first memory operation, not at import time
_client: chromadb.PersistentClient | None = None
_collection = None


def _get_collection():
    """
    Return the ChromaDB collection, initialising the client on first call.
    Lazy init avoids slowing down startup when memory isn't needed immediately.
    """
    global _client, _collection
    if _collection is not None:
        return _collection

    _client = chromadb.PersistentClient(path=_DB_PATH)

    # DefaultEmbeddingFunction uses onnxruntime (all-MiniLM-L6-v2 model).
    # It runs on CPU — no CUDA required, and it's compatible with Python 3.14.
    ef = embedding_functions.DefaultEmbeddingFunction()

    _collection = _client.get_or_create_collection(
        name="jarvis_memory",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},  # cosine similarity for semantic matching
    )
    print(f"[Memory] ChromaDB ready — {_collection.count()} memories loaded.")
    return _collection


def store(text: str, category: str = "fact") -> str:
    """
    Store a new memory with a timestamp.

    category options:
      "fact"       — a factual statement ("my car is a Land Cruiser")
      "preference" — a user preference ("I prefer concise answers")
      "reminder"   — a time-sensitive note ("call dad on Thursday")
    """
    col = _get_collection()

    # Use millisecond timestamp as a unique ID — simple and sortable
    doc_id = f"mem_{int(time.time() * 1000)}"

    col.add(
        documents=[text],
        metadatas=[{"category": category, "timestamp": int(time.time())}],
        ids=[doc_id],
    )
    return f"Stored ({category}): {text}"


def recall(query: str, n_results: int = 5) -> list[str]:
    """
    Semantic search — find memories most relevant to the query.

    Uses cosine distance (lower = more similar). Memories with distance > 0.8
    are too loosely related and are filtered out to avoid injecting irrelevant context.
    """
    col = _get_collection()
    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[query],
        n_results=min(n_results, col.count()),  # can't request more than what's stored
        include=["documents", "metadatas", "distances"],
    )

    memories = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # 0.8 cosine distance threshold — only return genuinely relevant results
        if dist < 0.8:
            cat = meta.get("category", "fact")
            memories.append(f"[{cat}] {doc}")

    return memories


def forget(query: str) -> str:
    """
    Delete the memory that most closely matches the query.

    Uses a stricter threshold (0.6) than recall to avoid accidentally deleting
    the wrong memory. If no close match is found, nothing is deleted.
    """
    col = _get_collection()
    if col.count() == 0:
        return "No memories stored."

    results = col.query(
        query_texts=[query],
        n_results=1,
        include=["documents", "distances"],
    )

    if not results["ids"][0]:
        return "No matching memory found."

    doc  = results["documents"][0][0]
    dist = results["distances"][0][0]

    # Stricter threshold for deletion — don't delete unless it's a clear match
    if dist > 0.6:
        return f"No close match found for: {query}"

    col.delete(ids=[results["ids"][0][0]])
    return f"Forgotten: {doc}"


def list_all(category: str | None = None) -> list[str]:
    """
    Return all stored memories, optionally filtered by category.
    Used by the 'list' action in memory_agent.py.
    """
    col = _get_collection()
    if col.count() == 0:
        return []

    where = {"category": category} if category else None
    results = col.get(where=where, include=["documents", "metadatas"])

    return [
        f"[{m.get('category', 'fact')}] {d}"
        for d, m in zip(results["documents"], results["metadatas"])
    ]


def get_relevant_memories(query: str, n: int = 4) -> str:
    """
    Called by the orchestrator on every Claude turn.

    Returns a formatted string ready to be appended to the system prompt.
    Returns "" if nothing relevant is found or if ChromaDB errors — never crashes
    the orchestrator; memory is best-effort.

    Example return value:
      RELEVANT MEMORIES ABOUT THE USER:
      - [fact] gym session every day at 6am
      - [preference] prefers concise spoken responses
    """
    try:
        memories = recall(query, n_results=n)
        if not memories:
            return ""
        return "RELEVANT MEMORIES ABOUT THE USER:\n" + "\n".join(f"- {m}" for m in memories)
    except Exception as e:
        print(f"[Memory] Recall error: {e}")
        return ""


def count() -> int:
    """Return the total number of stored memories."""
    return _get_collection().count()
