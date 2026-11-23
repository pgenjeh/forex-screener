# Pip Forex Screener — XAUUSD, XAGUSD & Majors

Screener multi-symbol tanpa API key. Sumber data: Biquote (feed MT5 live —
gratis, tanpa key, **utama**) + XAUS (xaus.com, gratis tanpa key — emas
saja, **kedua**) + Yahoo Finance (public, gratis — **terakhir**).

## Sumber data (`--source`)

| Sumber | Cakupan | Catatan |
|---|---|---|
| Biquote (utama) | Semua 14 simbol incl. DXY, 2.081 simbol total | 15.000 req/menit/IP, tanpa key; Daily ~19 bln, 1h ~7 hari, 4h ~41 hari; Weekly di-resample dari Daily; H4 pakai interval 4h native; tick live `GET /api/{symbol}` |
| XAUS (kedua) | XAUUSD Daily 5 thn + spot XAU/XAG/BTC | 60 req/menit, tanpa key; history tanpa kolom open (disintesis dari close kemarin); forex/DXY tidak ada; cuma kepake kalau Biquote gagal (emas Daily) |
| Yahoo Finance (terakhir) | Semua 14 simbol, Daily 5 thn | Dipakai terakhir kalau Biquote + XAUS gagal; kadang rate-limit; M1 emas/perak kadang kosong |

Default `auto`: Biquote dulu, gagal/terlalu sedikit -> XAUS (emas Daily saja) -> Yahoo. Yang dipakai
tercatat di output (`source` di JSON, baris "Sumber:" di MD/Telegram).

```bash
python3 screener.py --source auto      # default
python3 screener.py --source biquote   # paksa Biquote (mis. Yahoo rate-limit)
python3 screener.py --source yahoo     # paksa Yahoo
python3 screener.py --source xaus --symbols XAUUSD   # paksa XAUS (emas, Daily saja)
SCREENER_SOURCE=biquote python3 screener.py   # sama, via env
```

## Bandingkan sumber (`--compare`)

Satu command buat bandingin ketiganya sekaligus — harga + analisa Daily
(RSI/skor/sinyal) Yahoo vs Biquote vs XAUS, plus selisih %-nya:

```bash
python3 screener.py --compare                          # 7 simbol utama
python3 screener.py --compare --symbols XAUUSD XAGUSD  # simbol tertentu
```

Hasil: `output/compare-latest.md` (+ `.json`). XAUS di tabel cuma muncul
buat XAUUSD (Daily lengkap), XAGUSD/BTCUSD (harga spot saja), sisanya "-".

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
2. Railway → New Project → Deploy from GitHub repo → jalanin `run_services.py` (bukan website: jangan pasang domain/healthcheck)
3. Isi Variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_TIMES=07:00,19:30`, `TZ=Asia/Jakarta`

## Catatan

- Harga Yahoo (GC=F/SI=F) adalah futures proxy untuk spot XAU/XAG — untuk
  eksekusi, tetap cek harga broker kamu (spread bisa beda beberapa dolar).
  Harga Biquote adalah spot MT5 (emas ~$2-10 di bawah futures Yahoo).
- Bukan saran trading. Screener hanya filter: konfirmasi dengan struktur
  market, S/R, dan news (DXY, Fed, CPI) sebelum entry.
- Yahoo kadang rate-limit kalau dipanggil terlalu sering — interval 30 menit
  aman. Kalau Yahoo gagal, screener otomatis pindah ke Biquote (`--source auto`).
  Paksa sumber tertentu dengan `--source yahoo|biquote`.

## Cek kapan saja lewat Telegram

Selain update otomatis 07:00 & 19:30 WIB, chat bot-nya kapan saja:

- `/cek` — screener lengkap (semua simbol)
- `/xau` — emas & perak saja
- `/majors` — EURUSD, GBPUSD, USDJPY, DXY
- `/snr` — S/R 6 simbol utama
- `/scalp` — mode scalping
- `/banding` — bandingkan Yahoo vs Biquote vs XAUS (Daily + spot live, + file tabel lengkap)
- `/help` — daftar perintah

Bot hanya menjawab chat id di `TELEGRAM_CHAT_ID`. Detail di `TELEGRAM_SETUP.md`.

## Teknik: Top-Down + Support & Resistance

Sesuai gaya Abyan — screener ini bukan cuma RSI/EMA per timeframe:

- **Top-Down (Multi-Timeframe):** bias dibaca dari Weekly → Daily → H4 →
  H1 → M15. TF besar menentukan arah, TF kecil menentukan timing. Skor
  tertimbang: W 30%, D 30%, H4 20%, H1 10%, M15 10%. "Selaras 5/5" artinya
  semua TF searah.
- **Support & Resistance:** level S/R dari swing high/low (pivot) Daily
  (histori 5 tahun) yang di-cluster jadi zona, lengkap dengan jumlah
  pengujian (touches) dan jarak harga dalam % dan ATR. Kalau level Daily
  terlalu jauh, level H4 terdekat ditampilkan sebagai pelengkap (tanda H4).
- **Status posisi harga:** `di Support` / `di Resistance` (jarak ≤0.5 ATR),
  `mid-range`, atau `tanpa Support/Resistance dekat`.
- **Eksekusi:** searah bias Top-Down, tunggu konfirmasi di H1/M15 dekat
  level S/R sebelum masuk. Bukan saran trading.

Hasilnya ada di tabel `Top-Down & SnR` (console, `latest.md`, JSON
`topdown`) dan di pesan Telegram. Di bot Telegram: `/snr` untuk S/R
6 simbol utama, `/cek` untuk Top-Down lengkap.

## TradingView — indikator Pine Script

Ada versi indikatornya juga buat chart TradingView: `tradingview/pip-topdown-snr.pine`
(Pine Script v6). Logikanya sama: tabel Top-Down 5 TF + garis S/R Daily + alert
"di Support / di Resistance / bias berubah". Cara pasang: Pine Editor → paste →
Add to chart. Pakai chart M15 supaya semua 5 TF kebaca. Detail di
`tradingview/README.md`.

## Mode Scalping (`--mode scalping` / `/scalp` di Telegram)

Setup MT5 Abyan: trigger **Stochastic (14,3,3) cross di M5**, filter trend
**M15/H1/D1 searah** (MA 9/21/50/200 + EMA 20/50), konfirmasi **RSI14 +
Stochastic M1**. S/R dari pivot M15. **SL 0.5 ATR / TP1 1 ATR / TP2 2 ATR**
(ATR M15). Sesi market yang sedang buka ditampilkan (Sydney/Tokyo/London/
New York, jam WIB).

```bash
python3 screener.py --mode scalping                  # XAUUSD XAGUSD EURUSD GBPUSD USDJPY
python3 screener.py --mode scalping --symbols XAUUSD # emas saja
```

Sinyal: `LONG/SHORT SCALP` (skor ≥ ±50 + cross M5 searah + M1 searah),
`SIAP LONG/SHORT` (skor ≥ ±40 tapi cross belum terjadi — tunggu),
`WAIT` (tidak selaras). Output: `output/scalp-latest.md` (+ `.json`).

Mode ini **on-demand saja** — sinyal M1/M5 cepat basi, jadi tidak
dijadwalkan seperti Top-Down. Di Telegram tinggal kirim `/scalp` ke bot.

## MSNR + CRT

**MSNR (Malaysian SNR)** — level dari close/open candle, bukan wick:
A-level (resistance), V-level (support), Gap level, OCL (run ≥ 3 candle
sewarna). Hanya **level fresh** yang ditampilkan (belum pernah disentuh
wick sejak terbentuk); level yang ditembus close berbalik peran (RBS/SBR)
dan jadi fresh lagi. Dihitung di D1 + H4 (Top-Down) dan M15 (scalping).

**CRT (Candle Range Theory, ICT)** — candle C2 menyapu high/low candle
C1 lalu close balik ke dalam range C1 → target sisi seberang, invalidasi
di extreme sweep-nya. Hanya candle yang sudah tutup yang dinilai; sweep
yang close-nya bertahan di luar range = breakout, bukan CRT. Dihitung di
H4 + D1 (Top-Down) dan M15 + H1 (scalping). Output: arah, berapa bar lalu,
status (`active` / `target hit` / `invalidated`), target, invalidasi.

Aturan pakai: **CRT searah trend HTF di level MSNR fresh = konfluensi
terkuat.** CRT lawan trend itu mean-reversion — hati-hati, apalagi di hari
trend kuat. Backtest mekanis keduanya belum menunjukkan edge setelah
biaya; edge-nya (kalau ada) ada di filternya: level fresh, searah HTF,
sesi London/New York.
