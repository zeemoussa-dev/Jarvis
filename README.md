# J.A.R.V.I.S.
### Just A Rather Very Intelligent System

> A voice-activated AI assistant inspired by Iron Man's JARVIS — built for a real home with real integrations.

---

## What It Does

Speak to Jarvis. It wakes on your voice, understands what you need, routes the request to the right AI (local or cloud), calls the right agent, and speaks back — all within seconds.

- **Wake word detection** — always listening, near-zero CPU
- **Speech-to-text** — faster-whisper running locally
- **Hybrid AI routing** — simple queries go to a local Nvidia Nemotron 4B (free, instant). Complex or agentic requests route to Claude Sonnet (cloud)
- **Tool agents** — Home Assistant, Outlook, Plex, Radarr, Sonarr, qBittorrent, System Monitor
- **Voice synthesis** — XTTS v2 (GPU, voice cloned from a reference sample) with Edge TTS fallback
- **Electron UI** — fullscreen HUD showing real-time system stats, token usage, active agents, and conversation

---

## Architecture

```
Mic → Wake Word (openwakeword)
    → STT (faster-whisper, local)
    → Router (regex, no LLM call)
         ├── Local → Nvidia Nemotron Mini 4B (localhost:8001, GPU)
         └── Cloud → Claude Sonnet + Tool Loop (up to 5 rounds)
                          └── Agents: HA · Outlook · Plex · Radarr · Sonarr · qBit · System
    → TTS: XTTS v2 (localhost:8002, GPU) → Edge TTS fallback
    → Speakers
```

**Two Python runtimes** — Main process runs Python 3.14 (PyTorch-incompatible). GPU services (local LLM + XTTS) run as separate FastAPI microservices under Python 3.11 with CUDA 12.1.

**WebSocket UI** — FastAPI serves the Electron frontend on port 8765. Real-time events: `state`, `message`, `mood`, `stats`, `tokens`, `sysinfo`.

---

## Agents

| Agent | Tool Name | Key Actions |
|---|---|---|
| Briefing | `get_briefing` | Morning briefing, demo mode |
| Home Assistant | `smart_home` | Lights, switches, climate, sensors, presence, scenes, automations, notifications |
| Outlook | `outlook_manager` | Email, calendar, contacts, send, reply, flag, create/update/cancel events |
| Plex | `plex_manager` | Now playing, libraries, recently added, on deck, search |
| Radarr | `movie_manager` | Search, add, queue |
| Sonarr | `tv_manager` | Search, add, missing episodes |
| qBittorrent | `qbittorrent` | List, pause, resume, stats |
| System | `system_agent` | CPU, RAM, GPU, disk, network, processes, services, full report |

---

## Tech Stack

| Component | Technology |
|---|---|
| Main runtime | Python 3.14 |
| GPU services | Python 3.11 + CUDA 12.1 |
| Wake word | openwakeword |
| STT | faster-whisper (`base.en`) |
| Local LLM | Nvidia Nemotron Mini 4B Instruct (4-bit NF4, ~3GB VRAM) |
| Cloud LLM | Anthropic Claude Sonnet (`claude-sonnet-4-6`) |
| TTS primary | Coqui XTTS v2 (voice cloning, GPU) |
| TTS fallback | Microsoft Edge TTS (`en-GB-RyanNeural`) |
| UI server | FastAPI + WebSocket |
| Desktop UI | Electron (fullscreen HUD) |
| Home control | Home Assistant REST API |
| Calendar/Email | Microsoft Graph API (Outlook) |

---

## Screenshots

> Fullscreen HUD with live CPU/GPU/RAM metrics, token counters, active agents, and conversation log.

---

## Project Structure

```
Jarvis/
├── main.py                  # Entry point — orchestrates all services
├── config.py                # All config + secrets (loaded from .env)
├── core/
│   ├── orchestrator.py      # Claude tool loop + local LLM dispatch
│   ├── router.py            # Regex-based cloud/local routing (no LLM call)
│   ├── tts.py               # XTTS → Edge TTS fallback
│   ├── stt.py               # faster-whisper transcription
│   ├── wake_word.py         # openwakeword listener
│   ├── state.py             # WebSocket state + system stats broadcaster
│   └── mood.py              # PERSONAL / WORK / DEMO mode
├── agents/
│   ├── __init__.py          # Agent registry + dispatcher
│   ├── home_assistant.py
│   ├── outlook.py
│   ├── plex.py
│   ├── radarr.py
│   ├── sonarr.py
│   ├── qbittorrent.py
│   ├── briefing.py
│   └── system_agent.py
├── ui/
│   ├── server.py            # FastAPI app, WebSocket, port self-eviction
│   └── static/index.html    # Electron HUD
├── electron/
│   └── main.js              # Electron shell (fullscreen, tray, focus endpoint)
├── local_llm_service/       # Python 3.11 venv — Nemotron on GPU
│   ├── service.py
│   └── start.bat
├── tts_service/             # Python 3.11 venv — XTTS v2 on GPU
│   ├── service.py
│   └── start.bat
└── assets/
    └── Jarvis.mp3           # Reference voice sample for XTTS cloning
```

---

## License

Private project. Not for redistribution.
