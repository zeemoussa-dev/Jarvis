# Jarvis — Deployment Guide

This guide covers a clean install on a new Windows machine with an NVIDIA GPU.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Windows | 10/11 | x64 |
| Python | 3.14 | Main runtime — [python.org](https://www.python.org/downloads/) |
| Python | 3.11 | GPU services — [python.org](https://www.python.org/downloads/release/python-3119/) |
| Node.js | 18+ | Electron UI — [nodejs.org](https://nodejs.org/) |
| NVIDIA GPU | RTX series | VRAM: 3GB (LLM) + 4GB (XTTS) = 7GB minimum; 12GB recommended |
| CUDA Toolkit | 12.1 | [developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads) |
| NVIDIA Driver | 527+ | Must match CUDA 12.1 |
| Git | Any | [git-scm.com](https://git-scm.com/) |
| Microphone | Any | USB or built-in |

---

## 1. Clone the Repository

```powershell
git clone https://github.com/your-username/jarvis.git
cd jarvis
```

---

## 2. Environment Variables

Copy the template and fill in your secrets:

```powershell
copy .env.example .env
```

Edit `.env`:

```env
# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-...

# Home Assistant
HA_URL=http://10.0.0.200:8123
HA_TOKEN=your_long_lived_token

# Plex
PLEX_URL=http://10.0.0.100:32400
PLEX_TOKEN=your_plex_token

# Radarr
RADARR_URL=http://localhost:7878
RADARR_KEY=your_radarr_api_key

# Sonarr
SONARR_URL=http://localhost:8989
SONARR_KEY=your_sonarr_api_key

# qBittorrent
QBIT_URL=http://localhost:8080
QBIT_USER=admin
QBIT_PASS=your_password

# Microsoft Graph (Outlook)
MS_CLIENT_ID=your_azure_app_client_id
MS_REFRESH_TOKEN=your_refresh_token

# HuggingFace (Nemotron model download)
HF_TOKEN=hf_...
```

> **Never commit `.env` to git.** It is already in `.gitignore`.

---

## 3. Main Python Environment (Python 3.14)

```powershell
C:\Python314\python.exe -m pip install -r requirements.txt
```

If `requirements.txt` is missing, install manually:

```powershell
C:\Python314\python.exe -m pip install `
  anthropic fastapi uvicorn websockets `
  faster-whisper openwakeword `
  edge-tts sounddevice soundfile httpx `
  psutil pynvml python-dotenv
```

---

## 4. Local LLM Service (Python 3.11 + CUDA)

This service runs Nvidia Nemotron Mini 4B on your GPU.

```powershell
cd local_llm_service

# Create the venv with Python 3.11
C:\Python311\python.exe -m venv venv
.\venv\Scripts\activate

# Install PyTorch for CUDA 12.1 first
pip install torch==2.1.2+cu121 --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies (exact versions required)
pip install `
  transformers==4.44.0 `
  bitsandbytes==0.43.3 `
  accelerate==0.21.0 `
  "numpy<2" `
  fastapi uvicorn huggingface_hub

deactivate
cd ..
```

**Model download** — on first run, Nemotron Mini 4B (~8GB) downloads from HuggingFace automatically. Ensure `HF_TOKEN` is set in `.env` and you have accepted the model license at [huggingface.co/nvidia/Nemotron-Mini-4B-Instruct](https://huggingface.co/nvidia/Nemotron-Mini-4B-Instruct).

---

## 5. XTTS Voice Service (Python 3.11 + CUDA)

This service runs Coqui XTTS v2 for voice synthesis.

```powershell
cd tts_service

C:\Python311\python.exe -m venv venv
.\venv\Scripts\activate

pip install torch==2.1.2+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install transformers==4.44.0 "numpy<2"
pip install TTS fastapi uvicorn scipy

deactivate
cd ..
```

**Voice reference sample** — place a clean 6–30 second WAV or MP3 of the desired voice at:

```
assets\Jarvis.mp3
```

XTTS v2 clones the voice from this sample on every synthesis. Better audio quality = more consistent output. Use a sample with no background noise and clear speech.

**Model download** — on first run, XTTS v2 (~1.9GB) downloads automatically from HuggingFace.

---

## 6. Electron UI

```powershell
cd electron
npm install
cd ..
```

---

## 7. Microsoft Graph / Outlook Setup

Jarvis uses a public client OAuth2 flow (no client secret required for token refresh).

1. Go to [portal.azure.com](https://portal.azure.com) → Azure Active Directory → App registrations → New registration
2. Name: `Jarvis`, Supported account types: `Personal Microsoft accounts only`
3. Add redirect URI: `http://localhost` (Mobile and desktop applications)
4. Under API permissions, add: `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`, `Contacts.Read`
5. Copy the **Application (client) ID** → `MS_CLIENT_ID` in `.env`
6. Generate a refresh token using the OAuth device flow or any standard tool and set it as `MS_REFRESH_TOKEN`

---

## 8. First Launch

Jarvis auto-starts the XTTS service and Electron on boot. You only need one command:

```powershell
C:\Python314\python.exe main.py
```

**Startup sequence:**
1. XTTS service launches in a new console (waits up to 60 seconds for model load)
2. Jarvis UI server starts on port 8765
3. Electron HUD opens in fullscreen
4. JARVIS speaks the boot message once XTTS confirms ready
5. Wake word detection begins ("Hey JARVIS")

---

## 9. Running the Local LLM Separately

If you want to pre-warm the Nemotron model before starting Jarvis (reduces first-query latency):

```powershell
# In a separate terminal
local_llm_service\start.bat
```

Wait for `Model ready.` before speaking to Jarvis. If it's not running, all queries route to Claude (cloud) automatically.

---

## 10. Port Reference

| Port | Service | Notes |
|---|---|---|
| 8765 | Jarvis UI / WebSocket | FastAPI — main interface |
| 8766 | Electron focus endpoint | HTTP — Python calls this to bring window forward |
| 8001 | Local LLM service | Nemotron Mini 4B |
| 8002 | XTTS voice service | Coqui XTTS v2 |

---

## 11. Package Version Matrix

These exact versions are required for the GPU services. Other combinations will break.

| Package | Version | Why pinned |
|---|---|---|
| `torch` | `2.1.2+cu121` | CUDA 12.1, compatible with RTX 4000 series |
| `transformers` | `4.44.0` | 5.x dropped APIs used by bitsandbytes and TTS |
| `bitsandbytes` | `0.43.3` | 0.44+ has `impl_abstract` incompatibility with torch 2.1.2 |
| `accelerate` | `0.21.0` | 1.x calls `.to()` on quantized models which is forbidden |
| `numpy` | `<2` (→ 1.26.4) | numpy 2.x breaks torch 2.1.2 C extensions |

---

## 12. Troubleshooting

**`EADDRINUSE 8766`** — Old Electron still running. Kill it from Task Manager or restart the machine. Jarvis now handles this gracefully in newer versions.

**`address already in use :8765`** — Old Jarvis process still alive. Jarvis auto-kills it on startup via `_kill_port()`. If it persists: `Get-Process python | Stop-Process -Force`.

**XTTS voice inconsistent between sessions** — Jarvis now auto-starts the XTTS service on boot. If you see "using Edge TTS fallback" it means XTTS failed to load — check the XTTS console for errors.

**Local LLM not used** — Check that `local_llm_service\start.bat` ran successfully and printed `Model ready.`. The router only sends matching-pattern queries to the local model; everything else goes to Claude.

**`impl_abstract` error in bitsandbytes** — Wrong bitsandbytes version. Run: `pip install bitsandbytes==0.43.3` inside the relevant venv.

**GPU memory error on model load** — You need at least 3GB free VRAM for Nemotron and 4GB for XTTS. Close other GPU-heavy applications. Both can run simultaneously on an RTX 4070 (12GB).

**Wake word not triggering** — Ensure your default microphone is set in Windows Sound settings. Try lowering `WAKE_WORD_THRESHOLD` in `config.py` (default: 0.5).

---

## Updating

```powershell
git pull
C:\Python314\python.exe main.py
```

Version is shown in the Electron HUD bottom bar and at `GET http://localhost:8765/version`.
