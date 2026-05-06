"""
Strategy Engine - RSI + Moving Average Crossover
"""
from collections import deque

from config import (
    KLINE_BUFFER_SIZE,
    MA_LONG_PERIOD,
    MA_SHORT_PERIOD,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
)


class TradingStrategy:
    """Menghitung indikator teknikal dan menghasilkan sinyal trading."""

    def __init__(self, pair: str):
        self.pair = pair.upper()
        self.closes = deque(maxlen=KLINE_BUFFER_SIZE)
        self.prev_ma_short = None
        self.prev_ma_long = None

    @property
    def ready(self) -> bool:
        """Cek apakah data sudah cukup untuk kalkulasi."""
        return len(self.closes) >= max(MA_LONG_PERIOD, RSI_PERIOD + 1)

    def add_price(self, close_price: float) -> None:
        """Tambahkan harga close baru."""
        self.closes.append(close_price)

    def calculate_rsi(self) -> float | None:
        """Hitung RSI (Relative Strength Index)."""
        if len(self.closes) < RSI_PERIOD + 1:
            return None

        prices = list(self.closes)
        deltas = [prices[i] - prices[i - 1] for i in range(-RSI_PERIOD, 0)]

        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]

        avg_gain = sum(gains) / RSI_PERIOD if gains else 0
        avg_loss = sum(losses) / RSI_PERIOD if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_ma(self, period: int) -> float | None:
        """Hitung Simple Moving Average."""
        if len(self.closes) < period:
            return None
        prices = list(self.closes)
        return sum(prices[-period:]) / period

    def evaluate(self) -> dict | None:
        """
        Evaluasi sinyal trading berdasarkan RSI + MA Crossover.

        Returns:
            dict dengan sinyal atau None jika tidak ada sinyal.
            {
                "signal": "BUY" | "SELL",
                "pair": str,
                "price": float,
                "rsi": float,
                "ma_short": float,
                "ma_long": float,
                "reasons": list[str]
            }
        """
        if not self.ready:
            return None

        rsi = self.calculate_rsi()
        ma_short = self.calculate_ma(MA_SHORT_PERIOD)
        ma_long = self.calculate_ma(MA_LONG_PERIOD)

        if rsi is None or ma_short is None or ma_long is None:
            return None

        current_price = self.closes[-1]
        reasons = []
        signal = None

        # === Sinyal BELI ===
        buy_score = 0

        # RSI oversold
        if rsi < RSI_OVERSOLD:
            buy_score += 1
            reasons.append(f"RSI {rsi:.1f} (Oversold < {RSI_OVERSOLD})")

        # MA cross up (short MA di atas long MA, sebelumnya di bawah)
        if self.prev_ma_short is not None and self.prev_ma_long is not None:
            if ma_short > ma_long and self.prev_ma_short <= self.prev_ma_long:
                buy_score += 1
                reasons.append(
                    f"MA Cross Up (MA{MA_SHORT_PERIOD} > MA{MA_LONG_PERIOD})"
                )

        # Harga di atas MA short (konfirmasi bullish)
        if current_price > ma_short:
            buy_score += 1
            reasons.append("Harga di atas MA Short (Bullish)")

        # === Sinyal JUAL ===
        sell_score = 0
        sell_reasons = []

        # RSI overbought
        if rsi > RSI_OVERBOUGHT:
            sell_score += 1
            sell_reasons.append(f"RSI {rsi:.1f} (Overbought > {RSI_OVERBOUGHT})")

        # MA cross down
        if self.prev_ma_short is not None and self.prev_ma_long is not None:
            if ma_short < ma_long and self.prev_ma_short >= self.prev_ma_long:
                sell_score += 1
                sell_reasons.append(
                    f"MA Cross Down (MA{MA_SHORT_PERIOD} < MA{MA_LONG_PERIOD})"
                )

        # Tentukan sinyal (butuh minimal 2 konfirmasi)
        if buy_score >= 2:
            signal = "BUY"
        elif sell_score >= 2:
            signal = "SELL"
            reasons = sell_reasons

        # Update previous MA
        self.prev_ma_short = ma_short
        self.prev_ma_long = ma_long

        if signal:
            return {
                "signal": signal,
                "pair": self.pair,
                "price": current_price,
                "rsi": rsi,
                "ma_short": ma_short,
                "ma_long": ma_long,
                "reasons": reasons,
            }

        # Tetap update previous MA meskipun tidak ada sinyal
        return None
