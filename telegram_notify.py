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


def _load_dotenv():
    """Baca .env di folder screener (kalau ada) ke os.environ — tanpa library tambahan.
    .env sudah di .gitignore, jadi token tidak akan ke-commit. Railway pakai Variables,
    jadi .env di sana tidak dibutuhkan."""
    env_file = BASE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()


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


KEY_SYMBOLS = ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "DXY"]


def _td_line(td):
    """Satu baris Top-Down + SnR untuk satu simbol, misal:
    🥇 <b>XAUUSD</b> 🔴 Bearish (4/5) • W▼ D▼ H4▼ H1• M15▼
       S 3,642.10 (-1.0%) • R 3,751.10 (+1.9%) — di Support"""
    bias = td["bias"]
    emoji = "🟢" if bias == "Bullish" else ("🔴" if bias == "Bearish" else "⚪")
    medal = {"XAUUSD": "🥇", "XAGUSD": "🥈"}.get(td["symbol"], "▫️")
    short = {"Weekly": "W", "Daily": "D", "H4": "H4", "H1": "H1", "M15": "M15"}
    arrows = " ".join(f"{short[tf]}{td['tfs'].get(tf, {}).get('arrow', '?')}"
                      for tf in ["Weekly", "Daily", "H4", "H1", "M15"])
    snr = td.get("snr") or {}

    def _fmt(levels):
        if not levels:
            return "-"
        parts = []
        for c in levels:
            tag = " H4" if c.get("tf") == "H4" else ""
            parts.append(f"{c['price']:,} ({c['dist_pct']:+.1f}%, {c['touches']}x{tag})")
        return " / ".join(parts)
    sup, res = _fmt(snr.get("support")), _fmt(snr.get("resistance"))
    status = snr.get("status", "-")
    return (f"{medal} <b>{td['symbol']}</b> {emoji} {bias} ({td['aligned']}) • {arrows}\n"
            f"   S {sup} • R {res} — {status}")


def build_message(all_rows, now_str, topdown=None, source=None):
    """Bangun pesan ringkas dari hasil screener (dict Daily/H1 -> rows),
    plus blok Top-Down & SnR kalau data topdown tersedia."""
    lines = [f"<b>📊 Forex Screener — {now_str}</b>", ""]
    if topdown:
        lines.append("<b>📐 Top-Down &amp; SnR</b> (W/D/H4/H1/M15)")
        for sym in KEY_SYMBOLS:
            td = topdown.get(sym)
            if td:
                lines.append(_td_line(td))
        lines.append("Eksekusi: tunggu konfirmasi H1/M15 di dekat level S/R.")
        # CRT terbaru yang masih aktif (maks 2 bar terakhir) — pemicu sweep
        fresh_crt = []
        for sym in KEY_SYMBOLS:
            td = topdown.get(sym)
            if not td:
                continue
            for tf in ("H4", "Daily"):
                s = (td.get("crt") or {}).get(tf)
                if s and s["status"] == "active" and s["bars_ago"] <= 2:
                    arrow = "▲" if s["direction"] == "Bullish" else "▼"
                    fresh_crt.append(
                        f"{sym} {tf} {arrow} {s['direction']} "
                        f"(tgt {s['target']:,}, inval {s['invalidation']:,})"
                    )
                    break
        if fresh_crt:
            lines.append("<b>⚡ CRT aktif:</b> " + " • ".join(fresh_crt))
        lines.append("")
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
    lines.append(f"Sumber: {source or 'Yahoo Finance'}. Bukan saran trading — oversold ≠ sinyal buy.")
    return "\n".join(lines)


def build_scalp_message(rows, sessions, now_str, source=None):
    """Pesan ringkas mode scalping untuk Telegram."""
    lines = [f"<b>⚡ Scalp Mode — {now_str}</b>",
             f"Sesi aktif: {', '.join(sessions)} (WIB)", ""]
    for r in sorted(rows, key=lambda x: x["score"], reverse=True):
        snr = r.get("snr_m15") or {}
        sup = (snr.get("support") or [{}])[0]
        res = (snr.get("resistance") or [{}])[0]
        sr = []
        if sup.get("price") is not None:
            sr.append(f"S {sup['price']:,} ({sup['dist_pct']:+.1f}%)")
        if res.get("price") is not None:
            sr.append(f"R {res['price']:,} ({res['dist_pct']:+.1f}%)")
        lines.append(
            f"{r['emoji']} <b>{r['symbol']}</b> {r['price']:,} • "
            f"<b>{r['signal']}</b> (skor {r['score']:+d})"
        )
        lines.append(
            f"   Trend M15 {r['trend_m15']} / H1 {r['trend_h1']} / D1 {r['trend_d1']} • "
            f"Stoch M5 {r['stoch_k']}/{r['stoch_d']} • RSI M5 {r['rsi_m5']}"
        )
        lines.append(
            f"   SL {r['sl']:,} ({r['sl_pips']} pip) • TP1 {r['tp1']:,} • TP2 {r['tp2']:,}"
        )
        crt = r.get("crt") or {}
        crt_bits = []
        for tf in ("M15", "H1"):
            s = crt.get(tf)
            if s and s["status"] == "active":
                arrow = "▲" if s["direction"] == "Bullish" else "▼"
                crt_bits.append(f"{tf} {arrow} {s['direction']} (tgt {s['target']:,})")
        if crt_bits:
            lines.append(f"   ⚡ CRT: {' • '.join(crt_bits)}")
        if sr:
            lines.append(f"   S/R M15: {' • '.join(sr)}")
    lines.append("")
    lines.append("Trigger: cross Stochastic di M5, trend M15/H1/D1 searah. Bukan saran trading.")
    if source:
        lines.append(f"Sumber: {source}.")
    return "\n".join(lines)


def _pct_diff(a, b):
    """Selisih % a vs b, atau None kalau tidak bisa dihitung."""
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1) * 100

def build_compare_message(rows, now_str):
    """Pesan ringkas perbandingan sumber untuk Telegram (HTML).

    rows = hasil run_compare: [{symbol, spot_xaus, yahoo, biquote, xaus}]
    dengan tiap sumber berisi dict hasil analyse() atau None.
    """
    lines = [f"<b>⚖️ Banding Sumber — {now_str}</b>", ""]
    for rec in rows:
        sym = rec["symbol"]
        yh, bq, xa = rec.get("yahoo"), rec.get("biquote"), rec.get("xaus")
        lines.append(f"<b>{sym}</b>")
        for label, r in (("Yahoo", yh), ("Biquote", bq), ("XAUS", xa)):
            if r:
                lines.append(
                    f"{label} {r['price']:,} • RSI {r['rsi14']} • "
                    f"{r['score']:+d} {r['signal']}"
                )
        # XAUS spot saja (perak/BTC tanpa histori Daily)
        if not xa and rec.get("spot_xaus") is not None:
            lines.append(f"XAUS {rec['spot_xaus']:,} (spot)")
        diffs = []
        yh_p = yh["price"] if yh else None
        bq_p = bq["price"] if bq else None
        xa_p = xa["price"] if xa else rec.get("spot_xaus")
        d = _pct_diff(bq_p, yh_p)
        if d is not None:
            diffs.append(f"Bq {d:+.2f}%")
        d = _pct_diff(xa_p, yh_p)
        if d is not None:
            diffs.append(f"XAUS {d:+.2f}%")
        if diffs:
            lines.append(f"Selisih: {' • '.join(diffs)}")
        lines.append("")
    lines.append("Yahoo = futures, Biquote/XAUS = spot. Bukan saran trading.")
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
        msg = build_message(data.get("data", {}), data.get("generated_wib", ""),
                            data.get("topdown"), source=data.get("source"))
        ok = send_text(msg, token, chat_id)
        sys.exit(0 if ok else 1)
    print("Tidak ada output/latest.json — jalankan screener.py dulu.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
