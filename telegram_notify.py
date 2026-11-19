#!/usr/bin/env python3
"""
Kirim hasil screener ke Telegram — tanpa library tambahan.
Pakai Bot API resmi: https://api.telegram.org/bot<TOKEN>/sendMessage

Env yang dibutuhkan (jangan di-commit! isi di Railway Variables / .env):
  TELEGRAM_BOT_TOKEN=123456:ABC-...   # dari @BotFather
  TELEGRAM_CHAT_ID=123456789          # id kamu / grup, dari @userinfobot atau getUpdates
  TELEGRAM_TIMES=07:00,19:30          # dipakai scheduler.py (opsional)

Test:
  TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python3 telegram_notify.py --test
  TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python3 screener.py --telegram
"""
import json
import os
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent


def get_config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return token, chat_id


def send_text(text, token=None, chat_id=None, parse_mode="HTML"):
    """Kirim 1 pesan (di-split otomatis kalau >4096 karakter). Return True/False."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("⚠️  Telegram skip: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum di-set.", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram max 4096 karakter per pesan — potong per 4000
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [""]
    ok = True
    for chunk in chunks:
        r = requests.post(url, json={
            "chat_id": chat_id, "text": chunk,
            "parse_mode": parse_mode, "disable_web_page_preview": True,
        }, timeout=20)
        if r.status_code != 200:
            print(f"❌ Telegram gagal ({r.status_code}): {r.text[:300]}", file=sys.stderr)
            ok = False
        else:
            print("✅ Telegram terkirim.")
    return ok


def send_file(path, caption="", token=None, chat_id=None):
    """Kirim file (misal output/latest.md) sebagai dokumen."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("⚠️  Telegram skip: token/chat_id belum di-set.", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(path, "rb") as f:
        r = requests.post(url, data={"chat_id": chat_id, "caption": caption[:1024]},
                          files={"document": (Path(path).name, f)}, timeout=30)
    if r.status_code != 200:
        print(f"❌ Telegram kirim file gagal ({r.status_code}): {r.text[:300]}", file=sys.stderr)
        return False
    print(f"✅ File {path} terkirim ke Telegram.")
    return True


def build_message(all_rows, now_str):
    """Bangun pesan ringkas dari hasil screener (dict Daily/H1 -> rows)."""
    lines = [f"<b>📊 Forex Screener — {now_str}</b>", ""]
    daily = all_rows.get("Daily") or []
    if daily:
        # Sorot XAU / XAG dulu
        for r in daily:
            if r["symbol"] in ("XAUUSD", "XAGUSD"):
                emoji = "🥇" if r["symbol"] == "XAUUSD" else "🥈"
                lines.append(
                    f"{emoji} <b>{r['symbol']}</b> {r['price']:,} "
                    f"({r['chg_pct']:+.2f}%) • RSI {r['rsi14']} {r['rsi_tag']} • "
                    f"{r['trend']} • <b>{r['signal']}</b> (skor {r['score']:+d})"
                )
        lines.append("")
        strong_buy = [r for r in daily if r["score"] >= 60]
        strong_sell = [r for r in daily if r["score"] <= -60]
        if strong_buy:
            lines.append("<b>🟢 Terkuat:</b> " + ", ".join(
                f"{r['symbol']} +{r['score']}" for r in strong_buy))
        if strong_sell:
            lines.append("<b>🔴 Terlemah:</b> " + ", ".join(
                f"{r['symbol']} {r['score']}" for r in strong_sell))
        lines.append("")
        lines.append("<b>Daily:</b>")
        for r in sorted(daily, key=lambda x: x["score"], reverse=True):
            lines.append(
                f"{r['symbol']:8} {r['price']:,} ({r['chg_pct']:+.2f}%) "
                f"RSI {r['rsi14']} • {r['signal']}"
            )
    lines.append("")
    lines.append("Sumber: Yahoo Finance. Bukan saran trading — oversold ≠ sinyal buy.")
    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="kirim pesan test")
    ap.add_argument("--file", help="kirim file ini sebagai dokumen")
    ap.add_argument("--text", help="kirim teks ini")
    args = ap.parse_args()
    token, chat_id = get_config()
    if not token or not chat_id:
        print("Set dulu: export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...",
              file=sys.stderr)
        print("Cara dapatnya: lihat TELEGRAM_SETUP.md", file=sys.stderr)
        sys.exit(2)
    if args.test:
        ok = send_text("✅ Test dari Pip Forex Screener — bot Telegram kamu sudah terhubung!", token, chat_id)
        sys.exit(0 if ok else 1)
    if args.file:
        ok = send_file(args.file, caption="Hasil screener terbaru", token=token, chat_id=chat_id)
        sys.exit(0 if ok else 1)
    if args.text:
        ok = send_text(args.text, token, chat_id)
        sys.exit(0 if ok else 1)
    # default: kirim hasil latest.json kalau ada
    latest = BASE / "output" / "latest.json"
    if latest.exists():
        data = json.loads(latest.read_text())
        msg = build_message(data.get("data", {}), data.get("generated_wib", ""))
        ok = send_text(msg, token, chat_id)
        sys.exit(0 if ok else 1)
    print("Tidak ada output/latest.json — jalankan screener.py dulu.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
