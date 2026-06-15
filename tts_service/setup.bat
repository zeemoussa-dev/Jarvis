@echo off
echo Setting up XTTS v2 TTS service...
py -3.11 -m venv venv
call venv\Scripts\activate
pip install torch==2.1.2+cu121 torchaudio==2.1.2+cu121 --extra-index-url https://download.pytorch.org/whl/cu121
pip install TTS==0.22.0 fastapi uvicorn scipy numpy
echo.
echo Setup complete! Run start.bat to launch the TTS service.
pause
