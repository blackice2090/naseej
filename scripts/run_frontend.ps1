# Run the Naseej React frontend (Vite dev server).
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..\naseej-ai")
npm run dev
