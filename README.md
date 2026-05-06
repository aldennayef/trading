# Crypto Trading Bot - Notifikasi Telegram

Bot trading cryptocurrency yang memonitor harga real-time via Binance WebSocket dan memberikan sinyal **BUY**, **Take Profit (TP)**, dan **Cut Loss (CL)** ke Telegram.

## Fitur

- **Real-time monitoring** 8 pair: BTC, ETH, SOL, DOGE, SHIB, TRX, XRP, 1MBABYDOGE (vs USDT)
- **Triple Filter System** — sinyal harus melewati 3 gate wajib:
  1. **Fibonacci Retracement** — harga di level support/resistance
  2. **EMA 200** — filter trend jangka panjang (BUY hanya di uptrend, SELL hanya di downtrend)
  3. **ADX ≥ 25** — trend harus cukup kuat (menghindari sinyal di market sideways)
- **7 Indikator Penguat** untuk konfirmasi:
  - Stochastic RSI (timing entry presisi)
  - RSI (Relative Strength Index)
  - Moving Average Crossover (MA7 vs MA25)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
  - Volume Analysis
  - ATR (Average True Range) — TP/CL dinamis berdasarkan volatilitas
- **Triple Filter + minimal 2 konfirmasi** untuk setiap sinyal
- **ATR-based TP/CL** — target disesuaikan otomatis per pair berdasarkan volatilitas
- **Notifikasi Telegram** otomatis untuk sinyal BUY, TP, dan CL
- **Auto-reconnect** jika koneksi WebSocket terputus
- **Position tracking** dengan persistensi ke file JSON

## Arsitektur

```
main.py              → Entry point & orchestrator
config.py            → Konfigurasi (pairs, indikator, filter)
strategy.py          → Strategy engine (10 indikator)
binance_ws.py        → Binance WebSocket client (OHLCV)
position_manager.py  → Tracking posisi aktif & history
notifier.py          → Telegram notification service
```

## Alur Sistem

```
Binance WebSocket (kline: high, low, close, volume)
       │
       ├─→ Candle Close → Strategy Engine
       │                      │
       │                      ├─→ Gate 1: Fibonacci Retracement (WAJIB)
       │                      │     • Deteksi swing high/low (30 candle)
       │                      │     • BUY: harga dekat Fib 0.618/0.786 (support)
       │                      │     • SELL: harga dekat Fib 0.236/0.382 (resistance)
       │                      │
       │                      ├─→ Gate 2: EMA 200 (WAJIB)
       │                      │     • BUY: harga di atas EMA 200 (uptrend)
       │                      │     • SELL: harga di bawah EMA 200 (downtrend)
       │                      │
       │                      ├─→ Gate 3: ADX ≥ 25 (WAJIB)
       │                      │     • Hanya trade saat trend kuat
       │                      │
       │                      ├─→ Semua gate lolos → Cek 7 Indikator Penguat
       │                      │     • Stochastic RSI oversold/overbought
       │                      │     • RSI < 30 / RSI > 70
       │                      │     • MA Cross Up/Down
       │                      │     • MACD Bullish/Bearish
       │                      │     • Harga vs Bollinger Bands
       │                      │     • Volume Spike (≥ 1.5x avg)
       │                      │
       │                      ├─→ ≥ 2 konfirmasi BUY? → ATR TP/CL → Notif + Buka posisi
       │                      │
       │                      └─→ ≥ 2 konfirmasi SELL? → Kirim peringatan
       │
       └─→ Price Update → Position Manager
                              │
                              ├─→ Harga ≥ TP (ATR-based) → Notif Take Profit
                              └─→ Harga ≤ CL (ATR-based) → Notif Cut Loss
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
| `TP_PERCENT` | `3.0` | Take Profit default (fallback jika ATR tidak tersedia) |
| `CL_PERCENT` | `2.0` | Cut Loss default (fallback jika ATR tidak tersedia) |
| `LOG_LEVEL` | `INFO` | Level logging |

## Indikator Teknikal

### Gate Wajib (harus semua terpenuhi)

#### 1. Fibonacci Retracement
Fibonacci adalah **syarat wajib pertama** untuk semua sinyal.

- **Level Support (BUY):** 0.618 (Golden Ratio), 0.786
- **Level Resistance (SELL):** 0.236, 0.382
- **Toleransi:** ±0.5% dari level Fibonacci
- **Swing High/Low:** Dideteksi otomatis dari 30 candle terakhir
- **Formula:** `level = swing_high - (swing_high - swing_low) × ratio`

#### 2. EMA 200 (Exponential Moving Average 200)
Filter trend jangka panjang yang mencegah trading melawan trend besar.

- **BUY:** Harga harus **di atas** EMA 200 (uptrend confirmed)
- **SELL:** Harga harus **di bawah** EMA 200 (downtrend confirmed)
- Mengurangi sinyal palsu saat harga bergerak melawan trend utama

#### 3. ADX (Average Directional Index)
Mengukur kekuatan trend. Hanya trade saat trend cukup kuat.

- **ADX ≥ 25:** Trend kuat → sinyal diproses
- **ADX < 25:** Market sideways → sinyal diabaikan
- Menggunakan True Range + Directional Movement dari data High/Low/Close
- Periode: 14

### Indikator Penguat (butuh min 2 dari 7)

#### 1. Stochastic RSI
Versi RSI yang lebih sensitif untuk timing entry yang presisi.

- **%K < 20:** Oversold → konfirmasi beli
- **%K > 80:** Overbought → konfirmasi jual
- Parameter: Period=14, Smooth K=3, Smooth D=3

#### 2. RSI (Relative Strength Index)
- **RSI < 30:** Oversold → konfirmasi beli
- **RSI > 70:** Overbought → konfirmasi jual
- Periode: 14

#### 3. Moving Average Crossover
- **MA7 cross di atas MA25:** Konfirmasi bullish
- **MA7 cross di bawah MA25:** Konfirmasi bearish

#### 4. MACD (Moving Average Convergence Divergence)
- **MACD Bullish Cross:** Histogram negatif → positif → konfirmasi beli
- **MACD Bearish Cross:** Histogram positif → negatif → konfirmasi jual
- Parameter: Fast=12, Slow=26, Signal=9

#### 5. Bollinger Bands
- **Harga ≤ Lower Band:** Oversold → konfirmasi beli
- **Harga ≥ Upper Band:** Overbought → konfirmasi jual
- Periode: 20, Standar Deviasi: 2.0

#### 6. Volume Analysis
- **Volume Spike** (≥ 1.5x rata-rata): Konfirmasi kekuatan sinyal
- Periode MA Volume: 20

#### 7. ATR (Average True Range) — TP/CL Dinamis
ATR mengukur volatilitas dan menyesuaikan target TP/CL secara otomatis.

- **TP = Entry + ATR × 2.0** (pair volatile dapat target lebih lebar)
- **CL = Entry - ATR × 1.5** (stop loss proporsional terhadap volatilitas)
- Pair volatile (SHIB, DOGE): TP/CL otomatis lebih lebar
- Pair stabil (BTC, ETH): TP/CL otomatis lebih ketat
- Periode: 14

### Konfirmasi Sinyal
Sinyal BUY/SELL dikirim hanya jika:
1. **Fibonacci terpenuhi** (harga di level support/resistance)
2. **EMA 200 terpenuhi** (harga searah trend besar)
3. **ADX ≥ 25** (trend cukup kuat)
4. **Minimal 2 indikator penguat** mendukung arah yang sama

Semakin tinggi skor konfirmasi, semakin kuat sinyalnya.

## Contoh Notifikasi

```
🟢 SINYAL BELI (Fib+ADX+EMA200 + 4 konfirmasi)
━━━━━━━━━━━━━━━━━━
📊 Pair: BTCUSDT
💰 Entry: $97,500.00
🎯 TP: $98,450.00 (ATR-based)
🔴 CL: $96,787.50 (ATR-based)
━━━━━━━━━━━━━━━━━━
📈 Konfirmasi:
  • Fib 0.618 Support ($96,800.00)
  • EMA 200: $95,200.00 (Harga di atas = Uptrend)
  • ADX 32.5 (Trend Kuat >= 25)
  • Stoch RSI %K 15.3 (Oversold < 20)
  • RSI 28.5 (Oversold < 30)
  • MACD Bullish Cross (Hist: 0.0012)
  • Volume Spike (1250.50 >= 1.5x avg)
━━━━━━━━━━━━━━━━━━
📐 Fibonacci:
📐 Fib: $95,000.00 - $99,000.00
📐 Level: 0.618 = $96,528.00
📊 Stoch RSI: %K 15.3 | %D 18.7
📉 RSI: 28.5
📊 EMA 200: $95,200.00
📊 MA Short: $97,200.00
📊 MA Long: $96,800.00
📊 MACD: 0.0045 | Signal: 0.0033 | Hist: 0.0012
📊 BB: Upper $98,500.00 | Lower $96,000.00
📊 Volume: 1250.50 (1.8x avg)
📊 ADX: 32.5 | +DI: 28.1 | -DI: 15.3
📊 ATR: $475.00
━━━━━━━━━━━━━━━━━━
🕐 2026-05-06 08:40 UTC
```

## Disclaimer

> Bot ini hanya memberikan **notifikasi/rekomendasi** berdasarkan indikator teknikal.
> Bukan merupakan saran investasi. Selalu lakukan riset sendiri (DYOR).
> Penggunaan bot ini sepenuhnya menjadi tanggung jawab pengguna.
