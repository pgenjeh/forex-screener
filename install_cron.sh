#!/bin/bash
# Pasang cron Pip Forex Screener (aman: tidak menghapus cron lain)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/run_screener.sh" "$DIR/screener.py" "$DIR/scheduler.py" 2>/dev/null || true
mkdir -p "$DIR/logs" "$DIR/output"

# ganti path home di file cron sesuai lokasi sebenarnya
sed "s|/home/hatch/workspace/forex-screener|$DIR|g" "$DIR/forex-screener.cron" > /tmp/pip-forex.cron

# gabung dengan crontab yang sudah ada (buang duplikat baris screener lama)
(crontab -l 2>/dev/null | grep -v "forex-screener" || true; cat /tmp/pip-forex.cron) | crontab -
rm /tmp/pip-forex.cron

echo "✅ Cron terpasang. Cek dengan: crontab -l"
crontab -l | grep -A2 -B2 forex-screener || crontab -l
echo ""
echo "Test sekali jalan: $DIR/run_screener.sh"
echo "Log: tail -f $DIR/logs/run.log"
echo "Alternatif tanpa cron (loop python): nohup python3 $DIR/scheduler.py >> $DIR/logs/scheduler.log 2>&1 &"
