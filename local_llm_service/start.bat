@echo off
cd /d %~dp0
set HF_TOKEN=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
call venv\Scripts\activate
python service.py
