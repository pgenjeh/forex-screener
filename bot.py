#!/usr/bin/env python3
"""
Bot Telegram Pip Forex Screener — jawab perintah kapan saja (on-demand).

Bukan cuma kirim jadwal: bot ini "dengerin" Telegram terus (long polling
getUpdates) dan membalas perintah dari kamu. Jadi kapan pun mau cek market,
tinggal chat bot-nya, nggak perlu buka Muse atau nunggu jam 07:00 / 19:30.

Perintah:
  /cek     -> Top-Down lengkap (semua simbol, W/D/H4/H1/M15 + SnR)
  /xau     -> emas & perak saja (XAUUSD, XAGUSD)
  /majors  -> EURUSD, GBPUSD, USDJPY, DXY
  /snr     -> S/R 6 simbol utama (XAU, XAG, EURUSD, GBPUSD, USDJPY, DXY)
  /scalp   -> mode scalping: M1/M5/M15 + H1/D1, Stochastic + MA, SL/TP dari ATR
  /help    -> daftar perintah
  /start   -> salam + daftar perintah

Keamanan: bot HANYA menjawab chat yang id-nya sama dengan TELEGRAM_CHAT_ID
(env / .env). Pesan dari orang lain diabaikan diam-diam.

Env yang dibutuhkan (sama seperti telegram_notify.py):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

Jalan bareng scheduler di Railway lewat run_services.py:
  python3 run_services.py

Jalan sendiri (test lokal):
  python3 bot.py
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from telegram_notify import _load_dotenv, send_text  # noqa: E402

_load_dotenv()

WIB = timezone(timedelta(hours=7))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
COOLDOWN_SEC = 60  # jeda minimum antar run screener (biar nggak spam Yahoo)

HELP_TEXT = (
    "👋 <b>Pip Forex Screener</b>\n\n"
    "Chat aku kapan saja:\n"
    "  /cek — Top-Down lengkap (semua simbol)\n"
    "  /xau — emas &amp; perak (XAUUSD, XAGUSD)\n"
    "  /majors — EURUSD, GBPUSD, USDJPY, DXY\n"
    "  /snr — S/R 6 simbol utama\n"
    "  /scalp — mode scalping (M1/M5/M15 + H1/D1, Stochastic + MA)\n"
    "  /help — daftar perintah ini\n\n"
    "Teknik: Top-Down W/D/H4/H1/M15, eksekusi di S/R — tunggu konfirmasi\n"
    "H1/M15 dekat level sebelum masuk. Scalp: trigger cross Stochastic M5,\n"
    "trend M15/H1/D1 searah, SL 0.5 ATR / TP 1-2 ATR (M15).\n\n"
    "Jadwal otomatis tetap jalan tiap 07:00 &amp; 19:30 WIB. "
    "Bukan saran trading — oversold ≠ sinyal buy."
)

# perintah -> argumen screener.py (default timeframe = topdown)
COMMANDS = {
    "/cek": [],
    "/xau": ["--symbols", "XAUUSD", "XAGUSD"],
    "/majors": ["--symbols", "EURUSD", "GBPUSD", "USDJPY", "DXY"],
    "/snr": ["--symbols", "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "DXY"],
    "/scalp": ["--mode", "scalping"],
}

_last_run = 0.0


def log(msg):
    print(f"[{datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}] [bot] {msg}", flush=True)


def is_allowed(chat_id) -> bool:
    """Hanya chat id Abyan yang boleh pakai bot ini."""
    return str(chat_id) == str(CHAT_ID)


def parse_command(text):
    """Ambil perintah dari teks pesan. Return nama perintah atau None.

    '/cek@namabot argumen' -> '/cek'. Bukan perintah -> None.
    """
    if not text:
        return None
    first = text.strip().split()[0].lower()
    if not first.startswith("/"):
        return None
    return first.split("@")[0]


def cooldown_left():
    """Detik tersisa sebelum boleh run screener lagi (0 = boleh)."""
    return max(0, int(COOLDOWN_SEC - (time.time() - _last_run)))


def run_screener(args):
    """Jalankan screener.py (dia yang kirim ringkasan ke Telegram)."""
    global _last_run
    _last_run = time.time()
    cmd = [sys.executable, str(BASE / "screener.py"), "--telegram"] + args
    log(f"▶ Menjalankan: {' '.join(cmd[2:])}")
    try:
        r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and "Telegram terkirim" in out:
            return True, ""
        return False, out[-300:]
    except Exception as e:
        return False, str(e)


def handle_update(update):
    """Proses 1 update dari getUpdates. Return True kalau diproses."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return False
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not is_allowed(chat_id):
        log(f"⛔ Abaikan pesan dari chat id {chat_id} (bukan pemilik).")
        return False
    text = msg.get("text", "")
    cmd = parse_command(text)
    if cmd in ("/start", "/help"):
        send_text(HELP_TEXT)
        return True
    if cmd in COMMANDS:
        left = cooldown_left()
        if left:
            send_text(f"⏳ Baru saja ngecek — coba lagi dalam {left} detik ya.")
            return True
        send_text("⏳ Lagi ngecek market, sebentar ya…")
        ok, err = run_screener(COMMANDS[cmd])
        if ok:
            log("✅ Hasil on-demand terkirim.")
        else:
            log(f"❌ Screener gagal: {err}")
            send_text("❌ Maaf, screener gagal jalan. Coba /cek lagi sebentar lagi.")
        return True
    if cmd is not None:  # perintah tidak dikenal
        send_text("Perintah itu belum ada. Coba /help untuk daftar perintah.")
        return True
    return False  # bukan perintah — diam saja


def get_updates(offset, timeout=30):
    r = requests.get(f"{API}/getUpdates",
                     params={"offset": offset, "timeout": timeout,
                             "allowed_updates": ["message"]},
                     timeout=timeout + 10)
    if r.status_code == 401:
        log("❌ Token Telegram salah / tidak valid (401). Cek TELEGRAM_BOT_TOKEN.")
        sys.exit(1)
    if r.status_code == 409:
        log("⚠️  Ada bot lain yang juga polling (409) — mungkin 2 instance jalan. Tunggu 10 dtk…")
        time.sleep(10)
        return []
    if r.status_code != 200:
        log(f"⚠️  getUpdates gagal ({r.status_code}): {r.text[:200]}")
        time.sleep(5)
        return []
    return r.json().get("result", [])


def main():
    if not TOKEN or not CHAT_ID:
        print("Set dulu: export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...",
              file=sys.stderr)
        print("Cara dapatnya: lihat TELEGRAM_SETUP.md", file=sys.stderr)
        sys.exit(2)
    log("Bot mulai mendengarkan… (perintah: /cek /xau /majors /snr /scalp /help)")
    offset = None
    # Lewati pesan lama yang menumpuk sebelum bot nyala, biar tidak dibalas semua.
    try:
        old = get_updates(offset, timeout=0)
        if old:
            offset = old[-1]["update_id"] + 1
            log(f"Lewati {len(old)} pesan lama.")
    except SystemExit:
        raise
    except Exception as e:
        log(f"⚠️  Gagal baca pesan lama: {e}")
    while True:
        try:
            for update in get_updates(offset):
                offset = update["update_id"] + 1
                handle_update(update)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            log("Bot berhenti.")
            break
        except Exception as e:
            log(f"⚠️  Error loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
