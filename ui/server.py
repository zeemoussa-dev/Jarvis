"""
server.py — FastAPI UI server

Serves three screens and a REST data API:
  GET  /          → Screen 1: JARVIS HUD (index.html)
  GET  /screen2   → Screen 2: Media Dashboard
  GET  /screen3   → Screen 3: Home Dashboard
  GET  /api/media → JSON: Plex + qBittorrent + Radarr data (polled by screen2)
  GET  /api/home  → JSON: Home Assistant lights + presence (polled by screen3)
  POST /api/home/toggle → Toggle a HA light or switch entity

WebSocket /ws — real-time state, conversation, stats, sysinfo for all screens.
"""

import asyncio
import json
import threading
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core import state as jarvis_state
from agents import AGENT_TOOLS

app = FastAPI()

UI_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


# ── Screen routes ─────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(UI_DIR / "index.html")

@app.get("/screen2")
async def screen2():
    return FileResponse(UI_DIR / "screen2.html")

@app.get("/screen3")
async def screen3():
    return FileResponse(UI_DIR / "screen3.html")


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/state")
async def current_state():
    return {"state": jarvis_state.get_state().value}

@app.get("/version")
async def version():
    return {"version": config.VERSION, "api_version": config.API_VERSION}


@app.get("/api/media")
async def api_media():
    """
    Aggregate media data for Screen 2.
    Called by screen2.html every 20 seconds via setInterval.
    Returns structured JSON — not the human-readable strings from agents.
    """
    result = {"plex": {}, "downloads": [], "radarr_queue": [], "sonarr_queue": []}

    # ── Plex ─────────────────────────────────────────────────────────────────
    try:
        plex_headers = {"X-Plex-Token": config.PLEX_TOKEN, "Accept": "application/json"}
        async with httpx.AsyncClient(base_url=config.PLEX_URL, headers=plex_headers, timeout=10) as c:
            # Now playing sessions
            r = await c.get("/status/sessions")
            sessions = r.json().get("MediaContainer", {}).get("Metadata", [])
            result["plex"]["sessions"] = [_format_session(s) for s in sessions]

            # Account map: accountID (int) → display name
            # Plex history uses accountID, not a User object
            try:
                acc_r = await c.get("/accounts")
                accounts_raw = acc_r.json().get("MediaContainer", {}).get("Account", [])
                account_map = {a.get("id"): a.get("name", "Unknown") for a in accounts_raw}
            except Exception:
                account_map = {}

            # Recently watched history — who watched what
            r3 = await c.get("/status/sessions/history/all",
                              params={"sort": "viewedAt:desc", "X-Plex-Container-Size": 15})
            history = r3.json().get("MediaContainer", {}).get("Metadata", [])
            result["plex"]["history"] = [_format_history(h, account_map) for h in history[:12]]

            # Recently added — fetch from each section to get proper episode metadata
            r2 = await c.get("/library/recentlyAdded", params={"X-Plex-Container-Size": 10})
            items = r2.json().get("MediaContainer", {}).get("Metadata", [])
            result["plex"]["recent"] = [_format_media_item(i) for i in items[:8]]

            # Library sections + item counts
            r4 = await c.get("/library/sections")
            sections = r4.json().get("MediaContainer", {}).get("Directory", [])
            libs = []
            for s in sections:
                key  = s.get("key", "")
                stype = s.get("type", "")
                count = 0
                try:
                    # X-Plex-Container-Size=0 returns totalSize without loading items
                    cr = await c.get(f"/library/sections/{key}/all",
                                     params={"X-Plex-Container-Size": 0, "X-Plex-Container-Start": 0})
                    count = cr.json().get("MediaContainer", {}).get("totalSize", 0)
                except Exception:
                    pass
                libs.append({"title": s.get("title", ""), "type": stype, "key": key, "count": count})
            result["plex"]["libraries"] = libs
            result["plex"]["library_counts"] = {
                lib["type"]: lib["count"] for lib in libs
            }
    except Exception as e:
        result["plex"]["error"] = str(e)

    # ── qBittorrent ───────────────────────────────────────────────────────────
    try:
        qbit_base = config.QBIT_URL.rstrip("/") + "/api/v2"
        async with httpx.AsyncClient(base_url=qbit_base, timeout=8) as c:
            await c.post("/auth/login", data={"username": config.QBIT_USER, "password": config.QBIT_PASS})
            torrents = (await c.get("/torrents/info", params={"sort": "added_on", "reverse": True})).json()
            transfer = (await c.get("/transfer/info")).json()
            result["downloads"] = [
                {
                    "name": t.get("name", ""),
                    "progress": round(t.get("progress", 0) * 100),
                    "state": t.get("state", ""),
                    "dlspeed": _fmt_speed(t.get("dlspeed", 0)),
                    "size": _fmt_size(t.get("size", 0)),
                    "eta": t.get("eta", 0),
                    "hash": t.get("hash", ""),
                }
                for t in torrents[:8]
            ]
            result["transfer"] = {
                "dl": _fmt_speed(transfer.get("dl_info_speed", 0)),
                "ul": _fmt_speed(transfer.get("up_info_speed", 0)),
            }
    except Exception as e:
        result["downloads_error"] = str(e)

    # ── Radarr queue ──────────────────────────────────────────────────────────
    try:
        radarr_headers = {"X-Api-Key": config.RADARR_KEY}
        async with httpx.AsyncClient(base_url=config.RADARR_URL.rstrip("/") + "/api/v3", headers=radarr_headers, timeout=8) as c:
            q = (await c.get("/queue")).json()
            records = q.get("records", []) if isinstance(q, dict) else q
            result["radarr_queue"] = [
                {
                    "title": r.get("title", r.get("movie", {}).get("title", "Unknown")),
                    "progress": round(r.get("sizeleft", 1) / r.get("size", 1) * 100 - 100) if r.get("size") else 0,
                    "status": r.get("status", ""),
                }
                for r in records[:5]
            ]
    except Exception as e:
        result["radarr_error"] = str(e)

    return JSONResponse(result)


@app.get("/api/home")
async def api_home():
    """
    Home Assistant data for Screen 3.
    Returns all lights, presence trackers, and switches.
    Called by screen3.html every 10 seconds.
    """
    result = {"lights": [], "presence": [], "switches": []}
    try:
        ha_headers = {
            "Authorization": f"Bearer {config.HA_TOKEN}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(base_url=config.HA_URL, headers=ha_headers, timeout=10, verify=False) as c:
            r = await c.get("/api/states")
            states = r.json()

        for s in states:
            eid   = s.get("entity_id", "")
            name  = s.get("attributes", {}).get("friendly_name", eid.split(".")[-1].replace("_", " ").title())
            state = s.get("state", "")
            attrs = s.get("attributes", {})

            if eid.startswith("light."):
                result["lights"].append({
                    "entity_id": eid,
                    "name": name,
                    "state": state,
                    "brightness": attrs.get("brightness"),
                    "rgb_color": attrs.get("rgb_color"),
                })

            elif eid.startswith("device_tracker."):
                # Only include the known people from config.HA_PEOPLE (deduplicated by tracker ID)
                known_trackers = set(config.HA_PEOPLE.values())
                if eid in known_trackers:
                    # Find the display name: skip aliases like "me", "wife"
                    display = next(
                        (k.title() for k, v in config.HA_PEOPLE.items()
                         if v == eid and k not in ("me", "wife")),
                        name
                    )
                    if not any(p["entity_id"] == eid for p in result["presence"]):
                        result["presence"].append({
                            "entity_id": eid,
                            "name": display,
                            "state": state,
                            "source": attrs.get("source_type", ""),
                        })

            elif eid.startswith("switch."):
                result["switches"].append({
                    "entity_id": eid,
                    "name": name,
                    "state": state,
                })

    except Exception as e:
        result["error"] = str(e)

    return JSONResponse(result)


class ToggleRequest(BaseModel):
    entity_id: str
    action: str = "toggle"   # "toggle", "turn_on", "turn_off"


@app.post("/api/home/toggle")
async def api_home_toggle(req: ToggleRequest):
    """
    Toggle or set a HA light/switch from Screen 3.
    Screen 3 sends a POST here when the user clicks a light card.
    """
    try:
        domain = req.entity_id.split(".")[0]
        service = req.action  # toggle / turn_on / turn_off
        ha_headers = {
            "Authorization": f"Bearer {config.HA_TOKEN}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(base_url=config.HA_URL, headers=ha_headers, timeout=8, verify=False) as c:
            r = await c.post(
                f"/api/services/{domain}/{service}",
                json={"entity_id": req.entity_id},
            )
            r.raise_for_status()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ── VPN Control ──────────────────────────────────────────────────────────────

_VPN_HOST     = config.VPN_HOST
_VPN_USER     = config.VPN_USER
_VPN_PASS     = config.VPN_PASS
_VPN_SLOT     = config.VPN_SLOT
_VPN_ENTITY   = "input_boolean.vpn_cloud"
_HA_HEADERS   = lambda: {"Authorization": f"Bearer {config.HA_TOKEN}", "Content-Type": "application/json"}


def _ssh_exec(command: str) -> tuple[str, str]:
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(_VPN_HOST, username=_VPN_USER, password=_VPN_PASS, timeout=8)
    _, stdout, stderr = client.exec_command(command)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    client.close()
    return out, err


async def _ha_set_boolean(entity: str, state: bool):
    service = "turn_on" if state else "turn_off"
    async with httpx.AsyncClient(base_url=config.HA_URL, headers=_HA_HEADERS(), timeout=8) as c:
        await c.post(f"/api/services/input_boolean/{service}", json={"entity_id": entity})


@app.post("/api/vpn/on")
async def vpn_on():
    try:
        import asyncio
        out, err = await asyncio.to_thread(_ssh_exec, f"service start_vpnclient{_VPN_SLOT}")
        await _ha_set_boolean(_VPN_ENTITY, True)
        return {"ok": True, "out": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/vpn/off")
async def vpn_off():
    try:
        import asyncio
        out, err = await asyncio.to_thread(_ssh_exec, f"service stop_vpnclient{_VPN_SLOT}")
        await _ha_set_boolean(_VPN_ENTITY, False)
        return {"ok": True, "out": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/vpn/status")
async def vpn_status():
    try:
        import asyncio
        out, _ = await asyncio.to_thread(_ssh_exec, "nvram get vpnc_state_t")
        # vpnc_state_t is a CSV of states per slot; slot 5 = index 4
        states = out.split(",") if out else []
        is_on = len(states) > (_VPN_SLOT - 1) and states[_VPN_SLOT - 1].strip() in ("2", "1")
        await _ha_set_boolean(_VPN_ENTITY, is_on)
        return {"ok": True, "on": is_on, "raw": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


@app.get("/api/environment")
async def api_environment():
    """
    Environment data for Screen 3:
      - Outdoor weather from Open-Meteo (no API key required)
      - Indoor air quality / temp / humidity from Dyson via Home Assistant
      - Synology NAS storage and system health
    Polled every 60 seconds by screen3.html.
    """
    result: dict = {"weather": {}, "dyson": {}, "nas": {}, "people": []}

    # ── Outdoor weather (Open-Meteo, free, no key) ────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":  config.LOCATION_LAT,
                    "longitude": config.LOCATION_LON,
                    "current":   ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                                  "weather_code,wind_speed_10m,uv_index,precipitation,"
                                  "surface_pressure,visibility"),
                    "hourly":    "temperature_2m,weather_code,precipitation_probability",
                    "wind_speed_unit": "kmh",
                    "timezone":  "auto",
                    "forecast_days": 1,
                },
            )
            data = r.json()
            w = data.get("current", {})
            hourly = data.get("hourly", {})

            # Next 6 hours from current time
            import datetime as _dt
            now_h = _dt.datetime.now().hour
            times  = hourly.get("time", [])
            temps  = hourly.get("temperature_2m", [])
            codes  = hourly.get("weather_code", [])
            precip = hourly.get("precipitation_probability", [])
            forecast = []
            for i, t in enumerate(times):
                h = int(t[11:13]) if len(t) > 10 else 0
                if h >= now_h and len(forecast) < 6:
                    forecast.append({
                        "hour":   f"{h:02d}:00",
                        "temp":   _safe_float(temps[i]) if i < len(temps) else None,
                        "code":   codes[i] if i < len(codes) else 0,
                        "precip": precip[i] if i < len(precip) else 0,
                    })

            result["weather"] = {
                "temp":       _safe_float(w.get("temperature_2m")),
                "feels_like": _safe_float(w.get("apparent_temperature")),
                "humidity":   _safe_float(w.get("relative_humidity_2m")),
                "wind_kmh":   _safe_float(w.get("wind_speed_10m")),
                "uv":         _safe_float(w.get("uv_index")),
                "code":       w.get("weather_code"),
                "precip":     _safe_float(w.get("precipitation")),
                "pressure":   _safe_float(w.get("surface_pressure")),
                "visibility": _safe_float(w.get("visibility")),
                "location":   config.LOCATION_NAME,
                "forecast":   forecast,
            }
    except Exception as e:
        result["weather"]["error"] = str(e)

    # ── Home Assistant: Dyson sensors + known people ──────────────────────────
    try:
        ha_headers = {
            "Authorization": f"Bearer {config.HA_TOKEN}",
            "Content-Type":  "application/json",
        }
        async with httpx.AsyncClient(base_url=config.HA_URL, headers=ha_headers,
                                     timeout=10, verify=False) as c:
            states = (await c.get("/api/states")).json()

        dyson: dict = {}
        known_trackers = set(config.HA_PEOPLE.values())
        seen_trackers: set = set()

        for s in states:
            eid   = s.get("entity_id", "")
            attrs = s.get("attributes", {})
            state = s.get("state", "")
            fname = attrs.get("friendly_name", eid.split(".")[-1])
            dc    = attrs.get("device_class", "")
            unit  = attrs.get("unit_of_measurement", "")

            # Dyson sensors — match by device_class or entity/name keywords
            if eid.startswith("sensor."):
                key = (fname + " " + eid).lower()
                is_dyson = "dyson" in key

                # Also catch by device_class regardless of brand
                if is_dyson or dc in ("pm25", "pm10", "volatile_organic_compounds",
                                       "nitrogen_dioxide", "aqi", "humidity", "temperature"):
                    val = _safe_float(state)
                    if dc == "pm25" or "pm2" in key:
                        dyson.setdefault("pm25", val)
                    elif dc == "pm10" or "pm10" in key:
                        dyson.setdefault("pm10", val)
                    elif dc == "volatile_organic_compounds" or "voc" in key:
                        dyson.setdefault("voc", val)
                    elif dc == "nitrogen_dioxide" or "nox" in key or "no2" in key:
                        dyson.setdefault("nox", val)
                    elif dc == "humidity" and is_dyson:
                        dyson.setdefault("humidity", val)
                    elif dc == "temperature" and is_dyson:
                        dyson.setdefault("temp", val)
                    elif "air_quality" in key or dc == "aqi" or "aqi" in key:
                        dyson.setdefault("aqi", val)
                    elif "formaldehyde" in key or "hcho" in key:
                        dyson.setdefault("hcho", val)

            # Known people only
            if eid.startswith("device_tracker.") and eid in known_trackers and eid not in seen_trackers:
                seen_trackers.add(eid)
                display = next(
                    (k.title() for k, v in config.HA_PEOPLE.items()
                     if v == eid and k not in ("me", "wife")),
                    fname
                )
                result["people"].append({
                    "name":      display,
                    "state":     state,
                    "entity_id": eid,
                })

        result["dyson"] = dyson

    except Exception as e:
        result["ha_error"] = str(e)

    # ── Synology NAS ──────────────────────────────────────────────────────────
    if config.NAS_URL and config.NAS_USER:
        try:
            nas_base = config.NAS_URL.rstrip("/") + "/webapi"
            async with httpx.AsyncClient(base_url=nas_base, timeout=12, verify=False) as c:
                # Step 1: authenticate
                login = (await c.get("/auth.cgi", params={
                    "api": "SYNO.API.Auth", "version": "6", "method": "login",
                    "account": config.NAS_USER, "passwd": config.NAS_PASS, "format": "sid",
                })).json()
                sid = login.get("data", {}).get("sid", "")

                if sid:
                    # Storage volumes
                    vol_data = (await c.get("/entry.cgi", params={
                        "api": "SYNO.Storage.CGI.Volume", "method": "list",
                        "version": "1", "_sid": sid,
                    })).json().get("data", {})
                    vols = vol_data.get("volumes", [])

                    # System info (model, uptime, temp)
                    sys_data = (await c.get("/entry.cgi", params={
                        "api": "SYNO.Core.System", "method": "info",
                        "version": "1", "_sid": sid,
                    })).json().get("data", {})

                    # CPU + RAM utilization
                    util_data = (await c.get("/entry.cgi", params={
                        "api": "SYNO.Core.System.Utilization", "method": "get",
                        "version": "1", "_sid": sid,
                    })).json().get("data", {})

                    result["nas"] = {
                        "model":    sys_data.get("model", "Synology NAS"),
                        "temp":     sys_data.get("temperature"),
                        "uptime":   sys_data.get("uptime", 0),
                        "cpu_pct":  util_data.get("cpu", {}).get("user_load", 0),
                        "ram_pct":  util_data.get("memory", {}).get("real_usage", 0),
                        "volumes": [
                            {
                                "name":     v.get("display_name") or v.get("volume_path", f"Volume {i+1}"),
                                "total_gb": round(v.get("size", {}).get("total", 0) / 1024**3, 1),
                                "used_gb":  round(
                                    (v.get("size", {}).get("total", 0) - v.get("size", {}).get("avail", 0))
                                    / 1024**3, 1
                                ),
                                "used_pct": round(
                                    (1 - v.get("size", {}).get("avail", 1) /
                                     max(v.get("size", {}).get("total", 1), 1)) * 100
                                ),
                                "status":   v.get("status", "normal"),
                            }
                            for i, v in enumerate(vols)
                        ],
                    }

                    # Logout cleanly
                    await c.get("/auth.cgi", params={
                        "api": "SYNO.API.Auth", "version": "1",
                        "method": "logout", "_sid": sid,
                    })

        except Exception as e:
            result["nas"]["error"] = str(e)

    return JSONResponse(result)


# ── Mobile: audio transcribe + command ───────────────────────────────────────

class CommandRequest(BaseModel):
    text: str


@app.post("/api/command")
async def api_command(req: CommandRequest, token: str = Query(default="")):
    """Accept a text command from mobile, process it, and return audio bytes for playback on device."""
    if config.WS_TOKEN and token != config.WS_TOKEN:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")

    import base64
    from core.orchestrator import Orchestrator
    from core.state import broadcast_text
    from core.tts import synthesize_bytes

    if not hasattr(api_command, "_orch"):
        api_command._orch = Orchestrator()

    def _process():
        broadcast_text("user", req.text)
        # No speak_fn — mobile handles its own audio; PC stays quiet for mobile commands
        response, _ = api_command._orch.process(req.text)
        broadcast_text("jarvis", response)
        return response

    response = await asyncio.get_event_loop().run_in_executor(None, _process)
    audio_bytes = await synthesize_bytes(response)
    return {
        "ok": True,
        "response": response,
        "audio_b64": base64.b64encode(audio_bytes).decode(),
    }


@app.post("/api/transcribe")
async def api_transcribe(token: str = Query(default=""), audio: UploadFile = File(...)):
    """
    Accept an audio file from the mobile app, transcribe it, and feed the text
    through the orchestrator. The response arrives over the WebSocket like any
    normal voice interaction.
    """
    if config.WS_TOKEN and token != config.WS_TOKEN:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")

    import tempfile, os
    suffix = os.path.splitext(audio.filename or "audio.m4a")[1] or ".m4a"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await audio.read())
        tmp_path = f.name

    try:
        # Transcribe using the same STT pipeline as the voice loop
        from core.stt import transcribe
        from core.audio import load_audio_file
        pcm = load_audio_file(tmp_path)
        user_text = transcribe(pcm)
    finally:
        os.unlink(tmp_path)

    if not user_text or not user_text.strip():
        return {"ok": False, "error": "empty transcription"}

    import base64
    from core.orchestrator import Orchestrator
    from core.state import broadcast_text
    from core.tts import synthesize_bytes

    if not hasattr(api_transcribe, "_orch"):
        api_transcribe._orch = Orchestrator()

    def _process():
        broadcast_text("user", user_text)
        response, _ = api_transcribe._orch.process(user_text)
        broadcast_text("jarvis", response)
        return response

    response = await asyncio.get_event_loop().run_in_executor(None, _process)
    audio_bytes = await synthesize_bytes(response)
    return {
        "ok": True,
        "text": user_text,
        "response": response,
        "audio_b64": base64.b64encode(audio_bytes).decode(),
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    # Require token when WS_TOKEN is configured (external/mobile access)
    if config.WS_TOKEN and token != config.WS_TOKEN:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    q = jarvis_state.subscribe()

    # Send current state snapshot immediately on connect
    await websocket.send_text(json.dumps({"type": "state", "state": jarvis_state.get_state().value}))
    agent_names = [t["name"] for t in AGENT_TOOLS]
    await websocket.send_text(json.dumps({"type": "agents", "agents": agent_names}))
    from core.mood import get_mood
    await websocket.send_text(json.dumps({"type": "mood", "mood": get_mood().value}))
    await websocket.send_text(json.dumps({
        "type": "tokens",
        "local": jarvis_state._tokens_local,
        "cloud_in": jarvis_state._tokens_cloud_in,
        "cloud_out": jarvis_state._tokens_cloud_out,
    }))
    from core.tts import _xtts_available
    from core.stt import _parakeet_available, _parakeet_checked
    await websocket.send_text(json.dumps({
        "type": "sysinfo",
        "tts_engine": "XTTS V2" if _xtts_available else "EDGE TTS",
        "stt_engine": ("PARAKEET TDT 1.1B (GPU)" if _parakeet_available
                       else ("WHISPER BASE.EN" if _parakeet_checked else "CHECKING...")),
        "ai_core": "CLAUDE SONNET",
        "version": config.VERSION,
        "api_version": config.API_VERSION,
    }))

    try:
        while True:
            payload = await q.get()
            await websocket.send_text(payload)
    except WebSocketDisconnect:
        jarvis_state.unsubscribe(q)
    except Exception:
        jarvis_state.unsubscribe(q)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _plex_title(item: dict) -> str:
    """
    Build a clean display title from a Plex metadata item.

    Episode display:  "Breaking Bad  ·  S02E05 — Breakage"
    Movie display:    "The Dark Knight (2008)"

    Plex fields:
      grandparentTitle = show name  (present in sessions + history)
      parentTitle      = season name (present in recentlyAdded for episodes)
      parentIndex      = season number
      index            = episode number
      title            = episode/movie title
    """
    ptype = item.get("type", "")
    title = item.get("title", "Unknown")
    year  = item.get("year", "")

    # Show name: grandparentTitle (sessions/history) or fall back to grandparentTitle from recentlyAdded
    show = (
        item.get("grandparentTitle")
        or item.get("originallyAvailableAt", "")  # not show, skip
        or ""
    )
    # For recently-added, grandparentTitle is populated for episodes too — just ensure we use it
    show = item.get("grandparentTitle", "")

    season  = item.get("parentIndex")
    episode = item.get("index")

    if ptype == "episode":
        ep_tag = ""
        if season is not None and episode is not None:
            ep_tag = f"S{int(season):02d}E{int(episode):02d} — "
        if show:
            return f"{show}  ·  {ep_tag}{title}"
        # fallback: no show name available, just show ep code + title
        return f"{ep_tag}{title}" if ep_tag else title

    elif ptype == "season":
        # recentlyAdded can return seasons — show the series name + season
        show = item.get("parentTitle") or item.get("title", "Unknown")
        season = item.get("index") or item.get("parentIndex")
        if season is not None:
            return f"{show}  ·  Season {int(season)}"
        return show

    elif ptype == "movie":
        return f"{title}{' ('+str(year)+')' if year else ''}"

    elif ptype == "track":
        artist = item.get("grandparentTitle", "")
        return f"{artist} — {title}" if artist else title

    return title


def _format_session(s: dict) -> dict:
    """Format a live Plex session (now playing)."""
    duration   = s.get("duration", 1) or 1
    view_offset = s.get("viewOffset", 0)
    return {
        "title":    _plex_title(s),
        "type":     s.get("type", ""),
        "user":     s.get("User", {}).get("title", "Unknown"),
        "player":   s.get("Player", {}).get("title", ""),
        "state":    s.get("Player", {}).get("state", ""),
        "progress": round(view_offset / duration * 100),
        "duration_min": round(duration / 60000),
        "elapsed_min":  round(view_offset / 60000),
    }


def _format_history(h: dict, account_map: dict | None = None) -> dict:
    """Format a Plex session history entry (recently watched).

    History items use accountID (int) not a User object — resolve via account_map.
    """
    import datetime
    viewed_at = h.get("viewedAt", 0)
    try:
        dt = datetime.datetime.fromtimestamp(viewed_at)
        time_str = dt.strftime("%H:%M") + "  " + dt.strftime("%d %b")
    except Exception:
        time_str = ""

    # Resolve user: history returns accountID, live sessions return User.title
    user = ""
    if account_map:
        account_id = h.get("accountID")
        if account_id is not None:
            user = account_map.get(account_id, account_map.get(str(account_id), ""))
    if not user:
        user = h.get("User", {}).get("title", "") or h.get("user", "") or "Unknown"

    return {
        "title":  _plex_title(h),
        "type":   h.get("type", ""),
        "user":   user,
        "player": h.get("Player", {}).get("title", "") or h.get("deviceName", ""),
        "time":   time_str,
    }


def _format_media_item(i: dict) -> dict:
    """Format a recently-added Plex library item."""
    return {
        "title": _plex_title(i),
        "type":  i.get("type", ""),
        "year":  i.get("year", ""),
    }


def _fmt_size(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def _fmt_speed(bps: float) -> str:
    return _fmt_size(bps) + "/s"

def _fmt_eta(secs: int) -> str:
    if secs <= 0 or secs > 86400 * 30:
        return "—"
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m" if h else f"{m}m {s}s"


# ── Port cleanup & startup ────────────────────────────────────────────────────

def _kill_port(port: int) -> None:
    """Kill any process already holding the given port before we bind to it."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return
    import psutil, time
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    print(f"[Server] Port {port} held by PID {conn.pid} ({proc.name()}) — terminating.")
                    proc.terminate()
                    proc.wait(timeout=3)
                    time.sleep(0.5)
                    return
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    print(f"[Server] Could not terminate PID {conn.pid}: {e}")
    except psutil.AccessDenied:
        import subprocess, os
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                print(f"[Server] Port {port} held by PID {pid} (via netstat) — terminating.")
                os.system(f"taskkill /F /PID {pid}")
                time.sleep(0.5)
                return


def start(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Kill any stale Jarvis process on the port, then start the UI server."""
    _kill_port(port)
    import time; time.sleep(1.0)

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        jarvis_state.set_loop(loop)
        cfg = uvicorn.Config(app, host=host, port=port, log_level="warning", loop="asyncio")
        server = uvicorn.Server(cfg)
        loop.run_until_complete(server.serve())

    jarvis_state.start_stats_broadcaster()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
