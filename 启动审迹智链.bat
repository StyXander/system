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
  "%AUDITTRACE_PY%" -m pip install -r backend\requirements-lock.txt
  if errorlevel 1 goto :failed
)

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo Created .env. A model key is optional for R1 calculation.
)

if defined AUDITTRACE_VALIDATE_ONLY goto :end

rem 本启动器只绑定 127.0.0.1，允许评审现场接入新的巨潮公开年报样例。
rem 云端共享部署不会经过本启动器，仍保持默认只读。
rem 是否调用真实外部模型只由本机 .env 的 AUDITTRACE_DEMO_USE_EXTERNAL_MODEL 显式控制；
rem 本启动器不设置该变量，避免覆盖 .env 中的明确选择。
set "AUDITTRACE_DEMO_MODE=true"
set "AUDITTRACE_ONSITE_LIVE_SAMPLE=true"
set "AUDITTRACE_PROVIDER_PROBE_ENABLED=true"

rem Avoid duplicate services only when the running process exposes this demo's
rem bootstrap contract. A stale backend can still serve /api/health=200 while
rem leaving the new frontend permanently stuck in the booting state.
powershell -NoProfile -Command "try { $h=Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; $b=Invoke-RestMethod 'http://127.0.0.1:8000/api/demo/bootstrap' -TimeoutSec 3; if($h.service_status -eq 'ready' -and $b.schema_version -eq 'demo_bootstrap_v1' -and [int]$b.case_count -eq 15){ exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
  echo.
  echo AuditTrace is already running at http://127.0.0.1:8000
  if not defined AUDITTRACE_NO_BROWSER start "" "http://127.0.0.1:8000"
  goto :end
)

rem Do not pretend that an incompatible process on port 8000 is this build.
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',8000); if($c.Connected){ exit 0 } } catch {}; finally { $c.Dispose() }; exit 1" >nul 2>&1
if not errorlevel 1 (
  echo.
  echo Startup blocked: port 8000 is occupied by an incompatible or stale AuditTrace process.
  echo Close that service window, then run this launcher once more.
  goto :failed_running
)

echo.
echo AuditTrace is starting at http://127.0.0.1:8000
echo Keep this window open. Closing it stops the local service.
if not defined AUDITTRACE_NO_BROWSER start "" "http://127.0.0.1:8000"
rem Keep normal usage on one stable process so background tasks are not reloaded.
rem Set AUDITTRACE_RELOAD=1 explicitly when auto-reload is needed for development.
if defined AUDITTRACE_RELOAD (
  "%AUDITTRACE_PY%" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
) else (
  "%AUDITTRACE_PY%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
)
goto :end

:failed
echo.
echo Startup failed. Install Python 3.10 or newer, then run this file again.
goto :end

:failed_running
echo The launcher did not report a false success and did not stop an unverified process.
if not defined AUDITTRACE_NO_PAUSE pause
endlocal
exit /b 1

:end
if not defined AUDITTRACE_NO_PAUSE pause
endlocal
