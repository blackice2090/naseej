#!/usr/bin/env bash
# Run the Naseej React frontend (Vite dev server).
set -euo pipefail
cd "$(dirname "$0")/../naseej-ai"
exec npm run dev
