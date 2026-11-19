#!/usr/bin/env python3
"""
Scheduler Pip Forex Screener — tanpa library tambahan (stdlib saja).
Jalan terus di background, jalankan screener tiap interval saat market buka.

Jadwal (WIB, Senin-Jumat):
  - Setiap 30 menit, 07:00-23:00  -> screener daily+H1
  - Setiap Senin 07:05            -> ringkasan mingguan (sama, tapi log ditandai)
  - Di luar jam / weekend         -> tidur, cek tiap 10 menit

Pakai:
  python3 scheduler.py                 # jalan di foreground (untuk test)
  nohup python3 scheduler.py >> logs/scheduler.log 2>&1 &
  # ATAU lebih disarankan: pakai cron (lihat install_cron.sh)

Berhenti: Ctrl+C

Telegram: kalau env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID di-set, scheduler
kirim ringkasan ke Telegram tiap jam di TELEGRAM_TIMES (default "07:00,19:30" WIB).
Di Railway, isi kedua env itu di Variables — bot jalan 24 jam, kamu dapat
notif di Telegram tanpa buka Muse. Lihat TELEGRAM_SETUP.md.
"""
import os
import subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
WIB = timezone(timedelta(hours=7))
LOGDIR = BASE / "logs"
LOGDIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    line = f"[{datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}] {msg}"
    print(line, flush=True)
    with open(LOGDIR / "scheduler.log", "a") as f:
        f.write(line + "\n")

def market_open(now):
    # Senin=0 ... Jumat=4, 07:00-23:00 WIB
    return now.weekday() < 5 and 7 <= now.hour < 23

def telegram_times():
    raw = os.environ.get("TELEGRAM_TIMES", "07:00,19:30")
    return {t.strip() for t in raw.split(",") if t.strip()}

def run_screener(send_telegram=False):
    log("▶ Menjalankan screener..." + (" + Telegram" if send_telegram else ""))
    try:
        cmd = [sys.executable, str(BASE / "screener.py")]
        if send_telegram:
            cmd += ["--telegram"]
        r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        # simpan output terakhir
        (LOGDIR / "last_run.txt").write_text(out)
        if r.returncode == 0:
            # ringkas: hanya baris sinyal kuat
            strong = [l for l in out.splitlines() if "STRONG" in l]
            log("✅ Selesai. Sinyal kuat: " + (" | ".join(strong) if strong else "tidak ada"))
        else:
            log(f"❌ Gagal (exit {r.returncode}): {out[-500:]}")
    except Exception as e:
        log(f"❌ Error: {e}")

def main():
    log("Pip scheduler mulai. Interval 30 menit saat market buka (Sen-Jum 07:00-23:00 WIB).")
    log(f"Telegram times: {sorted(telegram_times())} WIB (set TELEGRAM_TIMES untuk ubah)")
    last_run_minute = -1
    while True:
        try:
            now = datetime.now(WIB)
            if market_open(now) and now.minute % 30 == 0 and now.minute != last_run_minute:
                last_run_minute = now.minute
                send_tg = now.strftime("%H:%M") in telegram_times()
                run_screener(send_telegram=send_tg)
            elif not market_open(now):
                if now.minute % 10 == 0 and now.minute != last_run_minute:
                    last_run_minute = now.minute
                    log("Market tutup / weekend — tidur.")
            time.sleep(20)
        except KeyboardInterrupt:
            log("Scheduler berhenti (Ctrl+C).")
            break

if __name__ == "__main__":
    main()
