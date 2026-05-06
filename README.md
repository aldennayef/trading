# Crypto Trading Bot - Notifikasi Telegram

Bot trading cryptocurrency yang memonitor harga real-time via Binance WebSocket dan memberikan sinyal **BUY**, **Take Profit (TP)**, dan **Cut Loss (CL)** ke Telegram.

## Fitur

- **Real-time monitoring** 8 pair: BTC, ETH, SOL, DOGE, SHIB, TRX, XRP, 1MBABYDOGE (vs USDT)
- **Confidence-based scoring** — sinyal hanya dikirim jika confidence ≥ 97%
- **10 indikator teknikal** (semua opsional, dihitung berbobot):
  - Fibonacci Retracement, EMA 200, ADX, Stochastic RSI, RSI
  - MA Crossover, MACD, Bollinger Bands, Volume, Price vs MA
- **LLM integration (opsional)** — OpenAI-compatible API untuk boost confidence
  - Auto-detect: jika `LLM_API_KEY` diset → LLM aktif, jika tidak → tetap jalan normal
  - Custom provider: Groq, Together AI, Ollama, dll via `LLM_BASE_URL`
- **ATR-based dynamic TP/CL** — target disesuaikan otomatis per pair berdasarkan volatilitas
- **Notifikasi Telegram** otomatis untuk sinyal BUY, TP, dan CL
- **Auto-reconnect** jika koneksi WebSocket terputus
- **Position tracking** dengan persistensi ke file JSON

## Arsitektur

```
main.py              → Entry point & orchestrator
config.py            → Konfigurasi (pairs, indikator, LLM, confidence)
strategy.py          → Strategy engine (10 indikator, confidence scoring)
llm_analyzer.py      → LLM integration (OpenAI-compatible)
binance_ws.py        → Binance WebSocket client (OHLCV)
position_manager.py  → Tracking posisi aktif & history
notifier.py          → Telegram notification service
```

## Alur Sinyal

```
Binance WebSocket (kline: high, low, close, volume)
       │
       ├─→ Candle Close → Strategy Engine
       │                      │
       │                      ├─→ Hitung 10 indikator
       │                      │     Setiap indikator → skor 0.0-1.0
       │                      │     Skor × bobot → confidence score
       │                      │
       │                      ├─→ Confidence ≥ 87%? (pre-threshold)
       │                      │     │
       │                      │     ├─→ Ya + LLM aktif → Kirim ke LLM
       │                      │     │     LLM return boost 0-10%
       │                      │     │     Final confidence = tech + LLM boost
       │                      │     │
       │                      │     └─→ Tanpa LLM → Langsung cek threshold
       │                      │
       │                      ├─→ Final confidence ≥ 97%?
       │                      │     │
       │                      │     ├─→ BUY → ATR TP/CL → Notif + Posisi
       │                      │     └─→ SELL → Kirim peringatan
       │                      │
       │                      └─→ < 97% → Skip (log debug)
       │
       └─→ Price Update → Position Manager
                              │
                              ├─→ Harga ≥ TP → Notif Take Profit
                              └─→ Harga ≤ CL → Notif Cut Loss
```

## Prasyarat

- Python 3.10+
- Telegram Bot Token (dari [@BotFather](https://t.me/BotFather))
- Chat ID Telegram (dari [@userinfobot](https://t.me/userinfobot))
- (Opsional) API key LLM — OpenAI, Groq, Together AI, dll

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

### Dengan LLM (opsional)
```bash
# Linux/macOS
export LLM_API_KEY="sk-your-openai-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # atau Groq, Together, dll
export LLM_MODEL="gpt-4o-mini"
python main.py

# Windows PowerShell
$env:LLM_API_KEY="sk-your-openai-key"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
py main.py
```

Bot akan otomatis mendeteksi apakah `LLM_API_KEY` diisi:
- **Diisi** → LLM aktif, memberikan boost confidence hingga +10%
- **Kosong** → Bot tetap jalan normal tanpa LLM

## Konfigurasi

| Variable | Default | Keterangan |
|----------|---------|------------|
| `TELEGRAM_BOT_TOKEN` | - | Token bot Telegram (wajib) |
| `TELEGRAM_CHAT_ID` | - | Chat ID tujuan notifikasi (wajib) |
| `LLM_API_KEY` | - | API key LLM (opsional, kosong = nonaktif) |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Base URL provider LLM |
| `LLM_MODEL` | `gpt-4o-mini` | Model LLM yang digunakan |
| `MIN_CONFIDENCE` | `97.0` | Minimum confidence (%) untuk mengirim sinyal |
| `TP_PERCENT` | `3.0` | Take Profit fallback jika ATR tidak tersedia |
| `CL_PERCENT` | `2.0` | Cut Loss fallback jika ATR tidak tersedia |
| `LOG_LEVEL` | `INFO` | Level logging |

## Confidence Scoring System

Setiap indikator memberikan skor **0.0 sampai 1.0** dikalikan **bobot**-nya:

| Indikator | Bobot | Cara Skor (BUY) | Cara Skor (SELL) |
|-----------|-------|------------------|------------------|
| **EMA 200** | 13 | 1.0 jika harga > EMA200 | 1.0 jika harga < EMA200 |
| **ADX** | 11 | Gradual 0-1 (ADX 15-30) | Gradual 0-1 (ADX 15-30) |
| **Fibonacci** | 10 | 1.0 jika dekat Fib 0.618/0.786 | 1.0 jika dekat Fib 0.236/0.382 |
| **Stochastic RSI** | 10 | Gradual (oversold %K 5-50) | Gradual (overbought %K 50-95) |
| **RSI** | 10 | Gradual (oversold 15-55) | Gradual (overbought 45-85) |
| **MACD** | 10 | 1.0 MACD > signal + hist > 0 | 1.0 MACD < signal + hist < 0 |
| **Volume** | 10 | Gradual (0.5x-2x average) | Gradual (0.5x-2x average) |
| **MA Cross** | 9 | 1.0 fresh cross up, 0.7 above | 1.0 fresh cross down, 0.7 below |
| **Bollinger** | 9 | 1.0 harga ≤ lower band | 1.0 harga ≥ upper band |
| **Price vs MA** | 8 | 1.0 harga > MA short | 1.0 harga < MA short |

**Total bobot: 100**

**Confidence = (Σ skor×bobot) / 100 × 100%**

### Contoh:
- 10 indikator semua skor 1.0 → confidence 100% → sinyal dikirim
- 9 indikator skor 1.0, 1 indikator skor 0.5 → confidence ~95% → TIDAK dikirim (< 97%)
- Semua skor 1.0 + LLM boost 10% → 110% (capped) → dikirim

### LLM Boost:
- Hanya dipanggil jika confidence ≥ 87% (pre-threshold) dan < 97%
- LLM menganalisis semua indikator dan memberikan confidence 0-100
- Boost = LLM confidence × 10% (max +10%)
- Final = tech confidence + LLM boost

## Provider LLM yang Didukung

Bot menggunakan OpenAI-compatible API, sehingga bisa digunakan dengan:

| Provider | Base URL | Model |
|----------|----------|-------|
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4o` |
| **Groq** | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| **Together AI** | `https://api.together.xyz/v1` | `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` |
| **Ollama (lokal)** | `http://localhost:11434/v1` | model lokal apapun |

## Contoh Notifikasi

```
🟢 SINYAL BELI (Confidence: 98.5%)
━━━━━━━━━━━━━━━━━━
📊 Pair: BTCUSDT
💰 Entry: $97,500.00
🎯 TP: $98,450.00 (ATR-based)
🔴 CL: $96,787.50 (ATR-based)
━━━━━━━━━━━━━━━━━━
📈 Alasan:
  • EMA 200: $95,200.00 (Harga di atas = Uptrend)
  • ADX 32.5 (Trend Kuat >= 25)
  • Stoch RSI %K 15.3 (Oversold < 20)
  • RSI 28.5 (Oversold < 30)
  • MACD Bullish Cross (Hist: 0.0012)
  • Volume Spike (1250.50 >= 1.5x avg)
  • Harga di atas MA Short (Bullish)
━━━━━━━━━━━━━━━━━━
🎯 Confidence: 98.5%
🤖 LLM Boost: +3.2%
🤖 LLM: Strong bullish momentum confirmed by multiple indicators
  █████ ema_200: 100%
  █████ adx: 100%
  █████ stoch_rsi: 100%
  █████ rsi: 100%
  █████ macd: 100%
  █████ volume: 100%
  █████ price_ma: 100%
  ███░░ ma_cross: 70%
  ███░░ bb: 60%
  ░░░░░ fibonacci: 0%
━━━━━━━━━━━━━━━━━━
📊 Indikator detail...
━━━━━━━━━━━━━━━━━━
🕐 2026-05-06 08:40 UTC
```

## Disclaimer

> Bot ini hanya memberikan **notifikasi/rekomendasi** berdasarkan indikator teknikal.
> Bukan merupakan saran investasi. Selalu lakukan riset sendiri (DYOR).
> Penggunaan bot ini sepenuhnya menjadi tanggung jawab pengguna.
