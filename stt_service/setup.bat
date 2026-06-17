@echo off
cd /d %~dp0
set PYTHON311=C:\Users\mahmo\AppData\Local\Programs\Python\Python311\python.exe
title Jarvis STT Setup — Parakeet TDT 1.1B

echo ============================================================
echo  JARVIS STT Service Setup — Parakeet TDT 1.1B (NeMo + CUDA)
echo ============================================================
echo.

echo [1/5] Creating Python 3.11 venv...
"%PYTHON311%" -m venv venv
if errorlevel 1 ( echo ERROR: Failed to create venv & pause & exit /b 1 )
echo       Done.
echo.

echo [2/5] Installing PyTorch 2.1.2 + CUDA 12.1 (~2 GB download)...
venv\Scripts\pip.exe install torch==2.1.2+cu121 --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 ( echo ERROR: PyTorch install failed & pause & exit /b 1 )
echo       Done.
echo.

echo [3/5] Installing NeMo ASR toolkit (~1 GB)...
venv\Scripts\pip.exe install "nemo_toolkit[asr]"
if errorlevel 1 ( echo ERROR: NeMo install failed & pause & exit /b 1 )
echo       Done.
echo.

echo [4/5] Pinning numpy for torch compatibility...
venv\Scripts\pip.exe install "numpy<2"
echo       Done.
echo.

echo [5/5] Installing service dependencies...
venv\Scripts\pip.exe install fastapi uvicorn python-multipart soundfile librosa
echo       Done.
echo.

echo ============================================================
echo  Setup complete. Run start.bat to launch Parakeet STT.
echo ============================================================
pause
