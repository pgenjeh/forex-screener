#!/usr/bin/env python3
"""
Pip Forex Screener — multi-symbol XAUUSD, XAGUSD, majors & crosses
====================================================================
Tanpa API key. Sumber: Yahoo Finance Chart API (public, gratis)
  https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>

Cara pakai:
  python3 screener.py                 # default: Top-Down semua symbol (W/D/H4/H1/M15 + SnR)
  python3 screener.py --symbols XAUUSD XAGUSD EURUSD
  python3 screener.py --timeframe 1d  # hanya daily
  python3 screener.py --timeframe 1h  # hanya H1
  python3 screener.py --timeframe both  # daily + H1 (lama)
  python3 screener.py --out md        # output markdown saja
  python3 screener.py --alert         # cetak hanya sinyal kuat / RSI ekstrem
  python3 screener.py --telegram      # + kirim ringkasan ke Telegram
                                      # butuh env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                                      # lihat TELEGRAM_SETUP.md

Teknik (sesuai gaya Abyan):
  Top-Down Analysis (Multi-Timeframe): bias dibaca dari Weekly -> Daily ->
  H4 -> H1 -> M15. TF besar menentukan arah, TF kecil menentukan timing.
  Bobot skor: W 30%, D 30%, H4 20%, H1 10%, M15 10%.
  Eksekusi pakai Support & Resistance: level S/R dihitung dari swing
  high/low (pivot) Daily (+ H4) yang sudah diuji >= 1x; harga yang dekat
  level (<=0.5 ATR) = zona pantau breakout / bounce.

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

def resample_4h(df):
    """Gabung candle 1H menjadi 4H (Yahoo tidak punya interval 4H)."""
    if df is None or len(df) < 80:
        return None
    d = df.set_index("time").resample("4h").agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"})
    return d.dropna().reset_index()


def find_snr(df, price, atr_val, digits, window=5):
    """Support & Resistance dari swing high/low (pivot) yang di-cluster.

    Level = harga pivot yang berdekatan (<=0.5 ATR) digabung jadi satu zona,
    touches = berapa kali level itu diuji. Return 2 Support terdekat di
    bawah harga + 2 Resistance terdekat di atas harga, lengkap dengan jarak
    dalam % dan ATR, plus status posisi harga terhadap level.
    """
    if df is None or len(df) < window * 2 + 10 or not atr_val:
        return {"support": [], "resistance": [], "status": "data kurang"}
    high = df["high"].values
    low = df["low"].values
    piv_hi, piv_lo = [], []
    for i in range(window, len(df) - window):
        if high[i] == high[i - window:i + window + 1].max():
            piv_hi.append(float(high[i]))
        if low[i] == low[i - window:i + window + 1].min():
            piv_lo.append(float(low[i]))

    def cluster(levels):
        if not levels:
            return []
        levels = sorted(levels)
        tol = 0.5 * atr_val
        groups = [[levels[0]]]
        for lv in levels[1:]:
            avg = sum(groups[-1]) / len(groups[-1])
            if abs(lv - avg) <= tol:
                groups[-1].append(lv)
            else:
                groups.append([lv])
        return [{"price": round(sum(g) / len(g), digits), "touches": len(g)}
                for g in groups]

    res = sorted([c for c in cluster(piv_hi) if c["price"] > price],
                 key=lambda c: c["price"])[:2]
    sup = sorted([c for c in cluster(piv_lo) if c["price"] < price],
                 key=lambda c: c["price"], reverse=True)[:2]
    for c in res:
        c["dist_pct"] = round((c["price"] / price - 1) * 100, 2)
        c["dist_atr"] = round((c["price"] - price) / atr_val, 1)
    for c in sup:
        c["dist_pct"] = round((c["price"] / price - 1) * 100, 2)
        c["dist_atr"] = round((price - c["price"]) / atr_val, 1)
    if sup and sup[0]["dist_atr"] <= 0.5:
        status = "di Support"
    elif res and res[0]["dist_atr"] <= 0.5:
        status = "di Resistance"
    elif not res:
        status = "tanpa Resistance dekat"
    elif not sup:
        status = "tanpa Support dekat"
    else:
        status = "mid-range"
    return {"support": sup, "resistance": res, "status": status}


TF_WEIGHTS = {"Weekly": 0.30, "Daily": 0.30, "H4": 0.20, "H1": 0.10, "M15": 0.10}
TF_ORDER = ["Weekly", "Daily", "H4", "H1", "M15"]


def build_topdown(symbol, rows_by_tf, snr):
    """Gabung bias semua TF jadi satu kesimpulan Top-Down."""
    tfs, wsum, wtot, bull, bear = {}, 0.0, 0.0, 0, 0
    for label in TF_ORDER:
        row = rows_by_tf.get(label)
        if not row:
            continue
        arrow = "▲" if row["score"] >= 25 else ("▼" if row["score"] <= -25 else "•")
        tfs[label] = {"trend": row["trend"], "score": row["score"],
                      "rsi14": row["rsi14"], "arrow": arrow}
        w = TF_WEIGHTS.get(label, 0)
        wsum += w * row["score"]
        wtot += w
        if row["score"] >= 25:
            bull += 1
        elif row["score"] <= -25:
            bear += 1
    wscore = int(round(wsum / wtot)) if wtot else 0
    n = len(tfs)
    if wscore >= 25:
        bias = "Bullish"
    elif wscore <= -25:
        bias = "Bearish"
    else:
        bias = "Mixed"
    return {"symbol": symbol, "bias": bias, "weighted_score": wscore,
            "aligned": f"{max(bull, bear)}/{n}", "bull": bull, "bear": bear,
            "tfs": tfs, "snr": snr}


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

def _snr_status(snr):
    """Status posisi harga vs level S/R terdekat (Daily / H4)."""
    for side, label in (("support", "di Support"), ("resistance", "di Resistance")):
        lvls = snr.get(side) or []
        if lvls and lvls[0].get("dist_atr", 99) <= 0.5:
            tag = " (H4)" if lvls[0].get("tf") == "H4" else ""
            return label + tag
    if not (snr.get("resistance") or []):
        return "tanpa Resistance dekat"
    if not (snr.get("support") or []):
        return "tanpa Support dekat"
    return "mid-range"


def _snr_str(levels):
    """'3,642.10 (-1.0%, 2x)' per level, digabung koma. Kosong -> '-'."""
    if not levels:
        return "-"
    parts = []
    for c in levels:
        tag = ", H4" if c.get("tf") == "H4" else ""
        parts.append(f"{c['price']:,} ({c['dist_pct']:+.1f}%, {c['touches']}x{tag})")
    return ", ".join(parts)

def print_topdown(topdown, now_wib):
    print(f"\n=== TOP-DOWN + SnR  •  {now_wib.strftime('%d %b %Y %H:%M WIB')} ===")
    print("Bias = skor tertimbang W30/D30/H4 20/H1 10/M15 10. S/R = pivot Daily.")
    print(f"{'Symbol':<8} {'W':>2} {'D':>2} {'H4':>2} {'H1':>2} {'M15':>3}  {'Bias':<8} {'Skor':>5}  {'Selaras':>7}  {'Support terdekat':<28} {'Resistance terdekat':<28} Status")
    print("-" * 130)
    for sym, td in sorted(topdown.items(), key=lambda kv: kv[1]["weighted_score"], reverse=True):
        arrows = {tf: td["tfs"].get(tf, {}).get("arrow", "?") for tf in TF_ORDER}
        snr = td.get("snr") or {}
        print(f"{sym:<8} {arrows['Weekly']:>2} {arrows['Daily']:>2} {arrows['H4']:>2} {arrows['H1']:>2} {arrows['M15']:>3}  {td['bias']:<8} {td['weighted_score']:>+5}  {td['aligned']:>7}  {_snr_str(snr.get('support')):<28} {_snr_str(snr.get('resistance')):<28} {snr.get('status', '-')}")
    print("-" * 130)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=list(SYMBOLS.keys()),
                    help="contoh: --symbols XAUUSD XAGUSD EURUSD")
    ap.add_argument("--timeframe", choices=["1d", "1h", "both", "topdown"], default="topdown")
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
    topdown = {}

    # --- timeframe apa saja yang diminta ---
    if args.timeframe == "topdown":
        wanted = ["Weekly", "Daily", "H4", "H1", "M15"]
    elif args.timeframe == "1d":
        wanted = ["Daily"]
    elif args.timeframe == "1h":
        wanted = ["H1"]
    else:  # both (lama)
        wanted = ["Daily", "H1"]

    # --- ambil data sekali per simbol, turunkan semua TF dari situ ---
    # H4 = resample candle 1H; H1 = 5 hari terakhir dari 1H 1 bulan.
    for sym in args.symbols:
        sym = sym.upper()
        if sym not in SYMBOLS:
            print(f"⚠️  {sym} tidak dikenal, skip. Pilihan: {', '.join(SYMBOLS)}")
            continue
        cfg = SYMBOLS[sym]
        dfs = {}
        try:
            if "Weekly" in wanted:
                dfs["Weekly"] = fetch_yahoo(cfg["yahoo"], "1wk", "5y")
            if "Daily" in wanted:
                # 5 tahun: SnR butuh histori panjang (harga sedang di low 1 tahun,
                # support terdekat bisa berasal dari struktur lama).
                dfs["Daily"] = fetch_yahoo(cfg["yahoo"], "1d", "5y")
            if "H4" in wanted or "H1" in wanted:
                df60 = fetch_yahoo(cfg["yahoo"], "60m", "1mo")
                if df60 is not None:
                    if "H4" in wanted:
                        dfs["H4"] = resample_4h(df60)
                    if "H1" in wanted:
                        dfs["H1"] = df60.tail(150).reset_index(drop=True)
            if "M15" in wanted:
                dfs["M15"] = fetch_yahoo(cfg["yahoo"], "15m", "5d")
        except Exception as e:
            print(f"⚠️  {sym}: gagal ambil data ({e})")
            continue
        rows_by_tf = {}
        for label in TF_ORDER:
            df = dfs.get(label)
            if df is None:
                continue
            row = analyse(sym, cfg, df)
            if row:
                row["timeframe"] = label
                rows_by_tf[label] = row
                all_rows.setdefault(label, []).append(row)
            else:
                print(f"⚠️  {sym} ({label}): data kurang / gagal")
        if not rows_by_tf:
            print(f"⚠️  {sym}: data kurang / gagal")
            continue
        # --- SnR dari Daily (+ H4 sebagai pelengkap) ---
        snr = None
        daily_row = rows_by_tf.get("Daily")
        if daily_row and dfs.get("Daily") is not None:
            snr = find_snr(dfs["Daily"], daily_row["price"], daily_row["atr"], cfg["digits"])
            if dfs.get("H4") is not None and rows_by_tf.get("H4"):
                h4 = find_snr(dfs["H4"], rows_by_tf["H4"]["price"],
                              rows_by_tf["H4"]["atr"], cfg["digits"])
                snr["h4"] = h4
                # Level H4 lebih dekat & relevan untuk eksekusi: tampilkan
                # di depan kalau level Daily terlalu jauh (>3%) atau tidak ada.
                for side in ("support", "resistance"):
                    cur = snr.get(side) or []
                    if (not cur or abs(cur[0]["dist_pct"]) > 3) and h4.get(side):
                        lvl = dict(h4[side][0])
                        lvl["tf"] = "H4"
                        snr[side] = [lvl] + cur[:1]
                snr["status"] = _snr_status(snr)
        topdown[sym] = build_topdown(sym, rows_by_tf, snr)

    if not all_rows:
        print("Tidak ada data. Cek internet / Yahoo Finance.")
        sys.exit(1)

    # --- tampilkan tabel per TF ---
    for label, rows in all_rows.items():
        view = rows
        if args.alert:
            view = [r for r in rows if abs(r["score"]) >= 60 or r["rsi14"] <= 30 or r["rsi14"] >= 70]
            if not view:
                print(f"\n[{label}] Tidak ada alert — semua netral.")
                continue
        if args.out in ("all", "console"):
            print_table(view, label, now)

    # --- tabel Top-Down & SnR ---
    if topdown and args.out in ("all", "console"):
        print_topdown(topdown, now)

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
            payload = {"generated_wib": now.isoformat(), "source": "Yahoo Finance Chart API",
                       "data": all_rows, "topdown": topdown}
            (OUT / f"screener_{stamp}.json").write_text(json.dumps(payload, indent=2))
            (OUT / "latest.json").write_text(json.dumps(payload, indent=2))
        if args.out in ("all", "md"):
            lines = [f"# Forex Screener — {now.strftime('%d %b %Y %H:%M WIB')}",
                     "", "Sumber: Yahoo Finance (GC=F, SI=F, EURUSD=X, dst). Bukan saran trading.",
                     "", "## Top-Down & SnR",
                     "Bias = skor tertimbang W30/D30/H4 20/H1 10/M15 10. "
                     "S/R = pivot Daily (touches = jumlah pengujian level).",
                     "", "| Symbol | W | D | H4 | H1 | M15 | Bias | Skor | Selaras | Support terdekat | Resistance terdekat | Status |",
                     "|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for sym, td in sorted(topdown.items(), key=lambda kv: kv[1]["weighted_score"], reverse=True):
                ar = {tf: td["tfs"].get(tf, {}).get("arrow", "?") for tf in TF_ORDER}
                snr = td.get("snr") or {}
                lines.append(f"| {sym} | {ar['Weekly']} | {ar['Daily']} | {ar['H4']} | {ar['H1']} | {ar['M15']} | **{td['bias']}** | {td['weighted_score']:+d} | {td['aligned']} | {_snr_str(snr.get('support'))} | {_snr_str(snr.get('resistance'))} | {snr.get('status', '-')} |")
            lines.append("")
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
            msg = build_message(all_rows, now.strftime('%d %b %Y %H:%M WIB'), topdown)
            print("\n📩 Mengirim ke Telegram...")
            send_text(msg)
            if args.telegram_file:
                send_file(OUT / "latest.md", caption="Hasil screener lengkap")
        except Exception as e:
            print(f"⚠️  Telegram gagal: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
