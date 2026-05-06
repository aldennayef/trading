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

# === Take Profit & Cut Loss default (dalam persen, fallback jika ATR tidak tersedia) ===
TP_PERCENT = float(os.getenv("TP_PERCENT", "3.0"))
CL_PERCENT = float(os.getenv("CL_PERCENT", "2.0"))

# === Indikator RSI ===
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# === Stochastic RSI ===
STOCH_RSI_PERIOD = 14
STOCH_RSI_SMOOTH_K = 3
STOCH_RSI_SMOOTH_D = 3
STOCH_RSI_OVERSOLD = 20
STOCH_RSI_OVERBOUGHT = 80

# === Moving Average ===
MA_SHORT_PERIOD = 7
MA_LONG_PERIOD = 25

# === EMA 200 (filter trend jangka panjang) ===
EMA_LONG_PERIOD = 200

# === MACD (Moving Average Convergence Divergence) ===
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# === Bollinger Bands ===
BB_PERIOD = 20
BB_STD_DEV = 2.0

# === Volume ===
VOLUME_MA_PERIOD = 20
VOLUME_SPIKE_MULTIPLIER = 1.5

# === ADX (Average Directional Index) ===
ADX_PERIOD = 14
ADX_STRONG_TREND = 25  # ADX >= 25 = trend kuat

# === ATR (Average True Range) ===
ATR_PERIOD = 14
ATR_TP_MULTIPLIER = 2.0  # TP = entry + ATR * multiplier
ATR_CL_MULTIPLIER = 1.5  # CL = entry - ATR * multiplier

# === Fibonacci Retracement ===
FIB_SWING_LOOKBACK = 30
FIB_TOLERANCE = 0.005
FIB_LEVELS = [0.236, 0.382, 0.500, 0.618, 0.786]
FIB_BUY_LEVELS = [0.618, 0.786]
FIB_SELL_LEVELS = [0.236, 0.382]

# === Minimum Konfirmasi untuk Sinyal (di atas Fibonacci) ===
MIN_BUY_CONFIRMATIONS = 2
MIN_SELL_CONFIRMATIONS = 2

# === Kline/Candlestick Interval ===
KLINE_INTERVAL = "1m"
KLINE_BUFFER_SIZE = 250  # Ditambah untuk EMA 200

# === Binance WebSocket ===
BINANCE_WS_BASE = "wss://stream.binance.com:9443"
BINANCE_REST_BASE = "https://api.binance.com"

# === Cooldown (detik) - jeda antar sinyal untuk pair yang sama ===
SIGNAL_COOLDOWN = 300

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
