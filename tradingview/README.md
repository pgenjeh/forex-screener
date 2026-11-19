# Pip Top-Down + SnR — Indikator TradingView

Indikator Pine Script v6 dengan logika yang **sama persis** dengan bot Telegram
Pip Forex Screener di repo ini, tapi tampil di chart TradingView.

## Yang ditampilkan

- **Tabel Top-Down (kanan atas):** skor + RSI tiap timeframe (Weekly, Daily,
  H4, H1, M15), bias gabungan tertimbang (W 30%, D 30%, H4 20%, H1 10%,
  M15 10%), dan hitungan "Selaras 5/5".
- **Garis S/R di chart:** 2 Support + 2 Resistance terdekat dari pivot Daily
  (histori yang dimuat chart), lengkap dengan label harga, jarak %, dan jumlah
  pengujian level (`3x`).
- **Status:** `di Support` / `di Resistance` (jarak ≤0.5 ATR) / `mid-range` /
  `tanpa Support/Resistance dekat`.
- **Alert bawaan (4):** harga mendekati Support, mendekati Resistance, bias
  berubah jadi Bullish, bias berubah jadi Bearish.

## Cara pasang (2 menit)

1. Buka [TradingView](https://www.tradingview.com) → **Pine Editor** (di bawah
   chart) → **New** / **Open** → hapus isi editor.
2. Copy seluruh isi `pip-topdown-snr.pine` (dari repo ini) → paste → klik
   **Add to chart**.
3. Selesai. Indikator langsung tampil di chart yang sedang dibuka.

## Chart yang disarankan

- **M15** — semua 5 TF kebaca (W/D/H4/H1/M15).
- **H1** — M15 tampil "–" (Pine tidak bisa ambil timeframe yang lebih rendah
  dari timeframe chart). Bobot dihitung ulang otomatis dari TF yang ada.
- **Daily** — H4/H1/M15 tampil "–".
- Simbol apa saja: XAUUSD, EURUSD, BTCUSD, saham, dll — indikator membaca
  simbol yang sedang dibuka di chart.

## Alert

Setelah indikator terpasang: klik kanan chart → **Add Alert** → Condition →
pilih "Pip: Harga di Support" (atau salah satu dari 4 kondisi) → Create.
Alert bisa dikirim ke email/aplikasi TradingView. (Webhook ke Telegram
butuh server penerima — belum ada di repo ini.)

## Batasan yang perlu diketahui

- **Pivot delay:** level S/R Daily baru terkonfirmasi 5 bar Daily setelah
  terbentuk — ini wajar, sama seperti di screener Python.
- **Tidak repaint** pada data terkonfirmasi (`lookahead` dimatikan). Nilai di
  bar yang sedang berjalan bisa berubah sampai bar itu tutup — itu normal.
- **Level S/R** dihitung dari histori yang dimuat chart (bukan 5 tahun penuh
  seperti screener Python, kecuali chart-nya dimuat jauh ke belakang).
  Makin panjang histori chart, makin lengkap levelnya.
- **Bukan saran trading.** Sama seperti bot: tunggu konfirmasi H1/M15 di
  dekat level sebelum eksekusi.
