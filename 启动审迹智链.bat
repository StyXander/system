@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "AUDITTRACE_PY=backend\.venv\Scripts\python.exe"
set "AUDITTRACE_CODEX_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%AUDITTRACE_PY%" (
  echo [First run] Creating the local Python environment...
  py -3 --version >nul 2>&1
  if not errorlevel 1 (
    py -3 -m venv backend\.venv
  ) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
      python -m venv backend\.venv
    ) else (
      if exist "%AUDITTRACE_CODEX_PY%" (
        "%AUDITTRACE_CODEX_PY%" -m venv backend\.venv
      ) else (
        goto :failed
      )
    )
  )
  if errorlevel 1 goto :failed
)

"%AUDITTRACE_PY%" -c "import fastapi,uvicorn,dotenv" >nul 2>&1
if errorlevel 1 (
  echo [First run] Installing required packages...
  "%AUDITTRACE_PY%" -m pip install -r backend\requirements.txt
  if errorlevel 1 goto :failed
)

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo Created .env. A model key is optional for R1 calculation.
)

if defined AUDITTRACE_VALIDATE_ONLY goto :end

echo.
echo AuditTrace is starting at http://127.0.0.1:8000
echo Keep this window open. Closing it stops the local service.
if not defined AUDITTRACE_NO_BROWSER start "" "http://127.0.0.1:8000"
"%AUDITTRACE_PY%" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
goto :end

:failed
echo.
echo Startup failed. Install Python 3.10 or newer, then run this file again.

:end
if not defined AUDITTRACE_NO_PAUSE pause
endlocal
