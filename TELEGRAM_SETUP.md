# Telegram Setup — 5 menit

Tujuannya: bot Telegram kirim update screener ke kamu, jadi nggak perlu buka Muse.

## 1. Bikin bot (2 menit)

1. Buka Telegram, cari **@BotFather**, tap `/start`
2. Kirim `/newbot`
3. Kasih nama, misal `Pip Forex Screener`
4. Kasih username, misal `pip_forex_bot` (harus unik, berakhiran `bot`)
5. BotFather balas dengan token, bentuknya:
   `123456789:AAEhBOweik6ad9r_QXMENQjcrGbqCr6yY54`
   👉 Itu `TELEGRAM_BOT_TOKEN`. Simpan baik-baik, **jangan di-share / di-commit**.

## 2. Dapatin Chat ID kamu (1 menit)

1. Cari **@userinfobot** di Telegram, tap `/start`
2. Dia balas dengan `Id: 123456789` — itu `TELEGRAM_CHAT_ID` kamu.

Alternatif: buka bot kamu, kirim `/start`, lalu buka di browser:
`https://api.telegram.org/bot<TOKEN>/getUpdates`
cari `"chat":{"id":123456789}`.

Mau kirim ke **grup**? Tambahin bot ke grup, kirim pesan di grup, lalu cek
`getUpdates` — id grup biasanya negatif (`-100...`).

## 3. Test lokal (1 menit)

```bash
cd forex-screener
export TELEGRAM_BOT_TOKEN="token-kamu"
export TELEGRAM_CHAT_ID="id-kamu"

python3 telegram_notify.py --test
# Harusnya muncul di Telegram: "✅ Test dari Pip Forex Screener..."

python3 screener.py --symbols XAUUSD XAGUSD --telegram
# Kirim ringkasan screener beneran ke Telegram
```

## 4. Pasang di Railway (biar jalan 24 jam)

Isi di Railway Project → Variables (bukan di file!):
- `TELEGRAM_BOT_TOKEN` = token dari BotFather
- `TELEGRAM_CHAT_ID` = id kamu
- `TELEGRAM_TIMES` = `07:00,19:30` (jam WIB kirim ringkasan)

Lihat `DEPLOY.md` untuk langkah Railway lengkap.

## Aman?

- Token = password bot kamu. Siapa pun yang pegang token bisa kirim pesan
  atas nama bot. Jangan taruh di GitHub, screenshot, atau chat publik.
- `.env` sudah masuk `.gitignore`, jadi nggak akan ke-push kalau kamu
  pakai `deploy_github.sh`.
- Kalau token bocor: ke @BotFather → `/revoke` → ganti token di Railway.

## Cek kapan saja (on-demand)

Selain jadwal otomatis 07:00 & 19:30 WIB, bot juga menjawab perintah kapan saja.
Caranya: buka chat bot di Telegram, kirim salah satu perintah ini:

| Perintah  | Artinya |
|-----------|---------|
| `/cek`    | Screener lengkap (semua simbol, Daily) |
| `/xau`    | Emas & perak saja (XAUUSD, XAGUSD) |
| `/majors` | EURUSD, GBPUSD, USDJPY, DXY |
| `/help`   | Daftar perintah |

Bot hanya menjawab chat yang id-nya sama dengan `TELEGRAM_CHAT_ID` — orang lain
yang chat bot ini akan diabaikan. Ada jeda 60 detik antar pengecekan (cooldown).

Teknis: `bot.py` memakai long polling `getUpdates`, jalan bareng `scheduler.py`
lewat `run_services.py` (Procfile / `railway.json` / `Dockerfile` sudah diarahkan
ke sana). Kalau Railway sudah deploy dari repo ini, redeploy otomatis saat
push — tidak perlu ubah apa-apa di dashboard selain memastikan Variables
(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) sudah terisi.

## Teknik di dalam pesan: Top-Down + SnR

Pesan Telegram sekarang diawali blok **📐 Top-Down & SnR**:

```
🥇 XAUUSD 🔴 Bearish (5/5) • W▼ D▼ H4▼ H1▼ M15▼
   S 3,353.4 (-8.8%, 1x) / 3,305.87 (-10.0%, 3x) • R 3,894.0 (+6.0%, 1x H4) — mid-range
```

- `W▼ D▼ H4▼ H1▼ M15▼` = arah tiap timeframe (▲ bullish, ▼ bearish, • netral).
- `(5/5)` = berapa TF yang selaras searah bias.
- `S` / `R` = 2 level terdekat, jarak dalam %, dan jumlah pengujian level
  (`3x` = level itu sudah 3x diuji — makin sering diuji, makin kuat).
  Tanda `H4` = level dari timeframe H4 (dipakai kalau level Daily terlalu jauh).
- Status `di Support` / `di Resistance` = harga sedang menempel level
  (≤0.5 ATR) — zona pantau bounce atau breakout.

Perintah baru di bot: `/snr` — S/R 6 simbol utama (XAU, XAG, EURUSD,
GBPUSD, USDJPY, DXY). `/cek` sekarang mengirim Top-Down lengkap.
