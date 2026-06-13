import httpx
import config

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=config.HA_URL.rstrip("/"),
        headers={"Authorization": f"Bearer {config.HA_TOKEN}", "Content-Type": "application/json"},
        verify=False,
        timeout=10,
    )


# ── Internal handlers ─────────────────────────────────────────────────────────

def _list_entities(domain: str) -> str:
    with _client() as c:
        resp = c.get("/api/states")
        resp.raise_for_status()
    entities = [s for s in resp.json() if s["entity_id"].startswith(f"{domain}.")]
    if not entities:
        return f"No entities found in domain '{domain}'."
    return "\n".join(
        f"{s['attributes'].get('friendly_name', s['entity_id'])} ({s['entity_id']}): {s['state']}"
        for s in entities
    )


def _get_state(entity_id: str) -> str:
    with _client() as c:
        resp = c.get(f"/api/states/{entity_id}")
        if resp.status_code == 404:
            return f"Entity '{entity_id}' not found."
        resp.raise_for_status()
    s = resp.json()
    name = s["attributes"].get("friendly_name", entity_id)
    attrs = {k: v for k, v in s["attributes"].items() if k != "friendly_name"}
    attr_str = ", ".join(f"{k}: {v}" for k, v in list(attrs.items())[:6])
    return f"{name} is {s['state']}. {attr_str}"


def _control_light(entity_id: str, action: str, brightness_pct: int = None, color_name: str = None) -> str:
    service = "turn_on" if action.lower() in ("on", "turn_on") else "turn_off"
    payload = {"entity_id": entity_id}
    if service == "turn_on":
        if brightness_pct is not None:
            payload["brightness_pct"] = max(1, min(100, brightness_pct))
        if color_name:
            payload["color_name"] = color_name
    with _client() as c:
        c.post(f"/api/services/light/{service}", json=payload).raise_for_status()
    word = "on" if service == "turn_on" else "off"
    extras = []
    if brightness_pct is not None and service == "turn_on":
        extras.append(f"brightness {brightness_pct}%")
    if color_name and service == "turn_on":
        extras.append(f"colour {color_name}")
    detail = " — " + ", ".join(extras) if extras else ""
    return f"{entity_id} turned {word}{detail}."


def _trigger_automation(entity_id: str) -> str:
    with _client() as c:
        c.post("/api/services/automation/trigger", json={"entity_id": entity_id}).raise_for_status()
    return f"Automation '{entity_id}' triggered."


def _run_script(entity_id: str) -> str:
    script_name = entity_id.replace("script.", "")
    with _client() as c:
        c.post(f"/api/services/script/{script_name}", json={}).raise_for_status()
    return f"Script '{entity_id}' is running."


# ── Single aggregated tool ────────────────────────────────────────────────────

def smart_home(
    action: str,
    entity_id: str = None,
    domain: str = None,
    light_action: str = None,
    brightness_pct: int = None,
    color_name: str = None,
) -> str:
    try:
        if action == "list_entities":
            return _list_entities(domain or "light")
        elif action == "get_state":
            return _get_state(entity_id)
        elif action == "control_light":
            return _control_light(entity_id, light_action or "on", brightness_pct, color_name)
        elif action == "trigger_automation":
            return _trigger_automation(entity_id)
        elif action == "run_script":
            return _run_script(entity_id)
        else:
            return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] smart_home({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "smart_home",
    "description": (
        "Control and query the smart home via Home Assistant. "
        "Use this for anything related to lights, sensors, automations, and scripts. "
        "Actions: 'list_entities' (discover devices in a domain), 'get_state' (read a device), "
        "'control_light' (turn on/off, set brightness or colour), "
        "'trigger_automation' (fire an automation), 'run_script' (execute a script)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_entities", "get_state", "control_light", "trigger_automation", "run_script"],
                "description": "The smart home action to perform.",
            },
            "entity_id": {
                "type": "string",
                "description": "Full HA entity ID, e.g. light.living_room, automation.good_morning.",
            },
            "domain": {
                "type": "string",
                "description": "HA domain for list_entities: light, sensor, switch, automation, script, binary_sensor.",
            },
            "light_action": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Turn the light on or off (required for control_light).",
            },
            "brightness_pct": {
                "type": "integer",
                "description": "Light brightness 1-100% (optional, control_light only).",
            },
            "color_name": {
                "type": "string",
                "description": "Light colour name e.g. 'red', 'warm white', 'blue' (optional, control_light only).",
            },
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "smart_home": lambda **kw: smart_home(**kw),
}
