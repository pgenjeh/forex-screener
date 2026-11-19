#!/bin/bash
# Wrapper screener — dipakai cron & manual. Log ke logs/
# Usage: ./run_screener.sh [--alert] [--symbols XAUUSD XAGUSD ...]
set -e
cd "$(dirname "$0")"
mkdir -p logs output
# pakai venv kalau ada, kalau tidak pakai python3 sistem
if [ -x "venv/bin/python" ]; then PY="venv/bin/python"; else PY="python3"; fi
echo "[$(TZ=Asia/Jakarta date '+%Y-%m-%d %H:%M:%S WIB')] ▶ screener $*" >> logs/run.log
"$PY" screener.py "$@" >> logs/run.log 2>&1
echo "[$(TZ=Asia/Jakarta date '+%Y-%m-%d %H:%M:%S WIB')] ✅ selesai" >> logs/run.log
