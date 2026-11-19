#!/usr/bin/env python3
"""
Pip Forex Screener — multi-symbol XAUUSD, XAGUSD, majors & crosses
====================================================================
Tanpa API key. Sumber: Yahoo Finance Chart API (public, gratis)
  https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>

Cara pakai:
  python3 screener.py                 # scan semua symbol, daily + H1
  python3 screener.py --symbols XAUUSD XAGUSD EURUSD
  python3 screener.py --timeframe 1d  # hanya daily
  python3 screener.py --timeframe 1h  # hanya H1
  python3 screener.py --out md        # output markdown saja
  python3 screener.py --alert         # cetak hanya sinyal kuat / RSI ekstrem
  python3 screener.py --telegram      # + kirim ringkasan ke Telegram
                                      # butuh env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                                      # lihat TELEGRAM_SETUP.md

Output:
  output/screener_YYYY-MM-DD_HHMM-WIB.csv
  output/screener_YYYY-MM-DD_HHMM-WIB.json
  output/screener_YYYY-MM-DD_HHMM-WIB.md
  output/latest.csv / latest.json / latest.md  (selalu overwrite)

Indikator per symbol:
  Harga, Chg%, EMA20/50/200, RSI14, ATR14 (harga + pips),
  Momentum 5d & 20d, posisi vs High/Low 20d, Trend, Skor -100..+100, Sinyal.
"""
import argparse, csv, json, math, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
OUT.mkdir(parents=True, exist_ok=True)
WIB = timezone(timedelta(hours=7))

# ---------------------------------------------------------------- symbols
# Yahoo ticker, digit/pip-size, nama
SYMBOLS = {
    "XAUUSD": {"yahoo": "GC=F",      "pip": 0.10, "digits": 2, "name": "Gold / USD"},
    "XAGUSD": {"yahoo": "SI=F",      "pip": 0.01, "digits": 3, "name": "Silver / USD"},
    "EURUSD": {"yahoo": "EURUSD=X",  "pip": 0.0001, "digits": 5, "name": "Euro / USD"},
    "GBPUSD": {"yahoo": "GBPUSD=X",  "pip": 0.0001, "digits": 5, "name": "Pound / USD"},
    "USDJPY": {"yahoo": "USDJPY=X",  "pip": 0.01, "digits": 3, "name": "USD / Yen"},
    "AUDUSD": {"yahoo": "AUDUSD=X",  "pip": 0.0001, "digits": 5, "name": "AUD / USD"},
    "USDCAD": {"yahoo": "USDCAD=X",  "pip": 0.0001, "digits": 5, "name": "USD / CAD"},
    "NZDUSD": {"yahoo": "NZDUSD=X",  "pip": 0.0001, "digits": 5, "name": "NZD / USD"},
    "USDCHF": {"yahoo": "USDCHF=X",  "pip": 0.0001, "digits": 5, "name": "USD / Franc"},
    "EURJPY": {"yahoo": "EURJPY=X",  "pip": 0.01, "digits": 3, "name": "Euro / Yen"},
    "GBPJPY": {"yahoo": "GBPJPY=X",  "pip": 0.01, "digits": 3, "name": "Pound / Yen"},
    "EURGBP": {"yahoo": "EURGBP=X",  "pip": 0.0001, "digits": 5, "name": "Euro / Pound"},
    "DXY":    {"yahoo": "DX-Y.NYB",  "pip": 0.01, "digits": 2, "name": "US Dollar Index"},
    "BTCUSD": {"yahoo": "BTC-USD",   "pip": 1.0, "digits": 0, "name": "Bitcoin / USD"},
}

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Pip-Forex-Screener/1.0"}

# ---------------------------------------------------------------- helpers
def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def rsi(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def atr(df, n=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([(high-low), (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def fetch_yahoo(ticker, interval, range_):
    """Return DataFrame OHLC atau None."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": interval, "range": range_, "includePrePost": "false"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()["chart"]["result"]
    if not data:
        return None
    res = data[0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "time": pd.to_datetime(ts, unit="s", utc=True),
        "open": q.get("open"), "high": q.get("high"),
        "low": q.get("low"), "close": q.get("close"),
        "volume": q.get("volume"),
    }).dropna(subset=["close"])
    return df

def analyse(symbol, cfg, df):
    if df is None or len(df) < 60:
        return None
    close = df["close"]
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    chg = (price - prev) / prev * 100
    chg5 = (price / float(close.iloc[-6]) - 1) * 100 if len(df) > 5 else 0
    chg20 = (price / float(close.iloc[-21]) - 1) * 100 if len(df) > 20 else 0
    e20 = float(ema(close, 20).iloc[-1]); e50 = float(ema(close, 50).iloc[-1])
    e200 = float(ema(close, 200).iloc[-1]) if len(df) >= 200 else float(ema(close, len(df)).iloc[-1])
    r = float(rsi(close, 14).iloc[-1])
    a = float(atr(df, 14).iloc[-1])
    pip = cfg["pip"]
    hi20 = float(df["high"].tail(20).max()); lo20 = float(df["low"].tail(20).min())
    pos20 = (price - lo20) / (hi20 - lo20) * 100 if hi20 > lo20 else 50

    # --- skor -100..+100 ---
    score = 0
    score += 25 if price > e50 else -25
    score += 15 if price > e20 else -15
    score += 10 if e20 > e50 else -10
    score += 10 if price > e200 else -10
    score += max(-15, min(15, (r - 50) * 0.5))          # RSI menjauh dari 50
    score += max(-10, min(10, chg5 * 2))                # momentum 5d
    score += max(-10, min(10, (pos20 - 50) * 0.2))      # posisi dalam range 20d
    score = int(round(max(-100, min(100, score))))

    if r >= 70: rsi_tag = "Overbought"
    elif r <= 30: rsi_tag = "Oversold"
    elif r >= 60: rsi_tag = "Kuat"
    elif r <= 40: rsi_tag = "Lemah"
    else: rsi_tag = "Netral"

    if score >= 60: signal = "STRONG BUY"
    elif score >= 25: signal = "BUY"
    elif score <= -60: signal = "STRONG SELL"
    elif score <= -25: signal = "SELL"
    else: signal = "NEUTRAL"

    if price > e50 and price > e200: trend = "Bullish"
    elif price < e50 and price < e200: trend = "Bearish"
    else: trend = "Mixed"

    return {
        "symbol": symbol, "name": cfg["name"], "price": round(price, cfg["digits"]),
        "chg_pct": round(chg, 2), "chg5_pct": round(chg5, 2), "chg20_pct": round(chg20, 2),
        "ema20": round(e20, cfg["digits"]), "ema50": round(e50, cfg["digits"]),
        "ema200": round(e200, cfg["digits"]),
        "rsi14": round(r, 1), "rsi_tag": rsi_tag,
        "atr": round(a, cfg["digits"]), "atr_pips": round(a / pip, 1),
        "high20": round(hi20, cfg["digits"]), "low20": round(lo20, cfg["digits"]),
        "pos20_pct": round(pos20, 0),
        "trend": trend, "score": score, "signal": signal,
        "day_high": round(float(df["high"].iloc[-1]), cfg["digits"]),
        "day_low": round(float(df["low"].iloc[-1]), cfg["digits"]),
    }

def fmt_price(v, digits):
    return f"{v:,.{digits}f}"

def print_table(rows, tf_label, now_wib):
    print(f"\n=== PIP SCREENER  •  {tf_label}  •  {now_wib.strftime('%d %b %Y %H:%M WIB')} ===")
    print(f"{'Symbol':<8} {'Harga':>12} {'Chg%':>7} {'RSI':>5} {'ATR(pip)':>9} {'EMA50':>12} {'Trend':<8} {'Skor':>5}  Sinyal")
    print("-" * 96)
    for r in sorted(rows, key=lambda x: x["score"], reverse=True):
        digits = SYMBOLS[r["symbol"]]["digits"]
        print(f"{r['symbol']:<8} {fmt_price(r['price'], digits):>12} {r['chg_pct']:>+7.2f} {r['rsi14']:>5.1f} {r['atr_pips']:>9.1f} {fmt_price(r['ema50'], digits):>12} {r['trend']:<8} {r['score']:>+5}  {r['signal']} ({r['rsi_tag']})")
    print("-" * 96)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=list(SYMBOLS.keys()),
                    help="contoh: --symbols XAUUSD XAGUSD EURUSD")
    ap.add_argument("--timeframe", choices=["1d", "1h", "both"], default="both")
    ap.add_argument("--out", choices=["all", "md", "csv", "json", "console"], default="all")
    ap.add_argument("--alert", action="store_true", help="hanya tampilkan sinyal kuat / RSI ekstrem")
    ap.add_argument("--telegram", action="store_true",
                    help="kirim ringkasan ke Telegram (env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")
    ap.add_argument("--telegram-file", action="store_true",
                    help="ikut kirim output/latest.md sebagai file Telegram")
    args = ap.parse_args()

    if pd is None:
        print("Butuh pandas + numpy + requests. Jalankan: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(WIB)
    stamp = now.strftime("%Y-%m-%d_%H%M")
    all_rows = {}

    tfs = []
    if args.timeframe in ("1d", "both"): tfs.append(("Daily", "1d", "6mo"))
    if args.timeframe in ("1h", "both"): tfs.append(("H1", "60m", "5d"))

    for tf_label, interval, range_ in tfs:
        rows = []
        for sym in args.symbols:
            sym = sym.upper()
            if sym not in SYMBOLS:
                print(f"⚠️  {sym} tidak dikenal, skip. Pilihan: {', '.join(SYMBOLS)}")
                continue
            try:
                df = fetch_yahoo(SYMBOLS[sym]["yahoo"], interval, range_)
                row = analyse(sym, SYMBOLS[sym], df)
                if row:
                    row["timeframe"] = tf_label
                    rows.append(row)
                else:
                    print(f"⚠️  {sym} ({tf_label}): data kurang / gagal")
            except Exception as e:
                print(f"⚠️  {sym} ({tf_label}): {e}")
        if not rows:
            continue
        all_rows[tf_label] = rows
        view = rows
        if args.alert:
            view = [r for r in rows if abs(r["score"]) >= 60 or r["rsi14"] <= 30 or r["rsi14"] >= 70]
            if not view:
                print(f"\n[{tf_label}] Tidak ada alert — semua netral.")
                continue
        if args.out in ("all", "console"):
            print_table(view, tf_label, now)

    if not all_rows:
        print("Tidak ada data. Cek internet / Yahoo Finance.")
        sys.exit(1)

    # --- simpan file (pakai Daily sebagai utama, H1 sebagai tambahan) ---
    flat = [r for rows in all_rows.values() for r in rows]
    if args.out in ("all", "csv", "json", "md"):
        if args.out in ("all", "csv"):
            for label, rows in all_rows.items():
                tag = label.lower()
                with open(OUT / f"screener_{stamp}-{tag}.csv", "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader(); w.writerows(rows)
            with open(OUT / "latest.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
                w.writeheader(); w.writerows(flat)
        if args.out in ("all", "json"):
            payload = {"generated_wib": now.isoformat(), "source": "Yahoo Finance Chart API", "data": all_rows}
            (OUT / f"screener_{stamp}.json").write_text(json.dumps(payload, indent=2))
            (OUT / "latest.json").write_text(json.dumps(payload, indent=2))
        if args.out in ("all", "md"):
            lines = [f"# Forex Screener — {now.strftime('%d %b %Y %H:%M WIB')}",
                     "", "Sumber: Yahoo Finance (GC=F, SI=F, EURUSD=X, dst). Bukan saran trading.",
                     ""]
            for label, rows in all_rows.items():
                lines.append(f"## {label}")
                lines.append("| Symbol | Harga | Chg% | RSI | ATR(pip) | Trend | Skor | Sinyal |")
                lines.append("|---|---|---|---|---|---|---|---|")
                for r in sorted(rows, key=lambda x: x["score"], reverse=True):
                    d = SYMBOLS[r["symbol"]]["digits"]
                    lines.append(f"| {r['symbol']} | {fmt_price(r['price'], d)} | {r['chg_pct']:+.2f}% | {r['rsi14']} ({r['rsi_tag']}) | {r['atr_pips']} | {r['trend']} | {r['score']:+d} | **{r['signal']}** |")
                lines.append("")
            (OUT / f"screener_{stamp}.md").write_text("\n".join(lines))
            (OUT / "latest.md").write_text("\n".join(lines))
        print(f"\n💾 Tersimpan di {OUT}/  (screener_{stamp}.* + latest.*)")

    # --- Telegram (opsional) ---
    if args.telegram:
        try:
            from telegram_notify import build_message, send_text, send_file
            msg = build_message(all_rows, now.strftime('%d %b %Y %H:%M WIB'))
            print("\n📩 Mengirim ke Telegram...")
            send_text(msg)
            if args.telegram_file:
                send_file(OUT / "latest.md", caption="Hasil screener lengkap")
        except Exception as e:
            print(f"⚠️  Telegram gagal: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
