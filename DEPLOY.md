# Deploy: GitHub → Railway + Telegram

Arsitektur: repo GitHub → Railway Worker (jalan 24 jam) → Telegram.
`scheduler.py` jalan terus, scan tiap 30 menit (Sen–Jum 07:00–23:00 WIB),
kirim ringkasan Telegram jam 07:00 & 19:30 WIB (atur via `TELEGRAM_TIMES`).

Biaya: Railway punya free trial / Hobby ~$5/bulan. Worker kecil ini
nggak butuh web server, jadi pemakaian CPU-nya kecil.

## Langkah 1 — GitHub (3 menit)

1. Buka github.com/new → buat repo kosong, misal `forex-screener`
   (jangan centang "Add README" — biar nggak konflik).
2. Di terminal:
   ```bash
   cd forex-screener
   ./deploy_github.sh https://github.com/pgenjeh/forex-screener.git
   ```
   Ganti `badasht` dengan username GitHub kamu kalau beda.
3. Cek di GitHub: file harus ada, dan **pastikan tidak ada `.env`** di repo.

## Langkah 2 — Railway (5 menit)

1. Buka railway.app → **New Project → Deploy from GitHub repo**
   → pilih repo `forex-screener`.
2. Railway otomatis baca `Dockerfile` + `railway.json`.
3. **Tidak perlu ubah tipe service / pasang domain:**
   Service ini cuma jalanin `python run_services.py` (dari `railway.json`)
   — dia proses yang jalan terus, bukan website. Jadi **jangan** generate
   public domain dan **jangan** isi healthcheck path: worker ini tidak
   membuka port sama sekali, dan health check ke port yang tidak ada akan
   membuat deploy kelihatan gagal padahal worker-nya sehat.
   Kalau Railway sudah pakai `railway.json`, start command-nya
   sudah `python scheduler.py`.
4. Isi Variables (Project → Variables → New Variable):
   | Nama | Isi |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | token dari @BotFather (lihat TELEGRAM_SETUP.md) |
   | `TELEGRAM_CHAT_ID` | id kamu dari @userinfobot |
   | `TELEGRAM_TIMES` | `07:00,19:30` |
   | `TZ` | `Asia/Jakarta` |
5. Deploy → cek Logs: harus muncul
   `Pip scheduler mulai. Interval 30 menit...`
6. Test: tunggu jam kirim berikutnya, atau test manual dari lokal:
   `python3 telegram_notify.py --test`

## Langkah 3 — Alternatif: Railway Cron Job (tanpa worker 24 jam)

Kalau mau lebih hemat (cuma jalan 2x sehari, bukan 24 jam):
1. Di Railway, tambah service **Cron Job** dari repo yang sama.
2. Command: `python screener.py --telegram --timeframe 1d`
3. Schedule: `0 0,12 * * *` — itu **00:00 & 12:00 UTC = 07:00 & 19:00 WIB**.
   (Railway cron pakai UTC, jadi kurangi 7 jam dari jam WIB.)
4. Isi Variables Telegram yang sama.

Kekurangan: cron job cuma kirim di jam itu, nggak ada scan 30 menitan.

## Troubleshooting

| Gejala | Penyebab / solusi |
|---|---|
| Log: `Telegram skip: token/chat_id belum di-set` | Variables di Railway belum diisi / salah nama. Cek ejaan `TELEGRAM_BOT_TOKEN`. |
| Log: `Telegram gagal (401)` | Token salah / sudah di-revoke. Buat ulang di @BotFather. |
| Log: `Telegram gagal (400) chat not found` | Chat ID salah, atau kamu belum `/start` bot-nya. Buka bot, tap Start. |
| Railway: service CrashLoop / "no port" | Bukan soal port — worker ini memang tidak buka port. Cek Logs: biasanya Variables belum diisi (token) atau build gagal. Jangan pasang domain/healthcheck. |
| Yahoo gagal / data kosong | Yahoo kadang rate-limit. Tunggu 10 menit, jalan lagi. Interval 30 menit aman. |
| Pesan Telegram nggak masuk jam 07:00 | Cek `TELEGRAM_TIMES` dan TZ. Ingat: scheduler pakai WIB; Railway Cron pakai UTC. |

## Update kode nanti

```bash
# edit file lokal, lalu:
git add . && git commit -m "ubah ..." && git push
# Railway auto-redeploy dari GitHub (kalau diaktifkan).
```
