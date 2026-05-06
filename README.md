# Crypto Trading Bot - Notifikasi Telegram

Bot trading cryptocurrency yang memonitor harga real-time via Binance WebSocket dan memberikan sinyal **BUY**, **Take Profit (TP)**, dan **Cut Loss (CL)** ke Telegram.

## Fitur

- **Real-time monitoring** 8 pair: BTC, ETH, SOL, DOGE, SHIB, TRX, XRP, 1MBABYDOGE (vs USDT)
- **Fibonacci Retracement sebagai filter WAJIB** — sinyal hanya muncul saat harga di level Fibonacci
- **5 Indikator Penguat** untuk konfirmasi:
  - RSI (Relative Strength Index)
  - Moving Average Crossover (MA7 vs MA25)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Volume Analysis
- **Fibonacci + minimal 2 konfirmasi** untuk setiap sinyal (mengurangi false signal)
- **Notifikasi Telegram** otomatis untuk sinyal BUY, TP, dan CL
- **Auto-reconnect** jika koneksi WebSocket terputus
- **Position tracking** dengan persistensi ke file JSON
- **Configurable** TP/CL persentase via environment variable

## Arsitektur

```
main.py              → Entry point & orchestrator
config.py            → Konfigurasi (pairs, TP/CL, indikator, Fibonacci)
strategy.py          → Strategy engine (Fibonacci + RSI + MA + MACD + BB + Volume)
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
       │                      ├─→ Fibonacci Retracement (WAJIB)
       │                      │     • Deteksi swing high/low (30 candle)
       │                      │     • Hitung level: 0.236, 0.382, 0.500, 0.618, 0.786
       │                      │     • BUY: harga dekat Fib 0.618/0.786 (support)
       │                      │     • SELL: harga dekat Fib 0.236/0.382 (resistance)
       │                      │
       │                      ├─→ Jika Fibonacci terpenuhi → Cek 5 Indikator Penguat
       │                      │     • RSI < 30 (oversold) / RSI > 70 (overbought)
       │                      │     • MA Cross Up/Down (MA7 vs MA25)
       │                      │     • MACD Bullish/Bearish Cross
       │                      │     • Harga vs Bollinger Bands
       │                      │     • Volume Spike (≥ 1.5x rata-rata)
       │                      │
       │                      ├─→ Fib + ≥ 2 konfirmasi BUY? → Kirim notif + Buka posisi
       │                      │
       │                      └─→ Fib + ≥ 2 konfirmasi SELL? → Kirim peringatan
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

### Linux / macOS
```bash
# Cara 1: Load dari file .env
export $(cat .env | xargs)
python main.py

# Cara 2: Set manual
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python main.py
```

### Windows (PowerShell)
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

### Fibonacci Retracement (WAJIB)
Fibonacci adalah **syarat wajib** untuk semua sinyal. Tanpa harga berada di level Fibonacci, sinyal **tidak akan dikirim** meskipun semua indikator lain mendukung.

- **Level Support (BUY):** 0.618 (Golden Ratio), 0.786
  - Harga harus berada dalam **±0.5%** dari level Fibonacci support
- **Level Resistance (SELL):** 0.236, 0.382
  - Harga harus berada dalam **±0.5%** dari level Fibonacci resistance
- **Swing High/Low:** Dideteksi otomatis dari 30 candle terakhir
- **Level dihitung:** `swing_high - (swing_high - swing_low) × ratio`

### Indikator Penguat

#### 1. RSI (Relative Strength Index)
- **RSI < 30**: Oversold → konfirmasi beli
- **RSI > 70**: Overbought → konfirmasi jual
- Periode: 14

#### 2. Moving Average Crossover
- **MA7 cross di atas MA25**: Konfirmasi bullish
- **MA7 cross di bawah MA25**: Konfirmasi bearish

#### 3. MACD (Moving Average Convergence Divergence)
- **MACD Bullish Cross**: Histogram dari negatif ke positif → konfirmasi beli
- **MACD Bearish Cross**: Histogram dari positif ke negatif → konfirmasi jual
- Parameter: Fast=12, Slow=26, Signal=9

#### 4. Bollinger Bands
- **Harga ≤ Lower Band**: Oversold → konfirmasi beli
- **Harga ≥ Upper Band**: Overbought → konfirmasi jual
- Periode: 20, Standar Deviasi: 2.0

#### 5. Volume Analysis
- **Volume Spike** (≥ 1.5x rata-rata): Konfirmasi kekuatan sinyal
- Periode MA Volume: 20

### Konfirmasi Sinyal
Sinyal BUY/SELL dikirim hanya jika:
1. **Fibonacci terpenuhi** (harga di level support/resistance)
2. **Minimal 2 indikator penguat** mendukung arah yang sama

Semakin tinggi skor konfirmasi, semakin kuat sinyalnya.

## Contoh Notifikasi

```
🟢 SINYAL BELI (Fib + 3 konfirmasi)
━━━━━━━━━━━━━━━━━━
📊 Pair: BTCUSDT
💰 Entry: $97,500.00
🎯 TP: $100,425.00
🔴 CL: $95,550.00
━━━━━━━━━━━━━━━━━━
📈 Konfirmasi (Fib + 3):
  • Fib 0.618 Support ($96,800.00)
  • RSI 28.5 (Oversold < 30)
  • MACD Bullish Cross (Hist: 0.0012)
  • Volume Spike (1250.50 >= 1.5x avg)
━━━━━━━━━━━━━━━━━━
📐 Fibonacci:
📐 Fib: $95,000.00 - $99,000.00
📐 Level: 0.618 = $96,528.00
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
