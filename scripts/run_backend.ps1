# Run the Naseej FastAPI backend in dev mode.
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..")
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
