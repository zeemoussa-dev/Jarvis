# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## How to Run

### Start Jarvis (main process)
```
C:\Python314\python.exe main.py
```
This launches the FastAPI/WebSocket UI server, Electron desktop app, wake-word detector, and orchestrator in one process.

### Start the Local LLM service (separate terminal, must start first)
```
local_llm_service\start.bat
```
Runs Llama 3.1 8B on GPU via Python 3.11 venv at `http://localhost:8001`. Wait for "Model ready." before starting Jarvis.

### Electron UI only (for UI development)
```
cd electron && npm start
```
Connects to `http://localhost:8765` (FastAPI). Must have Jarvis running first.

## Architecture

Jarvis is a **voice pipeline** with a **hybrid AI routing layer**:

```
Mic → Wake Word (openwakeword) → STT (faster-whisper)
    → Mood switch check
    → Orchestrator
        ├── Router: regex match? → Local LLM (localhost:8001)
        └── No match / agent needed → Claude (claude-sonnet-4-6) + tool loop
    → TTS (edge-tts, en-GB-RyanNeural) → Speakers
```

### Key design decisions

**Two Python runtimes**: Main process runs Python 3.14 (PyTorch incompatible). GPU services (local LLM, TTS) run as separate FastAPI microservices under Python 3.11 with CUDA.

**Hybrid routing** (`core/router.py`): Regex patterns classify each utterance. Matches route to Claude (cloud) for agentic tasks; non-matches go to local Llama 3.1 8B. Routing is done without an LLM call.

**Tool loop** (`core/orchestrator.py`): Claude can call up to `MAX_TOOL_ROUNDS=5` tool rounds. Each tool call dispatches to the relevant agent. One retry allowed per tool on error. History capped at `MAX_HISTORY=20` messages.

**Real-time date injection**: `_runtime_system_prompt()` appends Dubai date/time to every Claude call, enabling correct relative date handling ("tomorrow", "next week") without hallucination.

**Mood system** (`core/mood.py`): Three modes — PERSONAL (default), WORK, DEMO. Set via voice ("switch to demo mode") or code. Mood affects briefing content and is broadcast over WebSocket to the UI.

**WebSocket state**: `core/state.py` broadcasts `{type: "state"}`, `{type: "text"}`, and `{type: "mood"}` events to all connected clients on port 8765.

**Electron focus**: On each wake word, `main.py` sends HTTP GET to `http://127.0.0.1:8766/focus` — the Electron app's HTTP server brings the window to front.

## Agents

All agents expose a single function with an `action` enum parameter and a `TOOL_SCHEMA` dict for Claude. Add new agents by:
1. Creating `agents/your_agent.py` with `TOOL_SCHEMA` and `DISPATCH`
2. Importing in `agents/__init__.py` and adding to `AGENT_TOOLS` and `_DISPATCH`
3. Adding routing patterns to `core/router.py` `_CLOUD_PATTERNS`

| Agent | Tool name | Actions |
|---|---|---|
| Briefing | `get_briefing` | morning briefing (DEMO mode returns scripted content + triggers HA script) |
| Home Assistant | `home_assistant` | lights, switches, scripts, scenes, presence |
| Plex | `plex_manager` | now_playing, libraries, recent, on_deck, search |
| Radarr | `radarr_manager` | search, add, queue |
| Sonarr | `sonarr_manager` | search, add, missing episodes |
| qBittorrent | `qbit_manager` | list, pause, resume, stats |
| Outlook | `outlook_manager` | unread, recent_emails, search_emails, send_email, todays_meetings, upcoming_meetings, create_event |

## Configuration

All secrets live in `.env` (never commit). Key variables:
- `ANTHROPIC_API_KEY` — Claude API
- `HA_URL` / `HA_TOKEN` — Home Assistant (local, `http://10.0.0.200:8123`)
- `PLEX_URL` / `PLEX_TOKEN` — Plex (`http://10.0.0.100:32400`)
- `MS_CLIENT_ID` / `MS_REFRESH_TOKEN` — Microsoft Graph (Outlook); public client, no client_secret in token exchange
- `HF_TOKEN` — HuggingFace (Llama model download)

`config.py` loads `.env` and exposes all constants. `SYSTEM_PROMPT` is defined there and includes hard guard rails prohibiting hallucination, plus Outlook-first rules for calendar/email queries.

## Microsoft Graph / Outlook notes

- Auth: public client OAuth2 (`tenant="consumers"`), refresh token flow — no client_secret sent
- Timezone: all calendar operations use `Asia/Dubai` (UTC+4); `_TZ_HEADER` sent on every calendar request
- Calendar coverage: `_all_calendar_events()` iterates all calendars (not just default) to avoid missing events
- Token refresh happens on every call (no expiry tracking) — safe but slightly slow

## TTS

`core/tts.py` uses `edge-tts` with voice `en-GB-RyanNeural`. The `_clean()` function strips markdown and converts `J.A.R.V.I.S.` → `JARVIS` before synthesis. Audio plays via `sounddevice`. After speaking, `main.py` sleeps `POST_SPEAK_DELAY=0.6s` to prevent acoustic echo re-triggering the wake word.

## Local LLM Service

Located in `local_llm_service/`. Requires Python 3.11 venv with:
- `torch==2.1.2+cu121` (CUDA 12.1, NVIDIA 4070 Super)
- `transformers`, `bitsandbytes`, `accelerate`, `fastapi`, `uvicorn`
- `numpy<2` (numpy 2.x breaks torch 2.1.2)

Model: `meta-llama/Meta-Llama-3.1-8B-Instruct`, 4-bit NF4 quantization, ~5GB VRAM.
