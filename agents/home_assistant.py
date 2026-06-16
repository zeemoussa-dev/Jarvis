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


# ── Entity queries ────────────────────────────────────────────────────────────

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


def _get_sensor(sensor_type: str) -> str:
    """Read all sensors of a given type (temperature, humidity, motion, door, energy, power)."""
    type_map = {
        "temperature": ("sensor", "temperature"),
        "humidity":    ("sensor", "humidity"),
        "motion":      ("binary_sensor", "motion"),
        "door":        ("binary_sensor", "door"),
        "energy":      ("sensor", "energy"),
        "power":       ("sensor", "power"),
    }
    domain, keyword = type_map.get(sensor_type.lower(), ("sensor", sensor_type.lower()))
    with _client() as c:
        resp = c.get("/api/states")
        resp.raise_for_status()
    matches = [
        s for s in resp.json()
        if s["entity_id"].startswith(f"{domain}.")
        and keyword in s["entity_id"].lower()
    ]
    if not matches:
        return f"No {sensor_type} sensors found."
    lines = []
    for s in matches:
        name = s["attributes"].get("friendly_name", s["entity_id"])
        unit = s["attributes"].get("unit_of_measurement", "")
        lines.append(f"{name}: {s['state']} {unit}".strip())
    return "\n".join(lines)


def _get_history(entity_id: str, hours: int = 24) -> str:
    """Get state history for an entity over the last N hours."""
    from datetime import datetime, timezone, timedelta
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _client() as c:
        resp = c.get(f"/api/history/period/{start}", params={"filter_entity_id": entity_id})
        resp.raise_for_status()
    data = resp.json()
    if not data or not data[0]:
        return f"No history found for '{entity_id}' in the last {hours} hours."
    entries = data[0][-10:]  # last 10 state changes
    lines = [f"Last {len(entries)} state changes for {entity_id}:"]
    for e in entries:
        ts = e.get("last_changed", "")[:16].replace("T", " ")
        lines.append(f"  {ts}: {e['state']}")
    return "\n".join(lines)


# ── Light and switch control ──────────────────────────────────────────────────

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


def _control_switch(entity_id: str, action: str) -> str:
    service = "turn_on" if action.lower() in ("on", "turn_on") else "turn_off"
    with _client() as c:
        c.post(f"/api/services/switch/{service}", json={"entity_id": entity_id}).raise_for_status()
    return f"Switch '{entity_id}' turned {'on' if service == 'turn_on' else 'off'}."


def _set_climate(entity_id: str, temperature: float = None, mode: str = None) -> str:
    """Control AC/climate — set temperature or mode (cool, heat, auto, off)."""
    payload = {"entity_id": entity_id}
    if temperature is not None:
        payload["temperature"] = temperature
    if mode:
        with _client() as c:
            c.post("/api/services/climate/set_hvac_mode", json={"entity_id": entity_id, "hvac_mode": mode}).raise_for_status()
    if temperature is not None:
        with _client() as c:
            c.post("/api/services/climate/set_temperature", json=payload).raise_for_status()
    parts = []
    if temperature:
        parts.append(f"temperature to {temperature}°C")
    if mode:
        parts.append(f"mode to {mode}")
    return f"Climate '{entity_id}' set: {', '.join(parts)}." if parts else f"Climate '{entity_id}' updated."


# ── Automations and scripts ───────────────────────────────────────────────────

def _trigger_automation(entity_id: str) -> str:
    with _client() as c:
        c.post("/api/services/automation/trigger", json={"entity_id": entity_id}).raise_for_status()
    return f"Automation '{entity_id}' triggered."


def _toggle_automation(entity_id: str, enabled: bool) -> str:
    service = "turn_on" if enabled else "turn_off"
    with _client() as c:
        c.post(f"/api/services/automation/{service}", json={"entity_id": entity_id}).raise_for_status()
    return f"Automation '{entity_id}' {'enabled' if enabled else 'disabled'}."


def _run_script(entity_id: str) -> str:
    with _client() as c:
        c.post("/api/services/script/turn_on", json={"entity_id": entity_id}).raise_for_status()
    return f"Script '{entity_id}' is running."


def _activate_scene(entity_id: str) -> str:
    with _client() as c:
        c.post("/api/services/scene/turn_on", json={"entity_id": entity_id}).raise_for_status()
    return f"Scene '{entity_id}' activated."


def _send_notification(message: str, title: str = "JARVIS") -> str:
    """Send a push notification via Home Assistant mobile companion app."""
    with _client() as c:
        c.post("/api/services/notify/notify", json={"message": message, "title": title}).raise_for_status()
    return f"Notification sent: '{message}'."


# ── Presence ─────────────────────────────────────────────────────────────────

def _check_presence(person: str) -> str:
    key = person.lower().strip()
    entity_id = config.HA_PEOPLE.get(key)
    if not entity_id:
        known = ", ".join(config.HA_PEOPLE.keys())
        return f"I don't have a device registered for '{person}'. Known people: {known}."
    with _client() as c:
        resp = c.get(f"/api/states/{entity_id}")
        if resp.status_code == 404:
            return f"Device tracker '{entity_id}' not found in Home Assistant."
        resp.raise_for_status()
    state = resp.json()["state"]
    name = person.capitalize()
    return f"{'Yes' if state == 'home' else 'No'}, {name} is {'home' if state == 'home' else 'not home'}."


def _who_is_home() -> str:
    seen = {}
    with _client() as c:
        for name, entity_id in config.HA_PEOPLE.items():
            if entity_id in seen:
                continue
            seen[entity_id] = True
            resp = c.get(f"/api/states/{entity_id}")
            if resp.status_code != 200:
                continue
            seen[entity_id] = (name.capitalize(), resp.json()["state"] == "home")
    home = [v[0] for v in seen.values() if isinstance(v, tuple) and v[1]]
    away = [v[0] for v in seen.values() if isinstance(v, tuple) and not v[1]]
    parts = []
    if home:
        parts.append(f"{', '.join(home)} {'is' if len(home) == 1 else 'are'} home.")
    if away:
        parts.append(f"{', '.join(away)} {'is' if len(away) == 1 else 'are'} away.")
    return " ".join(parts) if parts else "Could not determine who is home."


def _get_energy() -> str:
    """Fetch power/energy consumption from HA energy sensors."""
    with _client() as c:
        resp = c.get("/api/states")
        resp.raise_for_status()
    states = resp.json()
    power   = [s for s in states if "power" in s["entity_id"] and s["entity_id"].startswith("sensor.")]
    energy  = [s for s in states if "energy" in s["entity_id"] and s["entity_id"].startswith("sensor.")]
    lines = []
    for s in (power + energy)[:8]:
        name = s["attributes"].get("friendly_name", s["entity_id"])
        unit = s["attributes"].get("unit_of_measurement", "")
        lines.append(f"{name}: {s['state']} {unit}".strip())
    return "\n".join(lines) if lines else "No energy sensors found."


# ── Single aggregated tool ────────────────────────────────────────────────────

def smart_home(
    action: str,
    entity_id: str = None,
    domain: str = None,
    light_action: str = None,
    brightness_pct: int = None,
    color_name: str = None,
    person: str = None,
    sensor_type: str = None,
    hours: int = 24,
    temperature: float = None,
    climate_mode: str = None,
    switch_action: str = None,
    enabled: bool = None,
    message: str = None,
    title: str = "JARVIS",
) -> str:
    try:
        match action:
            case "list_entities":    return _list_entities(domain or "light")
            case "get_state":        return _get_state(entity_id)
            case "get_sensor":       return _get_sensor(sensor_type or "temperature")
            case "get_history":      return _get_history(entity_id, hours)
            case "get_energy":       return _get_energy()
            case "control_light":    return _control_light(entity_id, light_action or "on", brightness_pct, color_name)
            case "control_switch":   return _control_switch(entity_id, switch_action or "on")
            case "set_climate":      return _set_climate(entity_id, temperature, climate_mode)
            case "trigger_automation": return _trigger_automation(entity_id)
            case "toggle_automation":  return _toggle_automation(entity_id, enabled if enabled is not None else True)
            case "run_script":       return _run_script(entity_id)
            case "activate_scene":   return _activate_scene(entity_id)
            case "check_presence":   return _check_presence(person or "")
            case "who_is_home":      return _who_is_home()
            case "send_notification": return _send_notification(message or "", title)
            case _:                  return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] smart_home({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "smart_home",
    "description": (
        "Control and query the smart home via Home Assistant. "
        "Actions: list_entities, get_state, get_sensor, get_history, get_energy, "
        "control_light, control_switch, set_climate, trigger_automation, toggle_automation, "
        "run_script, activate_scene, check_presence, who_is_home, send_notification."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_entities", "get_state", "get_sensor", "get_history", "get_energy",
                    "control_light", "control_switch", "set_climate",
                    "trigger_automation", "toggle_automation", "run_script", "activate_scene",
                    "check_presence", "who_is_home", "send_notification",
                ],
                "description": "The smart home action to perform.",
            },
            "entity_id":    {"type": "string",  "description": "Full HA entity ID, e.g. light.living_room."},
            "domain":       {"type": "string",  "description": "HA domain for list_entities: light, sensor, switch, automation, script, climate, binary_sensor."},
            "light_action": {"type": "string",  "enum": ["on", "off"], "description": "Turn light on or off."},
            "brightness_pct": {"type": "integer", "description": "Light brightness 1-100%."},
            "color_name":   {"type": "string",  "description": "Light colour name e.g. 'red', 'warm white'."},
            "switch_action": {"type": "string", "enum": ["on", "off"], "description": "Turn switch on or off."},
            "sensor_type":  {"type": "string",  "description": "Sensor type for get_sensor: temperature, humidity, motion, door, energy, power."},
            "hours":        {"type": "integer", "description": "Hours of history to retrieve (default 24)."},
            "temperature":  {"type": "number",  "description": "Target temperature in °C for set_climate."},
            "climate_mode": {"type": "string",  "description": "HVAC mode: cool, heat, auto, off."},
            "enabled":      {"type": "boolean", "description": "Enable or disable automation (toggle_automation)."},
            "person":       {"type": "string",  "description": "Person name for check_presence: wife, karma, mariam, mahmoud, me."},
            "message":      {"type": "string",  "description": "Notification message text."},
            "title":        {"type": "string",  "description": "Notification title (default: JARVIS)."},
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "smart_home": lambda **kw: smart_home(**kw),
}
