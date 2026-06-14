from datetime import datetime, timezone
import httpx
import config

_BASE = config.RADARR_URL.rstrip("/") + "/api/v3"
_HEADERS = {"X-Api-Key": config.RADARR_KEY}


def _get(path: str, **params) -> dict | list:
    with httpx.Client(base_url=_BASE, headers=_HEADERS, timeout=15) as c:
        r = c.get(path, params=params or None)
        r.raise_for_status()
        return r.json()


def _post(path: str, payload: dict) -> dict:
    with httpx.Client(base_url=_BASE, headers=_HEADERS, timeout=15) as c:
        r = c.post(path, json=payload)
        r.raise_for_status()
        return r.json()


# ── Actions ───────────────────────────────────────────────────────────────────

def _library_stats() -> str:
    movies = _get("/movie")
    total = len(movies)
    downloaded = sum(1 for m in movies if m.get("hasFile"))
    now = datetime.now(timezone.utc)
    this_month = sum(
        1 for m in movies
        if m.get("added") and
        datetime.fromisoformat(m["added"].replace("Z", "+00:00")).year == now.year and
        datetime.fromisoformat(m["added"].replace("Z", "+00:00")).month == now.month
    )
    return (
        f"Your movie library has {total} titles, "
        f"{downloaded} downloaded and available. "
        f"{this_month} movie{'s' if this_month != 1 else ''} added this month."
    )


def _lookup(title: str) -> str:
    """Check if a movie is in the library."""
    movies = _get("/movie")
    matches = [m for m in movies if title.lower() in m["title"].lower()]
    if not matches:
        return f"'{title}' is not in your library."
    lines = []
    for m in matches[:5]:
        status = "downloaded" if m.get("hasFile") else ("monitored" if m.get("monitored") else "not monitored")
        year = m.get("year", "")
        lines.append(f"{m['title']} ({year}) — {status}")
    return "\n".join(lines)


def _search_and_add(title: str) -> str:
    """Search Radarr for a movie and add the first result."""
    results = _get("/movie/lookup", term=title)
    if not results:
        return f"No movies found for '{title}'."

    movie = results[0]
    tmdb_id = movie.get("tmdbId")

    # Check if already in library
    library = _get("/movie")
    if any(m.get("tmdbId") == tmdb_id for m in library):
        return f"{movie['title']} ({movie.get('year', '')}) is already in your library."

    # Get root folder and quality profile
    root_folders = _get("/rootfolder")
    profiles = _get("/qualityprofile")
    if not root_folders or not profiles:
        return "Could not retrieve Radarr configuration (root folder or quality profile)."

    payload = {
        **movie,
        "qualityProfileId": profiles[0]["id"],
        "rootFolderPath": root_folders[0]["path"],
        "monitored": True,
        "addOptions": {"searchForMovie": True},
    }
    _post("/movie", payload)
    return f"Added '{movie['title']} ({movie.get('year', '')})' to your library and started searching for it."


def _queue() -> str:
    """Show what's currently downloading in Radarr."""
    data = _get("/queue", includeMovie=True)
    records = data.get("records", []) if isinstance(data, dict) else []
    if not records:
        return "Nothing is currently downloading in Radarr."
    lines = [f"{len(records)} item(s) in the download queue:"]
    for r in records[:6]:
        title = r.get("movie", {}).get("title", r.get("title", "Unknown"))
        pct = round((1 - r.get("sizeleft", 0) / max(r.get("size", 1), 1)) * 100)
        status = r.get("status", "")
        lines.append(f"  [{pct}% — {status}] {title}")
    return "\n".join(lines)


def _missing(limit: int = 5) -> str:
    """List monitored movies that haven't been downloaded yet."""
    data = _get("/wanted/missing", pageSize=limit, sortKey="title", sortDirection="ascending")
    records = data.get("records", [])
    total = data.get("totalRecords", 0)
    if not records:
        return "No missing movies — your library is complete."
    lines = [f"{total} missing movie(s). Top {len(records)}:"]
    for m in records:
        lines.append(f"  {m['title']} ({m.get('year', '')})")
    return "\n".join(lines)


# ── Single tool ───────────────────────────────────────────────────────────────

def movie_manager(action: str, title: str = None, limit: int = 5) -> str:
    try:
        if action == "stats":
            return _library_stats()
        elif action == "lookup":
            return _lookup(title or "")
        elif action == "add":
            return _search_and_add(title or "")
        elif action == "queue":
            return _queue()
        elif action == "missing":
            return _missing(limit)
        else:
            return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] movie_manager({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "movie_manager",
    "description": (
        "Manage your movie library via Radarr. "
        "Use 'stats' for total movies, how many are downloaded, and how many were added this month. "
        "Use 'lookup' to check if a specific movie is in the library. "
        "Use 'add' to search for a movie by title and add it to the library. "
        "Use 'queue' to see what's currently downloading. "
        "Use 'missing' to list monitored movies not yet downloaded."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["stats", "lookup", "add", "queue", "missing"],
                "description": "Action to perform.",
            },
            "title": {
                "type": "string",
                "description": "Movie title — required for lookup and add.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return for missing (default 5).",
            },
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "movie_manager": lambda **kw: movie_manager(**kw),
}
