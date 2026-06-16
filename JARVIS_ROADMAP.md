# JARVIS — Strategic Roadmap
## Deep Thinking: Making Jarvis Truly Powerful

> Current version: V0.0.103
> Status: Planning document — no code changes yet

---

## WHERE WE ARE TODAY

### Agent Inventory (36 total actions across 7 agents)

| Agent | Actions | Gap |
|---|---|---|
| Briefing | 1 | Single read-only summary |
| Smart Home | 7 | No sensors, no automations, no climate |
| Outlook | 7 | No drafts, no attachments, no contacts |
| Plex | 6 | No playback control, no ratings, no watchlist |
| Radarr | 5 | No quality management, no collections |
| Sonarr | 6 | No season management, no notifications |
| qBittorrent | 4 | No add-torrent, no category management |

### Current Routing Model (Binary)
```
User speaks → regex match? → Cloud (Claude + all agents)
                          → Local (Llama, no agents at all)
```

**Problem:** Local Llama is completely agent-blind. Even simple agent queries
("is the light on?", "what's playing?") that need one API call go fully to cloud.

---

## THE VISION

```
User speaks
    ↓
Intent classifier (local, fast)
    ↓
Task planner (breaks into sub-tasks if needed)
    ↓
Agent Orchestra
    ├── Agent A  ──────────────────────────┐
    ├── Agent B  → can call Agent C        │ parallel or
    └── Agent C  ← can request from A      │ sequential
    ↓
Results aggregator (local if simple, cloud if reasoning needed)
    ↓
Natural language response
```

---

## PILLAR 1 — EXPANDED AGENTS (10+ ACTIONS EACH)

### Smart Home Agent (target: 14 actions)
Beyond current 7:
- `get_sensor` — read temperature, humidity, motion, door, energy sensors
- `set_climate` — control AC temperature, mode (cool/heat/auto)
- `list_automations` — show all HA automations and their state
- `toggle_automation` — enable/disable an automation by name
- `get_energy` — power consumption from HA energy dashboard
- `get_history` — entity state history over time ("was the AC on last night?")
- `send_notification` — push message to HA mobile companion app

### Outlook Agent (target: 14 actions)
Beyond current 7:
- `get_email_body` — fetch full body of a specific email (not just preview)
- `reply_email` — reply to a message by ID
- `flag_email` — mark email as flagged/important
- `delete_email` — move to trash
- `list_contacts` — search address book
- `get_contact` — fetch contact details
- `update_event` — modify existing calendar event
- `cancel_event` — decline or delete event

### Plex Agent (target: 12 actions)
Beyond current 6:
- `play` — trigger playback on a specific Plex client
- `pause_playback` — pause active stream
- `stop_playback` — stop active stream
- `get_watchlist` — show Plex watchlist
- `rate_media` — set a star rating
- `get_recommendations` — fetch "More Like This" suggestions
- `get_watch_history` — list recently watched by user

### Media Manager Agent — Merge Radarr + Sonarr (target: 15 actions)
Unify movie and TV into one agent:
- All existing Radarr + Sonarr actions (11 total)
- `add_to_watchlist` — add to both Radarr and Sonarr watchlist with a single command
- `get_combined_queue` — unified download queue (movies + episodes)
- `delete_media` — remove from library and disk
- `get_quality_profiles` — list and change quality settings

### System Agent (NEW — target: 10 actions)
Replace static stats bar with a queryable agent:
- `get_cpu` — CPU usage and top processes
- `get_memory` — RAM usage and top consumers
- `get_gpu` — GPU utilisation, VRAM, temperature
- `get_disk` — disk space per drive
- `get_network` — upload/download speed, active connections
- `list_processes` — running processes with resource usage
- `kill_process` — terminate by name
- `get_services` — Windows services state
- `system_report` — full health summary (calls all of above)
- `restart_service` — restart a named Windows service

### Finance Agent (NEW — target: 10 actions)
Requires adding a bank/finance API (e.g., Plaid, or manual CSV):
- `get_balance` — current account balance(s)
- `get_recent_transactions` — last N transactions
- `search_transactions` — find by merchant or amount
- `get_monthly_summary` — spend by category this month
- `get_budget_status` — how much left in each budget
- `get_subscriptions` — recurring charges detected
- `compare_month` — this month vs last month
- `top_merchants` — where money is being spent most
- `flag_transaction` — mark unusual charge for review
- `export_summary` — generate a spend report

### Memory Agent (NEW — target: 10 actions)
Persistent knowledge base Jarvis builds over time:
- `remember` — store a fact ("Sir prefers room temp at 22°C for sleeping")
- `recall` — retrieve stored facts by topic
- `forget` — delete a specific memory
- `list_memories` — show all stored memories by category
- `update_memory` — modify an existing memory
- `get_preferences` — retrieve user preferences
- `set_preference` — update a preference
- `log_event` — log a timestamped event ("worked out today")
- `get_events` — retrieve logged events by date range
- `summarize_week` — summarise what was logged this week

### Web Agent (NEW — target: 8 actions)
Jarvis can research, fetch, and summarise online information:
- `search` — web search via SerpAPI or similar
- `fetch_page` — retrieve and clean a URL
- `summarise_url` — fetch and summarise in plain text
- `get_news` — latest news headlines by topic
- `track_package` — parcel tracking via courier APIs
- `check_price` — price lookup for a product
- `get_stock` — stock/crypto price
- `weather_forecast` — multi-day weather (already partially done via Open-Meteo)

---

## PILLAR 2 — AGENT-TO-AGENT COMMUNICATION

### The Problem Today
Agents are isolated. The briefing agent cannot ask Outlook for meetings.
Home Assistant cannot tell Plex to pause when someone rings the doorbell.

### Proposed: Agent Bus

Each agent gets access to a shared `agent_bus` — a lightweight in-process
message broker. Agents can:
1. **Request** — ask another agent for data synchronously
2. **Subscribe** — listen for events from another agent asynchronously
3. **Publish** — emit events other agents can react to

```python
# Example: Briefing calls Outlook and Smart Home internally
class BriefingAgent:
    def get_briefing(self):
        meetings = agent_bus.request("outlook", "todays_meetings")
        presence = agent_bus.request("smart_home", "who_is_home")
        weather  = agent_bus.request("weather", "summary")
        # combine into briefing
```

```python
# Example: Smart Home reacts to Plex events
agent_bus.subscribe("plex", "playback_started", lambda e:
    agent_bus.request("smart_home", "control_light",
        entity_id="light.living_room", light_action="off")
)
```

### Implementation Plan
- `core/agent_bus.py` — lightweight request/subscribe/publish broker
- Each agent exposes an `internal_dispatch` dict (separate from Claude's TOOL_SCHEMA)
- Bus calls are synchronous for request, async for subscribe
- Orchestrator can inject bus into each agent on init

### Example Multi-Agent Chains

| Trigger | Chain |
|---|---|
| "Good morning" briefing | Briefing → Outlook (meetings) → Smart Home (presence) → Weather → Memory (preferences) → Plex (what was watched last night) |
| Movie starts on Plex | Plex emits event → Smart Home dims lights → Outlook checks no upcoming meetings |
| Doorbell rings (HA motion) | Smart Home publishes → Plex pauses → Notification sent |
| "Leaving home" | Smart Home (presence leaves) → AC off → Lights off → Plex stop → Memory logs departure time |

---

## PILLAR 3 — HYBRID LLM WITHIN AGENTS

### The Problem Today
Routing is all-or-nothing at the message level:
- Simple agent query ("is the light on?") → Cloud Claude → wasted API cost
- Local Llama → no agents at all → blind to home state

### Proposed: Three-Tier Execution Model

```
Tier 1 — Local Llama (no tool call needed)
  → Chitchat, opinions, jokes, maths, explanations
  → "What's the capital of France?"
  → "Tell me a joke"

Tier 2 — Local Llama + Agent (single deterministic tool call)
  → Simple lookups where response is read-only and structured
  → "Is the light on?" → HA get_state → Llama formats result
  → "What's playing?" → Plex now_playing → Llama formats result
  → "Any unread emails?" → Outlook unread → Llama formats result

Tier 3 — Cloud Claude + Agents (reasoning required)
  → Multi-step tasks, ambiguity, write operations, chaining
  → "Schedule a meeting with Mariam tomorrow at 2pm" → Claude + Outlook
  → "Download the latest Mission Impossible and dim the lights" → Claude + Radarr + HA
  → "Summarise my unread DEWA emails and tell me if I owe money" → Claude + Outlook
```

### Implementation Plan

**Router upgrade** (`core/router.py`):
- Add a third category: `SIMPLE_AGENT_PATTERNS`
- These patterns match a single read-only agent lookup
- Route to `local_agent_call()` instead of full cloud path

```python
_SIMPLE_AGENT_PATTERNS = {
    r"\b(is|are).*(light|lamp).*(on|off)\b": ("smart_home", "get_state"),
    r"\bwhat.*(playing|streaming)\b":         ("plex_manager", "now_playing"),
    r"\bhow many unread\b":                   ("outlook_manager", "unread"),
    r"\bwho.*(home|there)\b":                 ("smart_home", "who_is_home"),
    r"\bhow many torrents\b":                 ("qbittorrent", "status"),
}
```

**Orchestrator addition** — `process_simple_agent()`:
```
1. Detect SIMPLE_AGENT pattern → extract tool + action
2. Call agent directly (no Claude)
3. Feed raw result to local Llama with tiny prompt: "Format this as a spoken response"
4. Return formatted response
```

This keeps 70-80% of agent queries off the cloud API entirely.

---

## PILLAR 4 — PROACTIVE JARVIS

### The Problem Today
Jarvis is purely reactive — it only does things when asked.

### Proposed: Background Monitors

Each monitor runs in a daemon thread and publishes events to the agent bus.

| Monitor | Check Interval | Trigger |
|---|---|---|
| Calendar Monitor | Every 5 min | Alert 15 min before a meeting |
| Email Monitor | Every 10 min | Alert on email from VIP senders |
| Home Arrival Monitor | Every 30 sec | Greet when person arrives home |
| Download Monitor | Every 60 sec | Announce when download completes |
| System Health Monitor | Every 30 sec | Alert if GPU temp > 85°C or disk < 10% |

**Delivery:** Proactive alerts use `speak()` directly — Jarvis speaks unprompted.
UI shows a badge for pending alerts the user hasn't acknowledged.

---

## PILLAR 5 — PERSISTENT MEMORY

### The Problem Today
Each session starts from zero. Jarvis doesn't remember that the user:
- Prefers 22°C when sleeping
- Always watches movies on TV1 not TV2
- Has a standing meeting every Tuesday at 10am
- Likes leg day on Mondays

### Proposed: Two-Layer Memory

**Layer 1 — Session Memory** (already exists, `history` in orchestrator)
- Last 20 messages
- Cleared on restart

**Layer 2 — Persistent Memory** (new, SQLite-backed)
- Stored in `memory/jarvis_memory.db`
- Three tables: `facts`, `preferences`, `events`
- Managed via Memory Agent (see Pillar 1)
- Injected as a compressed block into Claude's system prompt each session

```python
# System prompt addition
MEMORY_BLOCK = memory_agent.get_session_context()
# → "Sir prefers: room at 22°C for sleep, British accent responses,
#    leg day on Mondays. Last seen: yesterday at 6pm.
#    Standing meetings: Tuesday 10am standup."
```

---

## PILLAR 6 — NATURAL MULTI-STEP PLANNING

### The Problem Today
Claude handles multi-step implicitly via tool loops (max 5 rounds).
There is no explicit plan — Claude figures it out on the fly.

### Proposed: Task Planner

For complex requests, inject a planning step before tool execution:

```
User: "Prepare my office for the 3pm meeting"

Planner output:
  1. Check Outlook: confirm 3pm meeting exists and who's attending
  2. Smart Home: run script.office_room_meeting
  3. Smart Home: set lights to work scene
  4. Smart Home: set AC to 23°C
  5. Plex: pause any active streams
  6. Notify: "Office prepared for your 3pm meeting, sir"

Execute steps 1-5 in order, step 6 via TTS
```

The plan is shown in the UI before execution begins.
User can approve or skip steps (future enhancement).

---

## PILLAR 7 — THREE-SCREEN COMMAND CENTRE

### The Opportunity
You have 3 monitors. Today Jarvis occupies one fullscreen window and wastes the other two.
A true Iron Man HUD uses every display — each screen has a distinct purpose and personality.

### Proposed Screen Layout

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   SCREEN 1       │  │   SCREEN 2       │  │   SCREEN 3       │
│   PRIMARY HUD    │  │   CONTROL PANEL  │  │   INTEL / DATA   │
│                  │  │                  │  │                  │
│  Voice orb       │  │  Home map        │  │  Calendar today  │
│  State / mood    │  │  Live sensors    │  │  Unread emails   │
│  Comms log       │  │  Light controls  │  │  Download queue  │
│  System stats    │  │  AC / climate    │  │  Plex streams    │
│  Token usage     │  │  Who is home     │  │  News headlines  │
│                  │  │  Agent activity  │  │  Finance summary │
└──────────────────┘  └──────────────────┘  └──────────────────┘
       8765                  8766 (new)             8767 (new)
```

### Implementation Plan

**Electron multi-window** (`electron/main.js`):
- Use `electron.screen.getAllDisplays()` to detect all connected monitors
- Open a `BrowserWindow` on each display, fullscreen, no frame
- Each window loads a different route from the same FastAPI server:
  - `http://localhost:8765/` → Screen 1 (primary HUD — existing)
  - `http://localhost:8765/panel` → Screen 2 (home control panel)
  - `http://localhost:8765/intel` → Screen 3 (data / intel dashboard)

**FastAPI routes** (`ui/server.py`):
- `/panel` → serves `panel.html` (home control panel)
- `/intel` → serves `intel.html` (data dashboard)
- All three share the same WebSocket `/ws` — same event bus, different rendering

**Screen 2 — Home Control Panel** (`ui/static/panel.html`):
- Live floor plan or room grid (SVG-based, updates from HA state)
- Each room shows: lights on/off, AC temp, motion detected, energy usage
- Clickable controls (pointer-events enabled here unlike main HUD)
- Real-time sensor values: temperature, humidity, door sensors
- Presence indicators: who is in which room
- Agent activity log: what tools were called recently

**Screen 3 — Intel Dashboard** (`ui/static/intel.html`):
- **Calendar strip**: today's meetings with countdown timers
- **Email panel**: last 5 unread emails, flagged items
- **Download queue**: Radarr + Sonarr + qBit combined, with progress bars
- **Plex now playing**: active streams with artwork
- **System health**: GPU/CPU/RAM gauges (larger, more detailed than main HUD)
- **Weather**: current + 24h forecast
- **Finance widget** (future): daily spend summary

### Fallback Behaviour
- If only 1 monitor detected → fullscreen on primary, other UIs accessible via keyboard shortcut
- If 2 monitors → Screen 1 on primary, Screen 3 (intel) on secondary
- If 3 monitors → full layout above

### Wake Word Focus
Currently wake word calls `localhost:8766/focus` to bring main window forward.
Extension: broadcast focus event to all windows simultaneously — all three screens
animate their borders to show Jarvis is listening.

---

## PILLAR 8 — MIGRATE LOCAL LLM TO NEMOTRON

### Why Nemotron over Llama 3.1 8B

| Property | Llama 3.1 8B | Nemotron Mini 4B |
|---|---|---|
| Parameters | 8B | 4B |
| VRAM (4-bit) | ~5GB | ~2.5GB |
| Speed (tokens/sec on 4070S) | ~35 t/s | ~70 t/s |
| Context window | 128K | 4K |
| Training focus | General | Chat + tool-use + roleplay |
| NVIDIA optimisation | None | CUDA kernels, TensorRT-ready |
| Persona adherence | Average | Strong (built for assistant personas) |

**Model:** `nvidia/Nemotron-Mini-4B-Instruct`
- Fits comfortably in 12GB VRAM alongside XTTS v2 (~2GB) with headroom
- Optimised for conversational AI — better at staying in character as JARVIS
- Faster inference = lower latency on simple replies
- HuggingFace: `nvidia/Nemotron-Mini-4B-Instruct`

### Migration Plan

**Step 1 — Update `local_llm_service/service.py`:**
```python
MODEL_ID = "nvidia/Nemotron-Mini-4B-Instruct"
# BitsAndBytesConfig stays the same (4-bit NF4)
# No other code changes needed — same HuggingFace API
```

**Step 2 — Update system prompt in service.py:**
Nemotron is persona-aware — lean into it:
```python
SYSTEM_PROMPT = (
    "You are JARVIS, the AI assistant from Iron Man. "
    "You are sophisticated, witty, efficient. Speak in plain sentences — "
    "no markdown. Address the user as sir. Be concise."
)
```

**Step 3 — Tune generation parameters:**
Nemotron is a smaller model — tighter sampling helps quality:
```python
temperature=0.6,   # was 0.7
top_p=0.85,        # was 0.9
max_new_tokens=192 # was 256 — Nemotron is more concise
```

**Step 4 — Evaluate before committing:**
- Run 20 test prompts against both models
- Compare: response quality, character adherence, latency
- Keep the winner; old model stays cached on disk

### Future: Nemotron + TensorRT-LLM
Once confirmed working, NVIDIA's TensorRT-LLM can quantize and optimize
Nemotron further — potentially reaching 120+ tokens/sec on the 4070 Super.
This would make local responses feel near-instant (under 1 second for most replies).

### VRAM Budget with Full Stack

| Component | VRAM |
|---|---|
| Nemotron Mini 4B (4-bit) | ~2.5 GB |
| XTTS v2 | ~2.0 GB |
| System overhead | ~0.5 GB |
| **Total** | **~5.0 GB** |
| **Available (4070 Super)** | **12 GB** |
| **Headroom** | **~7 GB** |

This leaves room for a future vision model or larger upgrade.

---

## BUILD SEQUENCE (Suggested Order)

### Phase 1 — Foundation (V0.1.x)
- [ ] **Migrate local LLM to Nemotron Mini 4B** (Pillar 8)
- [ ] Agent Bus (`core/agent_bus.py`) (Pillar 2)
- [ ] Tier 2 routing (local Nemotron + single agent call) (Pillar 3)
- [ ] Smart Home expansion to 14 actions (Pillar 1)
- [ ] Outlook expansion to 14 actions (Pillar 1)
- [ ] System Agent (10 actions) (Pillar 1)
- [ ] Merge Radarr + Sonarr into Media Agent (Pillar 1)

### Phase 2 — Intelligence (V0.2.x)
- [ ] **Three-screen Electron layout** — Screen 2 Home Panel (Pillar 7)
- [ ] **Three-screen Electron layout** — Screen 3 Intel Dashboard (Pillar 7)
- [ ] Memory Agent + SQLite persistence (Pillar 5)
- [ ] Memory injection into system prompt (Pillar 5)
- [ ] Proactive calendar and email monitors (Pillar 4)
- [ ] Plex expansion + playback control (Pillar 1)
- [ ] Finance Agent (if API source decided) (Pillar 1)

### Phase 3 — Autonomy (V0.3.x)
- [ ] Agent-to-agent subscriptions (event-driven) (Pillar 2)
- [ ] Task Planner (plan display in UI) (Pillar 6)
- [ ] Web Agent (Pillar 1)
- [ ] Home arrival/departure automation chains (Pillar 4)
- [ ] Doorbell/sensor trigger pipeline (Pillar 4)
- [ ] TensorRT-LLM optimisation for Nemotron (Pillar 8)

### Phase 4 — Polish (V1.0)
- [ ] User approval flow for multi-step plans (Pillar 6)
- [ ] Full demo mode with all agents and all three screens active
- [ ] Self-improvement: Jarvis logs failed queries and suggests new patterns

---

## OPEN QUESTIONS TO DECIDE

1. **Finance agent data source** — Plaid (US-centric), bank OFX export, or manual CSV?
2. **Web search API** — SerpAPI ($), Brave Search API (cheaper), or local crawl?
3. **Memory UI** — Should the user be able to see/edit Jarvis memories from the UI?
4. **Proactive speaking** — Should Jarvis speak proactively when no one is in the room, or only via notification badge?
5. **Agent bus persistence** — Should agent events be logged to disk for replay/audit?
6. **Voice for proactive alerts** — Different TTS voice/tone for alerts vs responses?
7. **Screen 2 interaction** — Should the home control panel be fully clickable (mouse control of lights, AC, etc.) or voice-only like the main screen?
8. **Screen 3 refresh rate** — Email/calendar panels: pull on demand vs auto-refresh every N minutes?
9. **Nemotron evaluation** — Run side-by-side test before committing to migration, or migrate directly?
10. **TensorRT-LLM** — Pursue after Nemotron is stable, or skip and wait for a future GPU upgrade?

---

## PILLAR SUMMARY

| # | Pillar | Status | Target Phase |
|---|---|---|---|
| 1 | Expanded Agents (10+ actions each) | Planned | V0.1.x |
| 2 | Agent-to-Agent Communication (bus) | Planned | V0.1.x |
| 3 | Hybrid LLM within Agents (3-tier) | Planned | V0.1.x |
| 4 | Proactive Jarvis (background monitors) | Planned | V0.2.x |
| 5 | Persistent Memory (SQLite) | Planned | V0.2.x |
| 6 | Natural Multi-Step Planning | Planned | V0.3.x |
| 7 | Three-Screen Command Centre | Planned | V0.2.x |
| 8 | Migrate to Nemotron Mini 4B | Planned | V0.1.x |

---

*Document created: 2026-06-16*
*Last updated: 2026-06-16 — added Pillars 7 (multi-screen) and 8 (Nemotron)*
*Next review: when returning from break*
