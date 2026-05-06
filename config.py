"""
Konfigurasi Bot Trading Cryptocurrency
"""
import os

# === Telegram Bot Configuration ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Trading Pairs ===
TRADING_PAIRS = [
    "btcusdt",
    "ethusdt",
    "solusdt",
    "dogeusdt",
    "shibusdt",
    "trxusdt",
    "xrpusdt",
    "1mbabydogeusdt",
]

# === Take Profit & Cut Loss (dalam persen) ===
TP_PERCENT = float(os.getenv("TP_PERCENT", "3.0"))
CL_PERCENT = float(os.getenv("CL_PERCENT", "2.0"))

# === Indikator RSI ===
RSI_PERIOD = 14
RSI_OVERSOLD = 30  # Sinyal beli jika RSI < 30
RSI_OVERBOUGHT = 70  # Sinyal jual jika RSI > 70

# === Moving Average ===
MA_SHORT_PERIOD = 7  # MA pendek
MA_LONG_PERIOD = 25  # MA panjang

# === MACD (Moving Average Convergence Divergence) ===
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# === Bollinger Bands ===
BB_PERIOD = 20
BB_STD_DEV = 2.0  # Standar deviasi

# === Volume ===
VOLUME_MA_PERIOD = 20  # Periode MA untuk volume
VOLUME_SPIKE_MULTIPLIER = 1.5  # Volume dianggap spike jika >= 1.5x rata-rata

# === Fibonacci Retracement ===
FIB_SWING_LOOKBACK = 30  # Jumlah candle untuk deteksi swing high/low
FIB_TOLERANCE = 0.005  # 0.5% toleransi proximity ke level Fibonacci
FIB_LEVELS = [0.236, 0.382, 0.500, 0.618, 0.786]
FIB_BUY_LEVELS = [0.618, 0.786]  # Level support untuk sinyal beli
FIB_SELL_LEVELS = [0.236, 0.382]  # Level resistance untuk sinyal jual

# === Minimum Konfirmasi untuk Sinyal (di atas Fibonacci) ===
MIN_BUY_CONFIRMATIONS = 2  # Fibonacci wajib + minimal 2 indikator lain
MIN_SELL_CONFIRMATIONS = 2  # Fibonacci wajib + minimal 2 indikator lain

# === Kline/Candlestick Interval ===
KLINE_INTERVAL = "1m"  # 1 menit
KLINE_BUFFER_SIZE = 100  # Cukup untuk semua indikator

# === Binance WebSocket ===
BINANCE_WS_BASE = "wss://stream.binance.com:9443"
BINANCE_REST_BASE = "https://api.binance.com"

# === Cooldown (detik) - jeda antar sinyal untuk pair yang sama ===
SIGNAL_COOLDOWN = 300  # 5 menit

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
