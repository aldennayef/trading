# 🤖 Crypto Trading Bot - Notifikasi Telegram

Bot trading cryptocurrency yang memonitor harga real-time via Binance WebSocket dan memberikan sinyal **BUY**, **Take Profit (TP)**, dan **Cut Loss (CL)** ke Telegram.

## Fitur

- **Real-time monitoring** 5 pair: BTC, ETH, SOL, DOGE, SHIB (vs USDT)
- **Strategi RSI + Moving Average Crossover** untuk sinyal yang lebih akurat
- **Notifikasi Telegram** otomatis untuk sinyal BUY, TP, dan CL
- **Auto-reconnect** jika koneksi WebSocket terputus
- **Position tracking** dengan persistensi ke file JSON
- **Configurable** TP/CL persentase via environment variable

## Arsitektur

```
main.py              → Entry point & orchestrator
config.py            → Konfigurasi (pairs, TP/CL, indikator)
strategy.py          → RSI + MA Crossover strategy engine
binance_ws.py        → Binance WebSocket client
position_manager.py  → Tracking posisi aktif & history
notifier.py          → Telegram notification service
```

## Alur Sistem

```
Binance WebSocket (kline stream)
       │
       ├─→ Candle Close → Strategy Engine
       │                      │
       │                      ├─→ RSI < 30 + MA Cross Up → Sinyal BUY
       │                      │     → Buka posisi + Set TP/CL
       │                      │     → Kirim notif Telegram
       │                      │
       │                      └─→ RSI > 70 + MA Cross Down → Sinyal SELL
       │                            → Kirim peringatan Telegram
       │
       └─→ Price Update → Position Manager
                              │
                              ├─→ Harga ≥ TP → Notif Take Profit ✅
                              └─→ Harga ≤ CL → Notif Cut Loss ❌
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

Atau langsung set environment variable:

```bash
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python main.py
```

## Konfigurasi

| Variable | Default | Keterangan |
|----------|---------|------------|
| `TELEGRAM_BOT_TOKEN` | - | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | - | Chat ID tujuan notifikasi |
| `TP_PERCENT` | `3.0` | Take Profit dalam persen |
| `CL_PERCENT` | `2.0` | Cut Loss dalam persen |
| `LOG_LEVEL` | `INFO` | Level logging |

## Strategi Trading

### RSI (Relative Strength Index)
- **RSI < 30**: Oversold → potensi sinyal beli
- **RSI > 70**: Overbought → potensi sinyal jual

### Moving Average Crossover
- **MA7 cross di atas MA25**: Sinyal bullish
- **MA7 cross di bawah MA25**: Sinyal bearish

### Konfirmasi Sinyal
Sinyal BUY/SELL dikirim hanya jika **minimal 2 indikator** mendukung arah yang sama (mengurangi false signal).

## Contoh Notifikasi

```
🟢 SINYAL BELI
━━━━━━━━━━━━━━━━━━
📊 Pair: BTCUSDT
💰 Entry: $97,500.00
🎯 TP: $100,425.00
🔴 CL: $95,550.00
━━━━━━━━━━━━━━━━━━
📈 Indikator:
  • RSI 28.5 (Oversold < 30)
  • MA Cross Up (MA7 > MA25)
📉 RSI: 28.5
━━━━━━━━━━━━━━━━━━
🕐 2026-05-06 04:40 UTC
```

## Disclaimer

> ⚠️ Bot ini hanya memberikan **notifikasi/rekomendasi** berdasarkan indikator teknikal.
> Bukan merupakan saran investasi. Selalu lakukan riset sendiri (DYOR).
> Penggunaan bot ini sepenuhnya menjadi tanggung jawab pengguna.
