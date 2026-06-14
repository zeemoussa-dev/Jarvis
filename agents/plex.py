import httpx
import config

_BASE = config.PLEX_URL.rstrip("/")
_HEADERS = {
    "X-Plex-Token": config.PLEX_TOKEN,
    "Accept": "application/json",
}


def _get(path: str, **params) -> dict:
    with httpx.Client(base_url=_BASE, headers=_HEADERS, timeout=15) as c:
        r = c.get(path, params=params or None)
        r.raise_for_status()
        return r.json()


# ── Actions ───────────────────────────────────────────────────────────────────

def _now_playing() -> str:
    data = _get("/status/sessions")
    sessions = data.get("MediaContainer", {}).get("Metadata", [])
    if not sessions:
        return "Nothing is currently playing on Plex."
    lines = [f"{len(sessions)} active stream(s):"]
    for s in sessions:
        title = s.get("title", "Unknown")
        ptype = s.get("type", "")
        grandparent = s.get("grandparentTitle", "")
        user = s.get("User", {}).get("title", "Someone")
        player = s.get("Player", {}).get("title", "")
        state = s.get("Player", {}).get("state", "")
        if grandparent:
            label = f"{grandparent} — {title}"
        else:
            label = title
        lines.append(f"  {user} is {state} {label} ({ptype}) on {player}")
    return "\n".join(lines)


def _libraries() -> str:
    data = _get("/library/sections")
    sections = data.get("MediaContainer", {}).get("Directory", [])
    if not sections:
        return "No libraries found on Plex."
    lines = [f"{len(sections)} libraries:"]
    for s in sections:
        lines.append(f"  {s['title']} ({s['type']})")
    return "\n".join(lines)


def _stats() -> str:
    data = _get("/library/sections")
    sections = data.get("MediaContainer", {}).get("Directory", [])
    if not sections:
        return "No libraries found."
    parts = []
    for s in sections:
        key = s["key"]
        stype = s["type"]
        try:
            detail = _get(f"/library/sections/{key}/all", includeCollections=0)
            count = detail.get("MediaContainer", {}).get("totalSize") or len(
                detail.get("MediaContainer", {}).get("Metadata", [])
            )
            parts.append(f"{s['title']}: {count} {stype}(s)")
        except Exception:
            parts.append(f"{s['title']}: unavailable")
    return "Plex library stats. " + ". ".join(parts) + "."


def _recent(limit: int = 5) -> str:
    data = _get("/library/recentlyAdded", X_Plex_Container_Size=limit)
    items = data.get("MediaContainer", {}).get("Metadata", [])
    if not items:
        return "Nothing recently added to Plex."
    lines = [f"Recently added to Plex:"]
    for item in items[:limit]:
        title = item.get("title", "Unknown")
        grandparent = item.get("grandparentTitle", "")
        label = f"{grandparent} — {title}" if grandparent else title
        added = item.get("addedAt", "")
        lines.append(f"  {label}")
    return "\n".join(lines)


def _on_deck() -> str:
    data = _get("/library/onDeck")
    items = data.get("MediaContainer", {}).get("Metadata", [])
    if not items:
        return "Nothing on deck — no in-progress content."
    lines = ["On deck (in progress):"]
    for item in items[:6]:
        title = item.get("title", "Unknown")
        grandparent = item.get("grandparentTitle", "")
        label = f"{grandparent} — {title}" if grandparent else title
        viewed = item.get("viewOffset", 0)
        duration = item.get("duration", 0)
        if duration:
            pct = round(viewed / duration * 100)
            lines.append(f"  {label} ({pct}% watched)")
        else:
            lines.append(f"  {label}")
    return "\n".join(lines)


def _search(query: str) -> str:
    data = _get("/search", query=query, limit=5)
    items = data.get("MediaContainer", {}).get("Metadata", [])
    if not items:
        return f"No results found for '{query}' on Plex."
    lines = [f"Search results for '{query}':"]
    for item in items:
        title = item.get("title", "Unknown")
        grandparent = item.get("grandparentTitle", "")
        ptype = item.get("type", "")
        label = f"{grandparent} — {title}" if grandparent else title
        lines.append(f"  {label} ({ptype})")
    return "\n".join(lines)


# ── Single tool ───────────────────────────────────────────────────────────────

def plex_manager(action: str, query: str = None, limit: int = 5) -> str:
    try:
        if action == "now_playing":
            return _now_playing()
        elif action == "libraries":
            return _libraries()
        elif action == "stats":
            return _stats()
        elif action == "recent":
            return _recent(limit)
        elif action == "on_deck":
            return _on_deck()
        elif action == "search":
            return _search(query or "")
        else:
            return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] plex_manager({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "plex_manager",
    "description": (
        "Interact with your Plex Media Server. "
        "Use 'now_playing' to see active streams. "
        "Use 'libraries' to list all Plex libraries. "
        "Use 'stats' for item counts per library. "
        "Use 'recent' to see recently added content. "
        "Use 'on_deck' to see in-progress content. "
        "Use 'search' to find movies, shows, or episodes by title."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["now_playing", "libraries", "stats", "recent", "on_deck", "search"],
                "description": "Action to perform.",
            },
            "query": {
                "type": "string",
                "description": "Search query — required for search action.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results for recent (default 5).",
            },
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "plex_manager": lambda **kw: plex_manager(**kw),
}
