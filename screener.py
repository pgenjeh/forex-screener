#!/usr/bin/env python3
"""
Pip Forex Screener — multi-symbol XAUUSD, XAGUSD, majors & crosses
====================================================================
Tanpa API key. Sumber: Yahoo Finance Chart API (public, gratis) — utama;
  Biquote (feed MT5 live, gratis tanpa key) — fallback otomatis kalau Yahoo
  gagal/rate-limit; XAUS (xaus.com, gratis tanpa key) — emas saja, buat
  perbandingan. Pilih manual: --source yahoo|biquote|xaus|auto (default auto),
  atau env SCREENER_SOURCE. Bandingkan ketiganya: --compare.

Cara pakai:
  python3 screener.py                 # default: Top-Down semua symbol (W/D/H4/H1/M15 + SnR)
  python3 screener.py --symbols XAUUSD XAGUSD EURUSD
  python3 screener.py --timeframe 1d  # hanya daily
  python3 screener.py --timeframe 1h  # hanya H1
  python3 screener.py --timeframe both  # daily + H1 (lama)
  python3 screener.py --mode scalping # mode scalping: M1/M5/M15 + H1/D1, Stochastic + MA
  python3 screener.py --mode scalping --symbols XAUUSD
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

  Mode scalping (sesuai setup MT5 Abyan): trigger Stochastic (14,3,3) cross
  di M5, filter trend M15/H1/D1 searah (MA 9/21/50/200 + EMA 20/50),
  konfirmasi RSI14 + Stochastic M1, SL 0.5 ATR / TP1 1 ATR / TP2 2 ATR
  (ATR M15), S/R dari pivot M15, plus sesi market yang sedang buka
  (Sydney/Tokyo/London/New York, jam WIB). On-demand saja — sinyal M1/M5
  cepat basi, jadi tidak dijadwalkan. Telegram: /scalp di bot.

  MSNR + CRT (ditambahkan 20 Nov 2026):
  - MSNR (Malaysian SNR): level dari close/open candle (A/V/Gap/OCL),
    hanya level fresh yang ditampilkan; RBS/SBR saat close menembus level.
    Dihitung di D1 + H4 (Top-Down) dan M15 (scalping).
  - CRT (Candle Range Theory, ICT): candle C2 nyapu high/low candle C1
    lalu close balik ke dalam range -> target sisi seberang, invalidasi di
    extreme sweep. Hanya candle tutup yang dinilai. Dihitung di H4 + D1
    (Top-Down) dan M15 + H1 (scalping). CRT searah trend HTF = konfluensi
    terkuat; CRT lawan trend = hati-hati (mean-reversion).

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

# ---------------------------------------------------------------- sumber data
# Yahoo = utama (Daily 5 thn, semua 14 simbol). Biquote = fallback gratis
# tanpa key (feed MT5 live, 15.000 req/menit/IP, 2.081 simbol incl. DXY) —
# dipakai kalau Yahoo gagal/rate-limit. Biquote tidak punya interval 1w
# (di-resample dari Daily) dan retensi tiap interval terbatas: Daily ~500 bar
# (~19 bln), 1h ~169 bar (~7 hari) — jadi H4 dari resample 1h Biquote
# terlalu pendek, dipakai interval 4h native Biquote sebagai gantinya.
# Harga Biquote = spot MT5, Yahoo = futures (GC=F/SI=F): emas bisa beda
# ~$3-10, forex/DXY praktis identik.
BIQUOTE_BASE = "https://biquote.io/api"
BIQUOTE_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                     "60m": "1h", "1d": "1d", "4h": "4h"}
SOURCES_USED = set()  # sumber yang benar-benar dipakai di run ini
_SRC_NAMES = {"yahoo": "Yahoo Finance", "biquote": "Biquote (feed MT5)",
              "xaus": "XAUS (xaus.com)"}

def source_label():
    """Label sumber untuk output (MD/JSON/Telegram)."""
    if SOURCES_USED == {"biquote"}:
        return "Biquote (feed MT5)"
    if SOURCES_USED == {"xaus"}:
        return "XAUS (xaus.com)"
    if SOURCES_USED == {"yahoo", "biquote"}:
        return "Yahoo Finance + Biquote (fallback)"
    if len(SOURCES_USED) > 1:
        return " + ".join(_SRC_NAMES[s] for s in sorted(SOURCES_USED)) + " (campuran)"
    return "Yahoo Finance Chart API"

# ---------------------------------------------------------------- helpers
def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def sma(series, n):
    return series.rolling(n).mean()

def stochastic(df, k_period=14, k_smooth=3, d_smooth=3):
    """Stochastic (14,3,3) ala MT5: return (K, D) series."""
    low_n = df["low"].rolling(k_period).min()
    high_n = df["high"].rolling(k_period).max()
    raw_k = 100 * (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan)
    k = raw_k.rolling(k_smooth).mean()
    d = k.rolling(d_smooth).mean()
    return k, d

def current_sessions(now_wib):
    """Sesi market yang sedang buka (jam WIB, perkiraan jam standar)."""
    h = now_wib.hour + now_wib.minute / 60
    sessions = []
    if 5 <= h < 13:
        sessions.append("Sydney")
    if 7 <= h < 15:
        sessions.append("Tokyo")
    if 15 <= h < 23:
        sessions.append("London")
    if h >= 21 or h < 4:
        sessions.append("New York")
    return sessions or ["—"]

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

def fetch_biquote(symbol, interval, range_):
    """Return DataFrame OHLC dari Biquote (feed MT5, gratis tanpa key) atau None.

    Respons Biquote newest-first -> diurutkan menaik. Bar terakhir = candle
    forming (isOpen=true), sama seperti Yahoo, jadi analyse/MSNR/CRT yang
    memang mengabaikan bar terakhir tetap konsisten.

    Retensi Biquote (bukan limit request): Daily ~500 bar (~19 bln),
    1h ~169 bar (~7 hari), 4h ~181 bar (~41 hari); 15m/5m/1m cukup untuk
    kebutuhan screener. Daily 5y -> yang didapat ~19 bln terakhir.
    """
    if interval == "1wk":
        # Biquote tidak punya interval mingguan -> resample dari Daily.
        df = fetch_biquote(symbol, "1d", range_)
        if df is None or len(df) < 60:
            return None
        d = df.set_index("time").resample("W").agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "volume": "sum"})
        return d.dropna().reset_index()
    bq_iv = BIQUOTE_INTERVALS.get(interval)
    if bq_iv is None:
        return None
    r = requests.get(f"{BIQUOTE_BASE}/{symbol}/ohlc",
                     params={"interval": bq_iv, "limit": 500},
                     headers=HEADERS, timeout=20)
    r.raise_for_status()
    bars = (r.json() or {}).get("bars") or []
    if not bars:
        return None
    bars = sorted(bars, key=lambda b: b["openTime"])
    df = pd.DataFrame({
        "time": pd.to_datetime([b["openTime"] for b in bars], utc=True),
        "open": [b.get("open") for b in bars],
        "high": [b.get("high") for b in bars],
        "low": [b.get("low") for b in bars],
        "close": [b.get("close") for b in bars],
        "volume": [b.get("tickVolume", 0) for b in bars],
    }).dropna(subset=["close"])
    return df if len(df) else None

XAUS_BASE = "https://xaus.com/api/v1"

def fetch_xaus_spot():
    """Harga spot live XAUS: {XAUUSD, XAGUSD, BTCUSD} atau None.

    Gratis tanpa key, 60 req/menit. Cuma tiga simbol ini yang ada spot-nya.
    """
    r = requests.get(f"{XAUS_BASE}/spot", params={"compact": "1"},
                     headers=HEADERS, timeout=20)
    r.raise_for_status()
    d = r.json() or {}
    out = {}
    if d.get("spot_usd_oz") is not None:
        out["XAUUSD"] = float(d["spot_usd_oz"])
    if d.get("silver_usd_oz") is not None:
        out["XAGUSD"] = float(d["silver_usd_oz"])
    if d.get("btc_usd") is not None:
        out["BTCUSD"] = float(d["btc_usd"])
    return out or None

def fetch_xaus(symbol, interval, range_):
    """Return DataFrame OHLC Daily XAUUSD dari XAUS (/v1/history) atau None.

    Cuma emas yang punya histori candle (daily OHLC 5 thn, tanpa open —
    open disintesis dari close hari sebelumnya). Bar hari ini belum ada di
    history (berhenti di close kemarin) -> ditambah forming bar dari spot
    live. Perak/BTC cuma ada spot, tanpa histori -> None (lihat
    fetch_xaus_spot). Forex/DXY tidak ada di XAUS -> None.
    """
    if symbol != "XAUUSD" or interval not in ("1d", "1wk"):
        return None
    r = requests.get(f"{XAUS_BASE}/history", headers=HEADERS, timeout=20)
    r.raise_for_status()
    pts = (r.json() or {}).get("points") or []
    if len(pts) < 60:
        return None
    closes = [float(p["c"]) for p in pts]
    opens = [closes[0]] + closes[:-1]  # open hari ini = close kemarin
    df = pd.DataFrame({
        "time": pd.to_datetime([p["d"] for p in pts], utc=True),
        "open": opens,
        "high": [float(p["h"]) for p in pts],
        "low": [float(p["l"]) for p in pts],
        "close": closes,
        "volume": 0,
    }).dropna(subset=["close"]).sort_values("time").reset_index(drop=True)
    # Forming bar hari ini dari spot live (history berhenti di close kemarin).
    try:
        spot = fetch_xaus_spot()
        today = datetime.now(timezone.utc).date()
        last_day = df["time"].iloc[-1].date()
        if spot and "XAUUSD" in spot and today > last_day:
            px = spot["XAUUSD"]
            prev = float(df["close"].iloc[-1])
            df = pd.concat([df, pd.DataFrame([{
                "time": pd.Timestamp(today, tz="UTC"),
                "open": prev, "high": max(prev, px), "low": min(prev, px),
                "close": px, "volume": 0,
            }])], ignore_index=True)
    except Exception:
        pass  # spot gagal -> pakai history apa adanya
    if interval == "1wk":
        d = df.set_index("time").resample("W").agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "volume": "sum"})
        return d.dropna().reset_index()
    return df

def fetch_data(symbol, interval, range_, source="auto"):
    """Ambil OHLC untuk satu simbol+TF.

    source: "auto" = Yahoo dulu, gagal/terlalu sedikit -> Biquote;
    "yahoo"/"biquote"/"xaus" = paksa satu sumber (xaus cuma emas Daily).
    Sumber yang berhasil dicatat di SOURCES_USED (dipakai label output).
    """
    cfg = SYMBOLS[symbol]
    order = {"auto": ("yahoo", "biquote"),
             "yahoo": ("yahoo",), "biquote": ("biquote",),
             "xaus": ("xaus",)}.get(source, ("yahoo", "biquote"))
    for src in order:
        try:
            if src == "yahoo":
                df = fetch_yahoo(cfg["yahoo"], interval, range_)
            elif src == "biquote":
                df = fetch_biquote(symbol, interval, range_)
            else:
                df = fetch_xaus(symbol, interval, range_)
        except Exception as e:
            print(f"⚠️  {symbol} ({interval}): {src} gagal ({e})")
            df = None
        if df is not None and len(df) >= 60:
            SOURCES_USED.add(src)
            return df
        if df is not None:
            print(f"⚠️  {symbol} ({interval}): {src} cuma {len(df)} bar, coba sumber lain...")
    return None

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
    """Gabung candle 1H menjadi 4H (Yahoo tidak punya interval 4H; Biquote
    punya, tapi resample dipakai biar H4 konsisten di semua sumber)."""
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


# ---------------------------------------------------------------- MSNR + CRT
def find_msnr_levels(df, atr_val, digits):
    """Level MSNR (Malaysian SNR) dari body candle, bukan wick.

    - A-level (resistance): candle bullish diikuti bearish, level = close
      candle bullish. V-level (support): kebalikannya.
    - Gap level: candle open menjauh dari close sebelumnya (>0.1 ATR),
      level = close sebelumnya.
    - OCL: run >= 3 candle sewarna, level = close candle pertama run itu.
    - Fresh: level dianggap fresh sampai wick candle berikutnya menyentuhnya.
    - RBS/SBR: candle close menembus level -> peran berbalik, fresh lagi.
    """
    if df is None or len(df) < 10 or not atr_val:
        return []
    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    levels = []  # {price, kind, side, formed, fresh, touches}

    def near(price, side):
        for lv in levels:
            if lv["side"] == side and abs(lv["price"] - price) <= 0.3 * atr_val:
                return True
        return False

    def add(price, kind, side, idx):
        if near(price, side):
            return
        levels.append({"price": round(float(price), digits), "kind": kind,
                       "side": side, "formed": int(idx), "fresh": True,
                       "touches": 0})

    run_start, run_dir, run_len = 0, 0, 0
    # Bar terakhir = candle forming (belum tutup) -> jangan dipakai, sama
    # seperti alert Pine yang digate barstate.isconfirmed.
    for j in range(1, n - 1):
        o, c = opens[j], closes[j]
        # (a) level lama: sentuh wick -> unfresh; close tembus -> flip RBS/SBR
        for lv in levels:
            p = lv["price"]
            if lv["side"] == "resistance":
                if highs[j] >= p:
                    lv["fresh"] = False
                    lv["touches"] += 1
                if c > p:
                    lv["side"] = "support"
                    lv["fresh"] = True
                    lv["formed"] = j
            else:
                if lows[j] <= p:
                    lv["fresh"] = False
                    lv["touches"] += 1
                if c < p:
                    lv["side"] = "resistance"
                    lv["fresh"] = True
                    lv["formed"] = j
        # (b) level baru dari pasangan bar j-1, j
        po, pc = opens[j - 1], closes[j - 1]
        bull_prev, bear_prev = pc > po, pc < po
        bull_cur, bear_cur = c > o, c < o
        if bull_prev and bear_cur:
            add(pc, "A", "resistance", j)
        elif bear_prev and bull_cur:
            add(pc, "V", "support", j)
        gap = o - pc
        if abs(gap) > 0.1 * atr_val:
            add(pc, "Gap", "support" if gap > 0 else "resistance", j)
        # (c) OCL: run sewarna >= 3 candle berakhir di bar j
        d = 1 if c > o else (-1 if c < o else 0)
        if d != 0 and d == run_dir:
            run_len += 1
        else:
            if run_len >= 3:
                add(closes[run_start], "OCL",
                    "support" if run_dir > 0 else "resistance", j)
            run_start, run_dir, run_len = j, d, 1 if d != 0 else 0
    if run_len >= 3:
        add(closes[run_start], "OCL",
            "support" if run_dir > 0 else "resistance", n - 2)
    return levels


def nearest_msnr(levels, price, atr_val, digits):
    """2 Support + 2 Resistance MSNR fresh terdekat (dengan jarak % dan ATR)."""
    sup = sorted([lv for lv in levels
                  if lv["side"] == "support" and lv["price"] < price and lv["fresh"]],
                 key=lambda x: x["price"], reverse=True)[:2]
    res = sorted([lv for lv in levels
                  if lv["side"] == "resistance" and lv["price"] > price and lv["fresh"]],
                 key=lambda x: x["price"])[:2]
    out = {"support": [], "resistance": []}
    for lv in sup:
        d = dict(lv)
        d["dist_pct"] = round((lv["price"] / price - 1) * 100, 2)
        d["dist_atr"] = round((price - lv["price"]) / atr_val, 1)
        out["support"].append(d)
    for lv in res:
        d = dict(lv)
        d["dist_pct"] = round((lv["price"] / price - 1) * 100, 2)
        d["dist_atr"] = round((lv["price"] - price) / atr_val, 1)
        out["resistance"].append(d)
    return out


def detect_crt(df, atr_val, digits, max_lookback=60):
    """Deteksi CRT (Candle Range Theory, ICT) pada candle yang sudah tutup.

    C1 = candle range (high/low-nya). C2 = candle berikutnya:
    - Bullish CRT: C2 nyapu low C1 (low < low C1) lalu close balik ke dalam
      range C1 -> target = high C1, invalidasi = low C2.
    - Bearish CRT: C2 nyapu high C1 lalu close balik ke dalam -> target =
      low C1, invalidasi = high C2.
    Outside bar (C2 jebol dua sisi) diabaikan. Range C1 minimal 0.5 ATR.
    Status dihitung dari bar setelah C2: 'target hit' / 'invalidated' /
    'active'. Hanya C2 yang sudah tutup yang dinilai (bar terakhir = forming).
    """
    if df is None or len(df) < 5 or not atr_val:
        return []
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    setups = []
    for i in range(max(1, n - max_lookback - 1), n - 2):
        c1h, c1l = float(highs[i]), float(lows[i])
        if c1h - c1l < 0.5 * atr_val:
            continue
        c2h, c2l, c2c = float(highs[i + 1]), float(lows[i + 1]), float(closes[i + 1])
        if c2h > c1h and c2l < c1l:
            continue  # outside bar
        setup = None
        if c2l < c1l and c1l < c2c <= c1h:
            setup = {"direction": "Bullish", "range_high": round(c1h, digits),
                     "range_low": round(c1l, digits), "target": round(c1h, digits),
                     "invalidation": round(c2l, digits),
                     "sweep_atr": round((c1l - c2l) / atr_val, 2)}
        elif c2h > c1h and c1l <= c2c < c1h:
            setup = {"direction": "Bearish", "range_high": round(c1h, digits),
                     "range_low": round(c1l, digits), "target": round(c1l, digits),
                     "invalidation": round(c2h, digits),
                     "sweep_atr": round((c2h - c1h) / atr_val, 2)}
        if not setup:
            continue
        setup["bars_ago"] = int(n - 1 - (i + 1))
        # status: cek bar setelah C2 sampai bar terakhir (termasuk forming)
        status = "active"
        for k in range(i + 2, n):
            if setup["direction"] == "Bullish":
                if float(lows[k]) < setup["invalidation"]:
                    status = "invalidated"
                    break
                if float(highs[k]) >= setup["target"]:
                    status = "target hit"
                    break
            else:
                if float(highs[k]) > setup["invalidation"]:
                    status = "invalidated"
                    break
                if float(lows[k]) <= setup["target"]:
                    status = "target hit"
                    break
        setup["status"] = status
        setups.append(setup)
    return setups


def latest_crt(setups):
    """Setup CRT terbaru yang masih active, atau yang terbaru apa pun."""
    if not setups:
        return None
    for s in reversed(setups):
        if s["status"] == "active":
            return s
    return setups[-1]


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

def _msnr_str(levels):
    """'3,642.10 (A, -1.0%)' per level, digabung koma. Kosong -> '-'."""
    if not levels:
        return "-"
    parts = []
    for c in levels:
        tag = ", H4" if c.get("tf") == "H4" else ""
        parts.append(f"{c['price']:,} ({c['kind']}{tag}, {c['dist_pct']:+.1f}%)")
    return ", ".join(parts)


def _crt_str(crt):
    """'H4 Bullish (1 bar, aktif, target 3,600)' atau '-'."""
    if not crt:
        return "-"
    parts = []
    for tf in ("H4", "Daily"):
        s = crt.get(tf)
        if not s:
            continue
        arrow = "▲" if s["direction"] == "Bullish" else "▼"
        parts.append(f"{tf} {arrow} {s['direction']} ({s['bars_ago']} bar, {s['status']}, tgt {s['target']:,})")
    return " | ".join(parts) if parts else "-"


def print_msnr_crt(topdown, now_wib):
    print(f"\n=== MSNR + CRT  •  {now_wib.strftime('%d %b %Y %H:%M WIB')} ===")
    print("MSNR: level fresh dari close candle (A/V/Gap/OCL, D1+H4). CRT: sweep + close balik ke dalam range (H4/D1).")
    print(f"{'Symbol':<8} {'MSNR Support fresh':<30} {'MSNR Resistance fresh':<30} CRT terbaru")
    print("-" * 128)
    for sym, td in sorted(topdown.items(), key=lambda kv: kv[1]["weighted_score"], reverse=True):
        msnr = td.get("msnr") or {}
        print(f"{sym:<8} {_msnr_str(msnr.get('support')):<30} {_msnr_str(msnr.get('resistance')):<30} {_crt_str(td.get('crt'))}")
    print("-" * 128)


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

# ---------------------------------------------------------------- scalping
SCALP_SYMBOLS = ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY"]
SCALP_TFS = ["M1", "M5", "M15", "H1", "D1"]

def scalp_tf(df):
    """Indikator scalping untuk 1 timeframe (setup MT5 Abyan):
    MA 9/21/50/200 (SMA 200), EMA 20/50, Stochastic (14,3,3), RSI14, ATR14."""
    if df is None or len(df) < 60:
        return None
    close = df["close"]
    price = float(close.iloc[-1])
    k, d = stochastic(df)
    kk, dd = float(k.iloc[-1]), float(d.iloc[-1])
    kp, dp = float(k.iloc[-2]), float(d.iloc[-2])
    e9 = float(ema(close, 9).iloc[-1]); e21 = float(ema(close, 21).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    s200 = float(sma(close, 200).iloc[-1]) if len(df) >= 200 else float(sma(close, len(df)).iloc[-1])
    r = float(rsi(close, 14).iloc[-1])
    a = float(atr(df, 14).iloc[-1])
    if price > e50 and price > s200:
        trend = "Bullish"
    elif price < e50 and price < s200:
        trend = "Bearish"
    else:
        trend = "Mixed"
    return {"price": price, "ema9": e9, "ema21": e21, "ema50": e50,
            "ma200": s200, "rsi14": r, "stoch_k": kk, "stoch_d": dd,
            "stoch_k_prev": kp, "stoch_d_prev": dp,
            "cross_up": kp < dp and kk >= dd,
            "cross_dn": kp > dp and kk <= dd,
            "atr": a, "trend": trend}


def analyse_scalp(symbol, cfg, tfs, snr_m15=None):
    """Gabung M1/M5/M15/H1/D1 jadi satu sinyal scalping.
    Trigger: Stochastic cross di M5. Filter: trend M15/H1/D1 searah."""
    if not tfs.get("M5") or not tfs.get("M15"):
        return None
    m5, m15 = tfs["M5"], tfs["M15"]
    m1 = tfs.get("M1")
    price = m5["price"]
    digits, pip = cfg["digits"], cfg["pip"]
    atr15 = m15["atr"]

    score = 0
    for tf, w in (("D1", 20), ("H1", 20), ("M15", 20)):
        t = tfs.get(tf)
        if not t:
            continue
        score += w if t["trend"] == "Bullish" else (-w if t["trend"] == "Bearish" else 0)
    if m5["stoch_k"] > m5["stoch_d"]:
        score += 10
    elif m5["stoch_k"] < m5["stoch_d"]:
        score -= 10
    if m5["stoch_k"] < 20:
        score += 5
    elif m5["stoch_k"] > 80:
        score -= 5
    if 50 <= m5["rsi14"] <= 70:
        score += 5
    elif 30 <= m5["rsi14"] < 50:
        score -= 5
    if m15["ema9"] > m15["ema21"] > m15["ema50"]:
        score += 10
    elif m15["ema9"] < m15["ema21"] < m15["ema50"]:
        score -= 10
    score = int(round(max(-100, min(100, score))))

    long_trig = m5["cross_up"] and m5["stoch_k"] < 40
    short_trig = m5["cross_dn"] and m5["stoch_k"] > 60
    m1_ok_long = (m1 is None) or (m1["stoch_k"] >= m1["stoch_d"])
    m1_ok_short = (m1 is None) or (m1["stoch_k"] <= m1["stoch_d"])
    if score >= 50 and long_trig and m1_ok_long:
        signal, emoji = "LONG SCALP", "🟢"
    elif score <= -50 and short_trig and m1_ok_short:
        signal, emoji = "SHORT SCALP", "🔴"
    elif score >= 40:
        signal, emoji = "SIAP LONG (tunggu cross M5)", "🟡"
    elif score <= -40:
        signal, emoji = "SIAP SHORT (tunggu cross M5)", "🟡"
    else:
        signal, emoji = "WAIT", "⚪"

    # SL/TP dari ATR M15: SL 0.5 ATR, TP1 1 ATR, TP2 2 ATR.
    direction = 1 if score >= 0 else -1
    sl_dist, tp1_dist, tp2_dist = 0.5 * atr15, 1.0 * atr15, 2.0 * atr15
    return {
        "symbol": symbol, "price": round(price, digits),
        "score": score, "signal": signal, "emoji": emoji,
        "trend_m15": m15["trend"],
        "trend_h1": tfs.get("H1", {}).get("trend", "-"),
        "trend_d1": tfs.get("D1", {}).get("trend", "-"),
        "stoch_k": round(m5["stoch_k"], 1), "stoch_d": round(m5["stoch_d"], 1),
        "rsi_m5": round(m5["rsi14"], 1),
        "atr_m15": round(atr15, digits), "atr_m15_pips": round(atr15 / pip, 1),
        "sl": round(price - direction * sl_dist, digits),
        "tp1": round(price + direction * tp1_dist, digits),
        "tp2": round(price + direction * tp2_dist, digits),
        "sl_pips": round(sl_dist / pip, 1),
        "tp1_pips": round(tp1_dist / pip, 1),
        "tp2_pips": round(tp2_dist / pip, 1),
        "snr_m15": snr_m15 or {},
        "tfs": {tf: {"trend": t["trend"], "rsi14": round(t["rsi14"], 1),
                     "stoch_k": round(t["stoch_k"], 1)}
                for tf, t in tfs.items()},
    }


def _crt_short(crt):
    """'M15▼ aktif' / 'H1▲ 2bar' / '-' — setup CRT terbaru yang masih aktif."""
    if not crt:
        return "-"
    for tf in ("M15", "H1"):
        s = crt.get(tf)
        if s and s["status"] == "active":
            arrow = "▲" if s["direction"] == "Bullish" else "▼"
            return f"{tf}{arrow} aktif"
    for tf in ("M15", "H1"):
        s = crt.get(tf)
        if s:
            arrow = "▲" if s["direction"] == "Bullish" else "▼"
            return f"{tf}{arrow} {s['bars_ago']}bar"
    return "-"


def print_scalp(rows, sessions, now_wib):
    print(f"\n=== SCALP MODE  •  Sesi: {', '.join(sessions)}  •  {now_wib.strftime('%d %b %Y %H:%M WIB')} ===")
    print("Trigger: Stochastic cross di M5. Filter: trend M15/H1/D1 searah. SL 0.5 ATR, TP1 1 ATR, TP2 2 ATR (M15).")
    print("CRT: sweep + close balik ke dalam range (M15/H1) — konfirmasi tambahan, searah trend lebih kuat.")
    print(f"{'Symbol':<8} {'Harga':>12} {'M15':<8} {'H1':<8} {'D1':<8} {'Stoch M5':>10} {'RSI M5':>7} {'Skor':>5}  {'Sinyal':<26} {'CRT':<12} {'SL / TP1 / TP2'}")
    print("-" * 142)
    for r in sorted(rows, key=lambda x: x["score"], reverse=True):
        d = SYMBOLS[r["symbol"]]["digits"]
        stoch = f"{r['stoch_k']:.1f}/{r['stoch_d']:.1f}"
        sltp = f"{fmt_price(r['sl'], d)} / {fmt_price(r['tp1'], d)} / {fmt_price(r['tp2'], d)}"
        print(f"{r['symbol']:<8} {fmt_price(r['price'], d):>12} {r['trend_m15']:<8} {r['trend_h1']:<8} {r['trend_d1']:<8} {stoch:>10} {r['rsi_m5']:>7.1f} {r['score']:>+5}  {r['emoji']} {r['signal']:<24} {_crt_short(r.get('crt')):<12} {sltp}")
    print("-" * 142)


def build_scalp_md(rows, sessions, now):
    """Markdown mode scalping -> output/scalp-latest.md (+ copy bertimestamp)."""
    lines = [f"# Scalp Mode — {now.strftime('%d %b %Y %H:%M WIB')}",
             "", f"Sesi aktif: **{', '.join(sessions)}** (WIB).",
             "Trigger: Stochastic (14,3,3) cross di M5. Filter: trend M15/H1/D1 searah "
             "(MA 9/21/50/200 + EMA 20/50). SL 0.5 ATR, TP1 1 ATR, TP2 2 ATR (ATR M15).",
             "S/R terdekat dari pivot M15. Bukan saran trading — M1/M5 itu noisy, "
             "tunggu trend searah & level S/R.",
             "",
             "| Symbol | Harga | M15 | H1 | D1 | Stoch M5 | RSI M5 | Skor | Sinyal | CRT | SL | TP1 | TP2 | S/R M15 terdekat |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: x["score"], reverse=True):
        d = SYMBOLS[r["symbol"]]["digits"]
        snr = r.get("snr_m15") or {}
        sup = snr.get("support") or []
        res = snr.get("resistance") or []
        sr = []
        if sup:
            sr.append(f"S {fmt_price(sup[0]['price'], d)} ({sup[0]['dist_pct']:+.1f}%)")
        if res:
            sr.append(f"R {fmt_price(res[0]['price'], d)} ({res[0]['dist_pct']:+.1f}%)")
        lines.append(f"| {r['symbol']} | {fmt_price(r['price'], d)} | {r['trend_m15']} | {r['trend_h1']} | {r['trend_d1']} | {r['stoch_k']}/{r['stoch_d']} | {r['rsi_m5']} | {r['score']:+d} | {r['emoji']} **{r['signal']}** | {_crt_short(r.get('crt'))} | {fmt_price(r['sl'], d)} | {fmt_price(r['tp1'], d)} | {fmt_price(r['tp2'], d)} | {' • '.join(sr) if sr else '-'} |")
    lines.append("")
    for r in sorted(rows, key=lambda x: x["score"], reverse=True):
        tfs = " ".join(f"{tf}:{v['trend']}(RSI {v['rsi14']}, Stoch {v['stoch_k']})"
                       for tf, v in r["tfs"].items())
        msnr = r.get("msnr_m15") or {}
        lines.append(f"- **{r['symbol']}** — {tfs} • ATR M15 {r['atr_m15']} ({r['atr_m15_pips']} pip) • MSNR M15 fresh: S {_msnr_str(msnr.get('support'))} / R {_msnr_str(msnr.get('resistance'))}")
    return "\n".join(lines)


def run_scalping(args, now):
    """Pipeline mode scalping: ambil M1/M5/M15/H1/D1, hitung sinyal, simpan + Telegram."""
    stamp = now.strftime("%Y-%m-%d_%H%M")
    sessions = current_sessions(now)
    rows = []
    for sym in args.symbols:
        sym = sym.upper()
        if sym not in SYMBOLS:
            print(f"⚠️  {sym} tidak dikenal, skip. Pilihan: {', '.join(SYMBOLS)}")
            continue
        cfg = SYMBOLS[sym]
        try:
            dfs = {
                "M1": fetch_data(sym, "1m", "1d", args.source),
                "M5": fetch_data(sym, "5m", "5d", args.source),
                "M15": fetch_data(sym, "15m", "5d", args.source),
                "H1": fetch_data(sym, "60m", "1mo", args.source),
                "D1": fetch_data(sym, "1d", "1y", args.source),
            }
        except Exception as e:
            print(f"⚠️  {sym}: gagal ambil data ({e})")
            continue
        if dfs.get("H1") is not None:
            dfs["H1"] = dfs["H1"].tail(150).reset_index(drop=True)
        tfs = {}
        for label in SCALP_TFS:
            row = scalp_tf(dfs.get(label))
            if row:
                tfs[label] = row
            else:
                print(f"⚠️  {sym} ({label}): data kurang / gagal")
        if not tfs.get("M5") or not tfs.get("M15"):
            print(f"⚠️  {sym}: data M5/M15 kurang, skip")
            continue
        # S/R M15 untuk eksekusi dekat level
        snr_m15 = None
        if dfs.get("M15") is not None and tfs["M15"].get("atr"):
            snr_m15 = find_snr(dfs["M15"], tfs["M15"]["price"],
                               tfs["M15"]["atr"], cfg["digits"])
        # CRT (M15 + H1) & level MSNR M15
        crt_scalp = {}
        if dfs.get("M15") is not None:
            crt_scalp["M15"] = latest_crt(detect_crt(dfs["M15"], tfs["M15"]["atr"], cfg["digits"]))
        if dfs.get("H1") is not None and tfs.get("H1"):
            crt_scalp["H1"] = latest_crt(detect_crt(dfs["H1"], tfs["H1"]["atr"], cfg["digits"]))
        msnr_m15 = None
        if dfs.get("M15") is not None:
            lvls_m15 = find_msnr_levels(dfs["M15"], tfs["M15"]["atr"], cfg["digits"])
            msnr_m15 = nearest_msnr(lvls_m15, tfs["M15"]["price"], tfs["M15"]["atr"], cfg["digits"])
        row = analyse_scalp(sym, cfg, tfs, snr_m15)
        if row:
            row["crt"] = crt_scalp
            row["msnr_m15"] = msnr_m15 or {}
            rows.append(row)
    if not rows:
        print("Tidak ada data scalping. Cek internet / sumber data.")
        sys.exit(1)
    if args.out in ("all", "console"):
        print_scalp(rows, sessions, now)
    if args.out in ("all", "md"):
        md = build_scalp_md(rows, sessions, now)
        (OUT / f"scalp_{stamp}.md").write_text(md)
        (OUT / "scalp-latest.md").write_text(md)
        print(f"\n💾 Tersimpan di {OUT}/  (scalp_{stamp}.md + scalp-latest.md)")
    if args.out in ("all", "json"):
        payload = {"generated_wib": now.isoformat(), "mode": "scalping",
                   "sessions": sessions, "source": source_label(),
                   "data": rows}
        (OUT / f"scalp_{stamp}.json").write_text(json.dumps(payload, indent=2))
        (OUT / "scalp-latest.json").write_text(json.dumps(payload, indent=2))
    if args.telegram:
        try:
            from telegram_notify import build_scalp_message, send_text
            msg = build_scalp_message(rows, sessions, now.strftime('%d %b %Y %H:%M WIB'),
                                      source=source_label())
            print("\n📩 Mengirim ke Telegram...")
            send_text(msg)
        except Exception as e:
            print(f"⚠️  Telegram gagal: {e}", file=sys.stderr)


COMPARE_SYMBOLS = ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "DXY", "BTCUSD"]

def _cmp_diff(a, b):
    """Selisih % a vs b, atau '-'."""
    if a is None or b is None or b == 0:
        return "-"
    return f"{(a / b - 1) * 100:+.2f}%"

def run_compare(args, now):
    """Bandingkan harga + analisa Daily dari Yahoo vs Biquote vs XAUS.

    XAUS cuma punya emas (history Daily) + spot perak/BTC — selain itu "-".
    Simpan output/compare_{stamp}.md + compare-latest.md (+ .json).
    """
    stamp = now.strftime("%Y-%m-%d_%H%M")
    syms = args.symbols or COMPARE_SYMBOLS
    try:
        spot = fetch_xaus_spot()
    except Exception as e:
        print(f"⚠️  XAUS spot gagal ({e})")
        spot = None
    rows = []
    for sym in syms:
        sym = sym.upper()
        if sym not in SYMBOLS:
            print(f"⚠️  {sym} tidak dikenal, skip. Pilihan: {', '.join(SYMBOLS)}")
            continue
        cfg = SYMBOLS[sym]
        _spot = (spot or {}).get(sym)
        rec = {"symbol": sym,
               "spot_xaus": round(_spot, cfg["digits"]) if _spot is not None else None}
        for src in ("yahoo", "biquote", "xaus"):
            try:
                if src == "yahoo":
                    df = fetch_yahoo(cfg["yahoo"], "1d", "5y")
                elif src == "biquote":
                    df = fetch_biquote(sym, "1d", "5y")
                else:
                    df = fetch_xaus(sym, "1d", "5y")
            except Exception as e:
                print(f"⚠️  {sym} ({src}): gagal ({e})")
                df = None
            rec[src] = analyse(sym, cfg, df) if df is not None and len(df) >= 60 else None
        rows.append(rec)
    if not rows:
        print("Tidak ada data perbandingan.")
        sys.exit(1)
    # --- tabel harga ---
    print(f"\n📊 Perbandingan sumber — {now.strftime('%d %b %Y %H:%M WIB')} (Daily)")
    print(f"{'Symbol':8} {'Yahoo':>14} {'Biquote':>14} {'XAUS':>14} {'Bq-Yh':>8} {'XAUS-Yh':>8}")
    md = [f"# Perbandingan Sumber Data — {now.strftime('%d %b %Y %H:%M WIB')}",
          "",
          "Daily (analisa: EMA/RSI/ATR/skor) + harga spot live. "
          "XAUS cuma emas (history Daily) + spot perak/BTC; forex/DXY tidak ada di XAUS.",
          "",
          "| Symbol | Yahoo | Biquote | XAUS | Biquote vs Yahoo | XAUS vs Yahoo |",
          "|---|---|---|---|---|---|"]
    for rec in rows:
        sym = rec["symbol"]
        d = SYMBOLS[sym]["digits"]
        yh, bq, xa = rec["yahoo"], rec["biquote"], rec["xaus"]
        yh_p = yh["price"] if yh else None
        bq_p = bq["price"] if bq else None
        # Harga XAUS: dari analisa Daily (forming bar = spot) kalau ada,
        # kalau tidak dari spot langsung.
        xa_p = xa["price"] if xa else rec.get("spot_xaus")
        f = lambda p: fmt_price(p, d) if p is not None else "-"
        print(f"{sym:8} {f(yh_p):>14} {f(bq_p):>14} {f(xa_p):>14} "
              f"{_cmp_diff(bq_p, yh_p):>8} {_cmp_diff(xa_p, yh_p):>8}")
        md.append(f"| {sym} | {f(yh_p)} | {f(bq_p)} | {f(xa_p)} | "
                  f"{_cmp_diff(bq_p, yh_p)} | {_cmp_diff(xa_p, yh_p)} |")
    # --- tabel analisa ---
    print(f"\n{'Symbol':8} {'Yahoo':>34} {'Biquote':>34} {'XAUS':>34}")
    md += ["",
           "| Symbol | Yahoo (RSI, skor, sinyal) | Biquote (RSI, skor, sinyal) | XAUS (RSI, skor, sinyal) |",
           "|---|---|---|---|"]
    for rec in rows:
        sym = rec["symbol"]
        cells = []
        for src in ("yahoo", "biquote", "xaus"):
            r = rec[src]
            cells.append(f"RSI {r['rsi14']} ({r['rsi_tag']}), {r['score']:+d}, {r['signal']}" if r else "-")
        print(f"{sym:8} {cells[0]:>34} {cells[1]:>34} {cells[2]:>34}")
        md.append(f"| {sym} | {cells[0]} | {cells[1]} | {cells[2]} |")
    md += ["",
           "Catatan: Biquote = spot MT5, Yahoo = futures (GC=F/SI=F) — emas Biquote "
           "biasanya ~$2-10 di bawah Yahoo. XAUS = spot emas + spot perak/BTC.",
           "Selisih kecil (<0.5%) di forex/DXY = wajar (beda feed & waktu ambil, beda hitungan detik)."]
    if args.out in ("all", "md"):
        (OUT / f"compare_{stamp}.md").write_text("\n".join(md))
        (OUT / "compare-latest.md").write_text("\n".join(md))
    if args.out in ("all", "json"):
        payload = {"generated_wib": now.isoformat(), "mode": "compare", "data": rows}
        (OUT / f"compare_{stamp}.json").write_text(json.dumps(payload, indent=2))
        (OUT / "compare-latest.json").write_text(json.dumps(payload, indent=2))
    if args.out in ("all", "md", "json"):
        print(f"\n💾 Tersimpan di {OUT}/  (compare_{stamp}.* + compare-latest.*)")

    # --- Telegram (opsional, dipakai bot /banding) ---
    if args.telegram:
        try:
            from telegram_notify import build_compare_message, send_text, send_file
            msg = build_compare_message(rows, now.strftime('%d %b %Y %H:%M WIB'))
            print("\n📩 Mengirim ke Telegram...")
            send_text(msg)
            if args.out in ("all", "md"):
                send_file(OUT / "compare-latest.md",
                          caption="Tabel perbandingan lengkap (Yahoo vs Biquote vs XAUS)")
        except Exception as e:
            print(f"⚠️  Telegram gagal: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["topdown", "scalping"], default="topdown",
                    help="topdown = W/D/H4/H1/M15 + SnR (default); scalping = M1/M5/M15 + H1/D1, Stochastic + MA")
    ap.add_argument("--symbols", nargs="+", default=None,
                    help="contoh: --symbols XAUUSD XAGUSD EURUSD (default topdown: semua 14; scalping: XAU XAG EUR GBP JPY)")
    ap.add_argument("--timeframe", choices=["1d", "1h", "both", "topdown"], default="topdown")
    ap.add_argument("--out", choices=["all", "md", "csv", "json", "console"], default="all")
    ap.add_argument("--alert", action="store_true", help="hanya tampilkan sinyal kuat / RSI ekstrem")
    ap.add_argument("--telegram", action="store_true",
                    help="kirim ringkasan ke Telegram (env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")
    ap.add_argument("--telegram-file", action="store_true",
                    help="ikut kirim output/latest.md sebagai file Telegram")
    ap.add_argument("--source", choices=["auto", "yahoo", "biquote", "xaus"],
                    default=os.environ.get("SCREENER_SOURCE", "auto"),
                    help="sumber data: auto = Yahoo dulu, gagal -> Biquote "
                         "(default); yahoo/biquote/xaus = paksa satu sumber "
                         "(xaus cuma emas, Daily)")
    ap.add_argument("--compare", action="store_true",
                    help="bandingkan Yahoo vs Biquote vs XAUS (Daily + spot live), "
                         "bukan screener biasa")
    args = ap.parse_args()

    if pd is None:
        print("Butuh pandas + numpy + requests. Jalankan: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(WIB)
    if args.symbols is None:
        if args.compare:
            args.symbols = list(COMPARE_SYMBOLS)
        elif args.mode == "topdown":
            args.symbols = list(SYMBOLS.keys())
        else:
            args.symbols = list(SCALP_SYMBOLS)
    if args.compare:
        run_compare(args, now)
        return
    if args.mode == "scalping":
        run_scalping(args, now)
        return
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
                dfs["Weekly"] = fetch_data(sym, "1wk", "5y", args.source)
            if "Daily" in wanted:
                # 5 tahun: SnR butuh histori panjang (harga sedang di low 1 tahun,
                # support terdekat bisa berasal dari struktur lama).
                dfs["Daily"] = fetch_data(sym, "1d", "5y", args.source)
            if "H4" in wanted or "H1" in wanted:
                df60 = fetch_data(sym, "60m", "1mo", args.source)
                if df60 is not None:
                    if "H4" in wanted:
                        dfs["H4"] = resample_4h(df60)
                        if (dfs["H4"] is None or len(dfs["H4"]) < 60) and args.source in ("auto", "biquote"):
                            # Biquote 1h cuma ~7 hari -> H4 resample < 60 bar.
                            # Pakai interval 4h native Biquote (Yahoo tidak punya 4h).
                            h4_native = fetch_biquote(sym, "4h", "1mo")
                            if h4_native is not None and len(h4_native) >= 60:
                                dfs["H4"] = h4_native
                                SOURCES_USED.add("biquote")
                    if "H1" in wanted:
                        dfs["H1"] = df60.tail(150).reset_index(drop=True)
            if "M15" in wanted:
                dfs["M15"] = fetch_data(sym, "15m", "5d", args.source)
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
        # --- MSNR levels (D1 + H4) & CRT (H4 + D1) ---
        msnr = {"support": [], "resistance": [], "fresh_total": 0}
        crt = {}
        if daily_row and dfs.get("Daily") is not None:
            lvls_d = find_msnr_levels(dfs["Daily"], daily_row["atr"], cfg["digits"])
            near_d = nearest_msnr(lvls_d, daily_row["price"], daily_row["atr"], cfg["digits"])
            msnr["support"] = near_d["support"]
            msnr["resistance"] = near_d["resistance"]
            msnr["fresh_total"] = sum(1 for lv in lvls_d if lv["fresh"])
            crt["Daily"] = latest_crt(detect_crt(dfs["Daily"], daily_row["atr"], cfg["digits"]))
            if dfs.get("H4") is not None and rows_by_tf.get("H4"):
                lvls_h4 = find_msnr_levels(dfs["H4"], rows_by_tf["H4"]["atr"], cfg["digits"])
                near_h4 = nearest_msnr(lvls_h4, rows_by_tf["H4"]["price"],
                                       rows_by_tf["H4"]["atr"], cfg["digits"])
                msnr["fresh_total"] += sum(1 for lv in lvls_h4 if lv["fresh"])
                # Level H4 lebih dekat untuk eksekusi: tampilkan di depan
                # kalau level Daily terlalu jauh (>3%) atau tidak ada.
                for side in ("support", "resistance"):
                    cur = msnr.get(side) or []
                    if (not cur or abs(cur[0]["dist_pct"]) > 3) and near_h4.get(side):
                        lvl = dict(near_h4[side][0])
                        lvl["tf"] = "H4"
                        msnr[side] = [lvl] + cur[:1]
                crt["H4"] = latest_crt(detect_crt(dfs["H4"], rows_by_tf["H4"]["atr"], cfg["digits"]))
        topdown[sym]["msnr"] = msnr
        topdown[sym]["crt"] = crt

    if not all_rows:
        print("Tidak ada data. Cek internet / sumber data.")
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
        print_msnr_crt(topdown, now)

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
            payload = {"generated_wib": now.isoformat(), "source": source_label(),
                       "data": all_rows, "topdown": topdown}
            (OUT / f"screener_{stamp}.json").write_text(json.dumps(payload, indent=2))
            (OUT / "latest.json").write_text(json.dumps(payload, indent=2))
        if args.out in ("all", "md"):
            src_note = ("Yahoo Finance (GC=F, SI=F, EURUSD=X, dst)" if SOURCES_USED == {"yahoo"}
                        else source_label())
            lines = [f"# Forex Screener — {now.strftime('%d %b %Y %H:%M WIB')}",
                     "", f"Sumber: {src_note}. Bukan saran trading.",
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
            lines.append("## MSNR (level fresh, D1+H4)")
            lines.append("Level dari close candle (A = resistance, V = support, Gap, OCL). "
                         "Fresh = belum pernah disentuh wick sejak terbentuk; "
                         "RBS/SBR = level yang sudah ditembus close lalu berbalik peran.")
            lines.append("")
            lines.append("| Symbol | Support fresh terdekat | Resistance fresh terdekat | Level fresh (D1+H4) |")
            lines.append("|---|---|---|---|")
            for sym, td in sorted(topdown.items(), key=lambda kv: kv[1]["weighted_score"], reverse=True):
                msnr = td.get("msnr") or {}
                lines.append(f"| {sym} | {_msnr_str(msnr.get('support'))} | {_msnr_str(msnr.get('resistance'))} | {msnr.get('fresh_total', 0)} |")
            lines.append("")
            lines.append("## CRT (H4/D1)")
            lines.append("Sweep high/low candle sebelumnya lalu close balik ke dalam range = "
                         "target sisi seberang. Hanya candle yang sudah tutup yang dinilai; "
                         "sweep yang close-nya bertahan di luar range = breakout, bukan CRT.")
            lines.append("")
            lines.append("| Symbol | CRT terbaru |")
            lines.append("|---|---|")
            for sym, td in sorted(topdown.items(), key=lambda kv: kv[1]["weighted_score"], reverse=True):
                lines.append(f"| {sym} | {_crt_str(td.get('crt'))} |")
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
            msg = build_message(all_rows, now.strftime('%d %b %Y %H:%M WIB'), topdown,
                                source=source_label())
            print("\n📩 Mengirim ke Telegram...")
            send_text(msg)
            if args.telegram_file:
                send_file(OUT / "latest.md", caption="Hasil screener lengkap")
        except Exception as e:
            print(f"⚠️  Telegram gagal: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
