import httpx
import config

_BASE = config.QBIT_URL.rstrip("/") + "/api/v2"


def _get(path: str, **params) -> dict | list:
    with httpx.Client(base_url=_BASE, timeout=10) as c:
        r = c.post("/auth/login", data={"username": config.QBIT_USER, "password": config.QBIT_PASS})
        if r.status_code not in (200, 204) or "Fails" in r.text:
            raise ConnectionError(f"qBittorrent login failed (HTTP {r.status_code})")
        return c.get(path, params=params or None).json()


def _post(path: str, **data) -> None:
    with httpx.Client(base_url=_BASE, timeout=10) as c:
        r = c.post("/auth/login", data={"username": config.QBIT_USER, "password": config.QBIT_PASS})
        if r.status_code not in (200, 204) or "Fails" in r.text:
            raise ConnectionError(f"qBittorrent login failed (HTTP {r.status_code})")
        c.post(path, data=data)


def _fmt_size(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _fmt_speed(bps: float) -> str:
    return _fmt_size(bps) + "/s"


def _state_label(state: str) -> str:
    return {
        "downloading": "downloading", "stalledDL": "stalled",
        "uploading": "seeding",       "stalledUP": "seeding (stalled)",
        "pausedDL": "paused",         "pausedUP": "paused (complete)",
        "queuedDL": "queued",         "queuedUP": "queued",
        "checkingDL": "checking",     "checkingUP": "checking",
        "error": "error",             "missingFiles": "missing files",
        "moving": "moving",           "unknown": "unknown",
    }.get(state, state)


# ── Actions ───────────────────────────────────────────────────────────────────

def _get_status(filter_state: str = "all") -> str:
    """List torrents with progress, speed, and ETA."""
    transfer = _get("/transfer/info")
    torrents = _get("/torrents/info", filter=filter_state, sort="added_on", reverse=True)

    dl_speed = _fmt_speed(transfer.get("dl_info_speed", 0))
    ul_speed = _fmt_speed(transfer.get("up_info_speed", 0))

    if not torrents:
        return f"No torrents found. Global: down {dl_speed}, up {ul_speed}."

    lines = [f"Global: down {dl_speed}, up {ul_speed}. {len(torrents)} torrent(s):"]
    for t in torrents[:8]:
        pct  = round(t["progress"] * 100)
        eta  = t.get("eta", -1)
        eta_str = f", ETA {eta//3600}h {(eta%3600)//60}m" if 0 < eta < 8640000 else ""
        spd  = f", {_fmt_speed(t['dlspeed'])}" if t["dlspeed"] > 0 else ""
        name = t["name"][:45] + ("…" if len(t["name"]) > 45 else "")
        lines.append(f"  [{_state_label(t['state'])} {pct}%{spd}{eta_str}] {name}")

    if len(torrents) > 8:
        lines.append(f"  … and {len(torrents)-8} more.")
    return "\n".join(lines)


def _pause(name_fragment: str) -> str:
    torrents = _get("/torrents/info")
    matches = [t for t in torrents if name_fragment.lower() in t["name"].lower()]
    if not matches:
        return f"No torrent found matching '{name_fragment}'."
    _post("/torrents/pause", hashes="|".join(t["hash"] for t in matches))
    return f"Paused: {', '.join(t['name'][:40] for t in matches)}."


def _resume(name_fragment: str) -> str:
    torrents = _get("/torrents/info")
    matches = [t for t in torrents if name_fragment.lower() in t["name"].lower()]
    if not matches:
        return f"No torrent found matching '{name_fragment}'."
    _post("/torrents/resume", hashes="|".join(t["hash"] for t in matches))
    return f"Resumed: {', '.join(t['name'][:40] for t in matches)}."


def _delete(name_fragment: str, delete_files: bool = False) -> str:
    torrents = _get("/torrents/info")
    matches = [t for t in torrents if name_fragment.lower() in t["name"].lower()]
    if not matches:
        return f"No torrent found matching '{name_fragment}'."
    _post("/torrents/delete", hashes="|".join(t["hash"] for t in matches), deleteFiles=str(delete_files).lower())
    suffix = " and deleted files from disk" if delete_files else ""
    return f"Removed{suffix}: {', '.join(t['name'][:40] for t in matches)}."


# ── Single tool ───────────────────────────────────────────────────────────────

def qbittorrent(
    action: str,
    name: str = None,
    filter_state: str = "all",
    delete_files: bool = False,
) -> str:
    try:
        if action == "status":
            return _get_status(filter_state)
        elif action == "pause":
            return _pause(name or "")
        elif action == "resume":
            return _resume(name or "")
        elif action == "delete":
            return _delete(name or "", delete_files)
        else:
            return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] qbittorrent({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "qbittorrent",
    "description": (
        "Manage and monitor qBittorrent downloads. "
        "Use 'status' to see what's downloading with speeds and progress. "
        "Use 'pause', 'resume', or 'delete' with a name fragment to target specific torrents. "
        "filter_state can be: all, downloading, seeding, paused, completed, active, inactive, stalled."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "pause", "resume", "delete"],
                "description": "Action to perform.",
            },
            "name": {
                "type": "string",
                "description": "Partial torrent name to match (required for pause, resume, delete).",
            },
            "filter_state": {
                "type": "string",
                "description": "Filter for status: all, downloading, seeding, paused, completed, active, stalled.",
            },
            "delete_files": {
                "type": "boolean",
                "description": "If true, also delete the files from disk when deleting a torrent. Default false.",
            },
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "qbittorrent": lambda **kw: qbittorrent(**kw),
}
