# Pip Forex Screener — XAUUSD, XAGUSD & Majors

Screener multi-symbol tanpa API key, sumber Yahoo Finance (gratis).

## Yang di-scan (14 symbol)

| Symbol | Yahoo | Arti |
|---|---|---|
| XAUUSD | GC=F | Gold |
| XAGUSD | SI=F | Silver |
| EURUSD, GBPUSD, AUDUSD, NZDUSD | ...=X | Majors vs USD |
| USDJPY, USDCAD, USDCHF | ...=X | USD vs lainnya |
| EURJPY, GBPJPY, EURGBP | ...=X | Crosses |
| DXY | DX-Y.NYB | Kekuatan USD (filter) |
| BTCUSD | BTC-USD | Crypto (pembanding) |

## Indikator

Harga, Chg% harian, Chg 5d/20d, EMA20/50/200, RSI14, ATR14 (harga + pips),
High/Low 20d + posisi harga di range itu, Trend, Skor -100..+100, Sinyal
(STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL).

Skor: +25 harga>EMA50, +15 harga>EMA20, +10 EMA20>EMA50, +10 harga>EMA200,
±15 dari RSI, ±10 momentum 5d, ±10 posisi range 20d.

## Pakai

```bash
cd ~/workspace/forex-screener
pip install -r requirements.txt   # pandas, numpy, requests (biasanya sudah ada)
python3 screener.py                          # semua symbol, Daily + H1
python3 screener.py --symbols XAUUSD XAGUSD EURUSD
python3 screener.py --timeframe 1d
python3 screener.py --alert                  # hanya sinyal kuat / RSI ekstrem
./run_screener.sh                            # wrapper + log
```

Output di `output/`: `screener_YYYY-MM-DD_HHMM-daily.csv/.json/.md` + `latest.*`

## Scheduler / Cron

**Opsi A — cron (disarankan di VPS/server):**
```bash
./install_cron.sh
crontab -l   # cek
```
Jadwal: tiap 30 mnt Sen-Jum 07:00-23:00 WIB, ringkasan 07:00 & 19:30 WIB.
Log: `logs/run.log`, `logs/cron.log`.

**Opsi B — loop Python (tanpa cron, untuk laptop/VM yang hidup terus):**
```bash
nohup python3 scheduler.py >> logs/scheduler.log 2>&1 &
tail -f logs/scheduler.log
```

**Opsi C — cron di Muse (minta Pip):** Pip bisa bikinin cron job di sini yang
jalanin screener tiap pagi/sore dan kirim hasilnya ke chat.

## Telegram

```bash
export TELEGRAM_BOT_TOKEN="..." TELEGRAM_CHAT_ID="..."
python3 telegram_notify.py --test
python3 screener.py --telegram            # kirim ringkasan ke Telegram
python3 screener.py --telegram --telegram-file  # + kirim latest.md
```
Lihat `TELEGRAM_SETUP.md` (cara bikin bot & dapat Chat ID).

## Deploy: GitHub → Railway

Biar jalan 24 jam dan notif masuk Telegram tanpa buka Muse.
Lihat `DEPLOY.md` — ringkasnya:
1. `./deploy_github.sh https://github.com/pgenjeh/forex-screener.git`
2. Railway → New Project → Deploy from GitHub repo → service jadi **Worker**
3. Isi Variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_TIMES=07:00,19:30`, `TZ=Asia/Jakarta`

## Catatan

- Harga Yahoo (GC=F/SI=F) adalah futures proxy untuk spot XAU/XAG — untuk
  eksekusi, tetap cek harga broker kamu (spread bisa beda beberapa dolar).
- Bukan saran trading. Screener hanya filter: konfirmasi dengan struktur
  market, S/R, dan news (DXY, Fed, CPI) sebelum entry.
- Yahoo kadang rate-limit kalau dipanggil terlalu sering — interval 30 menit aman.
