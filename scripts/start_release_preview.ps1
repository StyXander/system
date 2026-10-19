$ErrorActionPreference = 'Stop'
$env:AUDITTRACE_DEMO_USE_EXTERNAL_MODEL = 'false'
$env:AUDITTRACE_DEMO_EXECUTOR_MODE = 'web'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8774
