from datetime import datetime, timezone, timedelta
import httpx
import config

_BASE = config.SONARR_URL.rstrip("/") + "/api/v3"
_HEADERS = {"X-Api-Key": config.SONARR_KEY}


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
    series = _get("/series")
    total = len(series)
    now = datetime.now(timezone.utc)
    this_month = sum(
        1 for s in series
        if s.get("added") and
        datetime.fromisoformat(s["added"].replace("Z", "+00:00")).year == now.year and
        datetime.fromisoformat(s["added"].replace("Z", "+00:00")).month == now.month
    )
    total_eps = sum(s.get("statistics", {}).get("totalEpisodeCount", 0) for s in series)
    downloaded_eps = sum(s.get("statistics", {}).get("episodeFileCount", 0) for s in series)
    return (
        f"Your TV library has {total} shows with {total_eps} episodes total, "
        f"{downloaded_eps} downloaded. "
        f"{this_month} show{'s' if this_month != 1 else ''} added this month."
    )


def _lookup(title: str) -> str:
    series = _get("/series")
    matches = [s for s in series if title.lower() in s["title"].lower()]
    if not matches:
        return f"'{title}' is not in your TV library."
    lines = []
    for s in matches[:5]:
        stats = s.get("statistics", {})
        eps = stats.get("episodeFileCount", 0)
        total = stats.get("totalEpisodeCount", 0)
        seasons = stats.get("seasonCount", 0)
        status = s.get("status", "unknown")
        lines.append(f"{s['title']} — {seasons} season(s), {eps}/{total} episodes, {status}")
    return "\n".join(lines)


def _search_and_add(title: str) -> str:
    results = _get("/series/lookup", term=title)
    if not results:
        return f"No shows found for '{title}'."

    show = results[0]
    tvdb_id = show.get("tvdbId")

    library = _get("/series")
    if any(s.get("tvdbId") == tvdb_id for s in library):
        return f"{show['title']} is already in your library."

    root_folders = _get("/rootfolder")
    profiles = _get("/qualityprofile")
    if not root_folders or not profiles:
        return "Could not retrieve Sonarr configuration."

    payload = {
        **show,
        "qualityProfileId": profiles[0]["id"],
        "rootFolderPath": root_folders[0]["path"],
        "monitored": True,
        "addOptions": {"searchForMissingEpisodes": True},
    }
    _post("/series", payload)
    return f"Added '{show['title']}' to your TV library and started searching for episodes."


def _queue() -> str:
    data = _get("/queue", includeSeries=True, includeEpisode=True)
    records = data.get("records", []) if isinstance(data, dict) else []
    if not records:
        return "Nothing is currently downloading in Sonarr."
    lines = [f"{len(records)} item(s) in the TV download queue:"]
    for r in records[:6]:
        series = r.get("series", {}).get("title", "Unknown")
        ep = r.get("episode", {})
        ep_str = f"S{ep.get('seasonNumber', 0):02}E{ep.get('episodeNumber', 0):02}" if ep else ""
        pct = round((1 - r.get("sizeleft", 0) / max(r.get("size", 1), 1)) * 100)
        status = r.get("status", "")
        lines.append(f"  [{pct}% — {status}] {series} {ep_str}")
    return "\n".join(lines)


def _missing(limit: int = 5) -> str:
    data = _get("/wanted/missing", pageSize=limit, sortKey="airDateUtc", sortDirection="descending")
    records = data.get("records", [])
    total = data.get("totalRecords", 0)
    if not records:
        return "No missing episodes — all monitored content is downloaded."
    lines = [f"{total} missing episode(s). Most recent {len(records)}:"]
    for ep in records:
        series = ep.get("series", {}).get("title", "Unknown")
        s = ep.get("seasonNumber", 0)
        e = ep.get("episodeNumber", 0)
        title = ep.get("title", "")
        lines.append(f"  {series} S{s:02}E{e:02} — {title}")
    return "\n".join(lines)


def _upcoming(days: int = 7) -> str:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    episodes = _get("/calendar", start=now.date().isoformat(), end=end.date().isoformat(), includeSeries=True)
    if not episodes:
        return f"No episodes airing in the next {days} days."
    lines = [f"{len(episodes)} episode(s) airing in the next {days} days:"]
    for ep in episodes[:8]:
        series = ep.get("series", {}).get("title", "Unknown")
        s = ep.get("seasonNumber", 0)
        e = ep.get("episodeNumber", 0)
        air = ep.get("airDate", "")
        lines.append(f"  {air} — {series} S{s:02}E{e:02}")
    return "\n".join(lines)


# ── Single tool ───────────────────────────────────────────────────────────────

def tv_manager(action: str, title: str = None, limit: int = 5, days: int = 7) -> str:
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
        elif action == "upcoming":
            return _upcoming(days)
        else:
            return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] tv_manager({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "tv_manager",
    "description": (
        "Manage your TV show library via Sonarr. "
        "Use 'stats' for total shows, episodes downloaded, and shows added this month. "
        "Use 'lookup' to check if a show is in the library. "
        "Use 'add' to search for a show and add it. "
        "Use 'queue' to see what's currently downloading. "
        "Use 'missing' to list monitored episodes not yet downloaded. "
        "Use 'upcoming' to see what episodes are airing soon."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["stats", "lookup", "add", "queue", "missing", "upcoming"],
                "description": "Action to perform.",
            },
            "title": {
                "type": "string",
                "description": "Show title — required for lookup and add.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results for missing (default 5).",
            },
            "days": {
                "type": "integer",
                "description": "Days ahead to check for upcoming episodes (default 7).",
            },
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "tv_manager": lambda **kw: tv_manager(**kw),
}
