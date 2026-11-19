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
