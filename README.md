# Crypto Trading Bot - Notifikasi Telegram

Bot trading cryptocurrency yang memonitor harga real-time via Binance WebSocket dan memberikan sinyal **BUY**, **Take Profit (TP)**, dan **Cut Loss (CL)** ke Telegram.

## Fitur

- **Real-time monitoring** 5 pair: BTC, ETH, SOL, DOGE, SHIB (vs USDT)
- **5 Indikator Teknikal** untuk sinyal yang lebih akurat:
  - RSI (Relative Strength Index)
  - Moving Average Crossover (MA7 vs MA25)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Volume Analysis
- **Minimal 3 konfirmasi** untuk setiap sinyal (mengurangi false signal)
- **Notifikasi Telegram** otomatis untuk sinyal BUY, TP, dan CL
- **Auto-reconnect** jika koneksi WebSocket terputus
- **Position tracking** dengan persistensi ke file JSON
- **Configurable** TP/CL persentase via environment variable

## Arsitektur

```
main.py              → Entry point & orchestrator
config.py            → Konfigurasi (pairs, TP/CL, indikator)
strategy.py          → Strategy engine (RSI + MA + MACD + BB + Volume)
binance_ws.py        → Binance WebSocket client
position_manager.py  → Tracking posisi aktif & history
notifier.py          → Telegram notification service
```

## Alur Sistem

```
Binance WebSocket (kline stream + volume)
       │
       ├─→ Candle Close → Strategy Engine
       │                      │
       │                      ├─→ Hitung 5 Indikator
       │                      │     • RSI < 30 (oversold)
       │                      │     • MA Cross Up (MA7 > MA25)
       │                      │     • MACD Bullish Cross
       │                      │     • Harga ≤ BB Lower Band
       │                      │     • Volume Spike (≥ 1.5x rata-rata)
       │                      │
       │                      ├─→ ≥ 3 konfirmasi BUY? → Kirim notif + Buka posisi
       │                      │
       │                      └─→ ≥ 3 konfirmasi SELL? → Kirim peringatan
       │
       └─→ Price Update → Position Manager
                              │
                              ├─→ Harga ≥ TP (+3%) → Notif Take Profit
                              └─→ Harga ≤ CL (-2%) → Notif Cut Loss
```

## Prasyarat

- Python 3.10+
- Telegram Bot Token (dari [@BotFather](https://t.me/BotFather))
- Chat ID Telegram (dari [@userinfobot](https://t.me/userinfobot))

## Instalasi

```bash
cd crypto_trading_bot

# Install dependencies
pip install -r requirements.txt

# Copy dan edit konfigurasi
cp .env.example .env
# Edit .env dengan token Telegram kamu
```

## Setup Telegram Bot

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot` dan ikuti instruksinya
3. Copy **Bot Token** yang diberikan
4. Cari **@userinfobot**, kirim `/start` untuk dapat **Chat ID**
5. Masukkan keduanya ke file `.env`

## Menjalankan Bot

```bash
# Load environment variables
export $(cat .env | xargs)

# Jalankan bot
python main.py
```

Windows (PowerShell):
```powershell
$env:TELEGRAM_BOT_TOKEN="your_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"
py main.py
```

## Konfigurasi

| Variable | Default | Keterangan |
|----------|---------|------------|
| `TELEGRAM_BOT_TOKEN` | - | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | - | Chat ID tujuan notifikasi |
| `TP_PERCENT` | `3.0` | Take Profit dalam persen |
| `CL_PERCENT` | `2.0` | Cut Loss dalam persen |
| `LOG_LEVEL` | `INFO` | Level logging |

## Indikator Teknikal

### 1. RSI (Relative Strength Index)
- **RSI < 30**: Oversold → potensi sinyal beli
- **RSI > 70**: Overbought → potensi sinyal jual
- Periode: 14

### 2. Moving Average Crossover
- **MA7 cross di atas MA25**: Sinyal bullish
- **MA7 cross di bawah MA25**: Sinyal bearish

### 3. MACD (Moving Average Convergence Divergence)
- **MACD Bullish Cross**: Histogram dari negatif ke positif → sinyal beli
- **MACD Bearish Cross**: Histogram dari positif ke negatif → sinyal jual
- Parameter: Fast=12, Slow=26, Signal=9

### 4. Bollinger Bands
- **Harga ≤ Lower Band**: Oversold → potensi sinyal beli
- **Harga ≥ Upper Band**: Overbought → potensi sinyal jual
- Periode: 20, Standar Deviasi: 2.0

### 5. Volume Analysis
- **Volume Spike** (≥ 1.5x rata-rata): Konfirmasi kekuatan sinyal
- Periode MA Volume: 20

### Konfirmasi Sinyal
Sinyal BUY/SELL dikirim hanya jika **minimal 3 indikator** mendukung arah yang sama. Semakin tinggi skor konfirmasi, semakin kuat sinyalnya (maks 7).

## Contoh Notifikasi

```
🟢 SINYAL BELI (Skor: 4)
━━━━━━━━━━━━━━━━━━
📊 Pair: BTCUSDT
💰 Entry: $97,500.00
🎯 TP: $100,425.00
🔴 CL: $95,550.00
━━━━━━━━━━━━━━━━━━
📈 Konfirmasi (4):
  • RSI 28.5 (Oversold < 30)
  • MA Cross Up (MA7 > MA25)
  • MACD Bullish Cross (Hist: 0.0012)
  • Volume Spike (1250.50 >= 1.5x avg)
━━━━━━━━━━━━━━━━━━
📉 RSI: 28.5
📊 MA Short: $97,200.00
📊 MA Long: $96,800.00
📊 MACD: 0.0045 | Signal: 0.0033 | Hist: 0.0012
📊 BB: Upper $98,500.00 | Lower $96,000.00
📊 Volume: 1250.50 (1.8x avg)
━━━━━━━━━━━━━━━━━━
🕐 2026-05-06 08:40 UTC
```

## Disclaimer

> Bot ini hanya memberikan **notifikasi/rekomendasi** berdasarkan indikator teknikal.
> Bukan merupakan saran investasi. Selalu lakukan riset sendiri (DYOR).
> Penggunaan bot ini sepenuhnya menjadi tanggung jawab pengguna.
