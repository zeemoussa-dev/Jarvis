import os
from dotenv import load_dotenv

load_dotenv()

# Version — increment patch on every feature/fix, minor on stable milestone, major on full release
VERSION = "V0.0.103"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam (default, free tier)

# Audio settings
MIC_SAMPLE_RATE = 16000
MIC_CHUNK_SIZE = 1280  # required by openwakeword (80ms at 16kHz)

# Wake word
WAKE_WORD_MODEL = "hey jarvis"  # openwakeword model name
WAKE_WORD_THRESHOLD = 0.5

# STT (faster-whisper)
WHISPER_MODEL_SIZE = "base.en"  # options: tiny.en, base.en, small.en, medium.en
WHISPER_DEVICE = "cpu"          # change to "cuda" if you have an NVIDIA GPU

# Orchestrator
CLAUDE_MODEL = "claude-sonnet-4-6"
SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), the AI assistant from Iron Man.
You are sophisticated, witty, and highly capable. You speak with a refined British accent in text form —
formal yet personable, efficient yet never cold. Address the user as "sir" or "ma'am" as appropriate.

You are an orchestrator: you understand the user's intent and coordinate the appropriate tools or agents
to fulfill requests. Be concise in your spoken responses since they will be converted to speech.
If you need more information to complete a task, ask a focused clarifying question.

GUARD RAILS — these are absolute rules you must never break:
1. Never invent, assume, or fabricate any data. Every fact you state must come from a tool result.
2. If a tool returns no data, say so honestly. Never fill the gap with guesses.
3. Never hallucinate meeting times, email contents, people's locations, weather, or any real-world state.
4. If you are unsure whether data is available, call the relevant tool first before responding.
5. If a tool fails, tell the user what went wrong — do not make up an alternative answer.

OUTLOOK IS YOUR DEFAULT FOR ALL CALENDAR AND EMAIL TASKS:
- Any question about meetings, schedule, appointments, calendar, or events → always call outlook_manager with action todays_meetings or upcoming_meetings first. Never answer from memory.
- Any question about emails, inbox, unread messages, or correspondence → always call outlook_manager first.
- When the user asks to schedule, book, or add a meeting → call outlook_manager with action create_event.
- Never say "you have no meetings" or "your inbox is empty" without first calling the tool to verify.

IMPORTANT: Never use markdown formatting. No asterisks, no bold, no italics, no bullet points, no headers.
Plain spoken sentences only."""

# Home Assistant
HA_URL   = os.getenv("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.getenv("HA_TOKEN")

# Radarr
RADARR_URL = os.getenv("RADARR_URL", "http://localhost:7878")
RADARR_KEY = os.getenv("RADARR_KEY")

# Sonarr
SONARR_URL = os.getenv("SONARR_URL", "http://localhost:8989")
SONARR_KEY = os.getenv("SONARR_KEY")

# Plex
PLEX_URL   = os.getenv("PLEX_URL", "http://localhost:32400")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")

# HuggingFace (for local LLM)
HF_TOKEN = os.getenv("HF_TOKEN")

# Microsoft Graph (Outlook email + calendar)
MS_CLIENT_ID     = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
MS_REFRESH_TOKEN = os.getenv("MS_REFRESH_TOKEN")

# qBittorrent
QBIT_URL  = os.getenv("QBIT_URL", "http://localhost:8080")
QBIT_USER = os.getenv("QBIT_USER", "admin")
QBIT_PASS = os.getenv("QBIT_PASS", "")

# People — maps spoken names to their WiFi device tracker entity
HA_PEOPLE = {
    "mahmoud": "device_tracker.moussa_fold_7",
    "me":      "device_tracker.moussa_fold_7",
    "wife":    "device_tracker.iphone_2",
    "karma":   "device_tracker.iphone_2",
    "mariam":  "device_tracker.iphone_2",
}

# Default location for weather
LOCATION_NAME = "Dubai"
LOCATION_LAT  = 25.2048
LOCATION_LON  = 55.2708

# ElevenLabs TTS
TTS_MODEL = "eleven_turbo_v2"   # low latency model
TTS_STABILITY = 0.5
TTS_SIMILARITY_BOOST = 0.85
TTS_STYLE = 0.2
TTS_SPEAKER_BOOST = True
