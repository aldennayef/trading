"""
Strategy Engine - RSI + MA Crossover + MACD + Bollinger Bands + Volume
"""
import math
from collections import deque

from config import (
    BB_PERIOD,
    BB_STD_DEV,
    KLINE_BUFFER_SIZE,
    MA_LONG_PERIOD,
    MA_SHORT_PERIOD,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    MIN_BUY_CONFIRMATIONS,
    MIN_SELL_CONFIRMATIONS,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
    VOLUME_MA_PERIOD,
    VOLUME_SPIKE_MULTIPLIER,
)


class TradingStrategy:
    """Menghitung indikator teknikal dan menghasilkan sinyal trading."""

    def __init__(self, pair: str):
        self.pair = pair.upper()
        self.closes = deque(maxlen=KLINE_BUFFER_SIZE)
        self.volumes = deque(maxlen=KLINE_BUFFER_SIZE)
        self.prev_ma_short: float | None = None
        self.prev_ma_long: float | None = None
        self.prev_macd_histogram: float | None = None

    @property
    def ready(self) -> bool:
        """Cek apakah data sudah cukup untuk kalkulasi."""
        min_needed = max(
            MA_LONG_PERIOD,
            RSI_PERIOD + 1,
            MACD_SLOW + MACD_SIGNAL,
            BB_PERIOD,
        )
        return len(self.closes) >= min_needed

    def add_price(self, close_price: float, volume: float = 0.0) -> None:
        """Tambahkan harga close dan volume baru."""
        self.closes.append(close_price)
        self.volumes.append(volume)

    # =========================================
    # Indikator: RSI
    # =========================================

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

    # =========================================
    # Indikator: Moving Average
    # =========================================

    def calculate_ma(self, period: int) -> float | None:
        """Hitung Simple Moving Average."""
        if len(self.closes) < period:
            return None
        prices = list(self.closes)
        return sum(prices[-period:]) / period

    def _calculate_ema(self, data: list[float], period: int) -> list[float]:
        """Hitung Exponential Moving Average (internal helper)."""
        if len(data) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for price in data[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema

    # =========================================
    # Indikator: MACD
    # =========================================

    def calculate_macd(self) -> tuple[float | None, float | None, float | None]:
        """
        Hitung MACD (Moving Average Convergence Divergence).

        Returns:
            (macd_line, signal_line, histogram) atau (None, None, None).
        """
        prices = list(self.closes)
        if len(prices) < MACD_SLOW + MACD_SIGNAL:
            return None, None, None

        ema_fast = self._calculate_ema(prices, MACD_FAST)
        ema_slow = self._calculate_ema(prices, MACD_SLOW)

        # Align EMA lengths — EMA slow starts later
        offset = MACD_SLOW - MACD_FAST
        ema_fast_aligned = ema_fast[offset:]

        macd_line_series = [
            f - s for f, s in zip(ema_fast_aligned, ema_slow)
        ]

        if len(macd_line_series) < MACD_SIGNAL:
            return None, None, None

        signal_series = self._calculate_ema(macd_line_series, MACD_SIGNAL)
        if not signal_series:
            return None, None, None

        macd_value = macd_line_series[-1]
        signal_value = signal_series[-1]
        histogram = macd_value - signal_value

        return macd_value, signal_value, histogram

    # =========================================
    # Indikator: Bollinger Bands
    # =========================================

    def calculate_bollinger_bands(
        self,
    ) -> tuple[float | None, float | None, float | None]:
        """
        Hitung Bollinger Bands.

        Returns:
            (upper_band, middle_band, lower_band) atau (None, None, None).
        """
        if len(self.closes) < BB_PERIOD:
            return None, None, None

        prices = list(self.closes)[-BB_PERIOD:]
        middle = sum(prices) / BB_PERIOD
        variance = sum((p - middle) ** 2 for p in prices) / BB_PERIOD
        std_dev = math.sqrt(variance)

        upper = middle + BB_STD_DEV * std_dev
        lower = middle - BB_STD_DEV * std_dev

        return upper, middle, lower

    # =========================================
    # Indikator: Volume Analysis
    # =========================================

    def calculate_volume_signal(self) -> tuple[float | None, float | None, bool]:
        """
        Analisis volume.

        Returns:
            (current_volume, avg_volume, is_volume_spike)
        """
        if len(self.volumes) < VOLUME_MA_PERIOD + 1:
            return None, None, False

        vols = list(self.volumes)
        current_vol = vols[-1]
        avg_vol = sum(vols[-VOLUME_MA_PERIOD - 1:-1]) / VOLUME_MA_PERIOD

        if avg_vol == 0:
            return current_vol, avg_vol, False

        is_spike = current_vol >= avg_vol * VOLUME_SPIKE_MULTIPLIER
        return current_vol, avg_vol, is_spike

    # =========================================
    # Evaluasi Sinyal
    # =========================================

    def evaluate(self) -> dict | None:
        """
        Evaluasi sinyal trading berdasarkan semua indikator.

        Indikator yang digunakan:
        1. RSI — oversold/overbought
        2. MA Crossover — trend direction
        3. MACD — momentum
        4. Bollinger Bands — volatility & mean reversion
        5. Volume — konfirmasi kekuatan

        Butuh minimal MIN_BUY_CONFIRMATIONS / MIN_SELL_CONFIRMATIONS
        konfirmasi untuk menghasilkan sinyal.

        Returns:
            dict dengan sinyal atau None jika tidak ada sinyal.
        """
        if not self.ready:
            return None

        rsi = self.calculate_rsi()
        ma_short = self.calculate_ma(MA_SHORT_PERIOD)
        ma_long = self.calculate_ma(MA_LONG_PERIOD)
        macd_line, macd_signal, macd_histogram = self.calculate_macd()
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands()
        current_vol, avg_vol, vol_spike = self.calculate_volume_signal()

        if rsi is None or ma_short is None or ma_long is None:
            return None

        current_price = self.closes[-1]
        reasons = []

        # === Sinyal BELI ===
        buy_score = 0

        # 1. RSI oversold
        if rsi < RSI_OVERSOLD:
            buy_score += 1
            reasons.append(f"RSI {rsi:.1f} (Oversold < {RSI_OVERSOLD})")

        # 2. MA cross up
        if self.prev_ma_short is not None and self.prev_ma_long is not None:
            if ma_short > ma_long and self.prev_ma_short <= self.prev_ma_long:
                buy_score += 1
                reasons.append(
                    f"MA Cross Up (MA{MA_SHORT_PERIOD} > MA{MA_LONG_PERIOD})"
                )

        # 3. Harga di atas MA short (konfirmasi bullish)
        if current_price > ma_short:
            buy_score += 1
            reasons.append("Harga di atas MA Short (Bullish)")

        # 4. MACD: crossover lebih kuat, fallback ke line>signal jika tidak ada crossover
        macd_buy_counted = False
        if macd_histogram is not None and self.prev_macd_histogram is not None:
            if macd_histogram > 0 and self.prev_macd_histogram <= 0:
                buy_score += 1
                reasons.append(
                    f"MACD Bullish Cross (Hist: {macd_histogram:.4f})"
                )
                macd_buy_counted = True

        if not macd_buy_counted and macd_line is not None and macd_signal is not None:
            if macd_line > macd_signal:
                buy_score += 1
                reasons.append("MACD Line > Signal (Momentum Bullish)")

        # 6. Harga dekat/di bawah Bollinger lower band (oversold)
        if bb_lower is not None and current_price <= bb_lower:
            buy_score += 1
            reasons.append(
                f"Harga di bawah BB Lower ({_fmt(current_price)} <= {_fmt(bb_lower)})"
            )

        # 7. Volume spike (konfirmasi kekuatan)
        if vol_spike:
            buy_score += 1
            reasons.append(
                f"Volume Spike ({current_vol:.2f} >= {VOLUME_SPIKE_MULTIPLIER}x avg)"
            )

        # === Sinyal JUAL ===
        sell_score = 0
        sell_reasons = []

        # 1. RSI overbought
        if rsi > RSI_OVERBOUGHT:
            sell_score += 1
            sell_reasons.append(f"RSI {rsi:.1f} (Overbought > {RSI_OVERBOUGHT})")

        # 2. MA cross down
        if self.prev_ma_short is not None and self.prev_ma_long is not None:
            if ma_short < ma_long and self.prev_ma_short >= self.prev_ma_long:
                sell_score += 1
                sell_reasons.append(
                    f"MA Cross Down (MA{MA_SHORT_PERIOD} < MA{MA_LONG_PERIOD})"
                )

        # 3. MACD: crossover lebih kuat, fallback ke line<signal jika tidak ada crossover
        macd_sell_counted = False
        if macd_histogram is not None and self.prev_macd_histogram is not None:
            if macd_histogram < 0 and self.prev_macd_histogram >= 0:
                sell_score += 1
                sell_reasons.append(
                    f"MACD Bearish Cross (Hist: {macd_histogram:.4f})"
                )
                macd_sell_counted = True

        if not macd_sell_counted and macd_line is not None and macd_signal is not None:
            if macd_line < macd_signal:
                sell_score += 1
                sell_reasons.append("MACD Line < Signal (Momentum Bearish)")

        # 5. Harga dekat/di atas Bollinger upper band (overbought)
        if bb_upper is not None and current_price >= bb_upper:
            sell_score += 1
            sell_reasons.append(
                f"Harga di atas BB Upper ({_fmt(current_price)} >= {_fmt(bb_upper)})"
            )

        # 6. Volume spike (konfirmasi kekuatan sell)
        if vol_spike:
            sell_score += 1
            sell_reasons.append(
                f"Volume Spike ({current_vol:.2f} >= {VOLUME_SPIKE_MULTIPLIER}x avg)"
            )

        # === Tentukan sinyal ===
        signal = None
        if buy_score >= MIN_BUY_CONFIRMATIONS:
            signal = "BUY"
        elif sell_score >= MIN_SELL_CONFIRMATIONS:
            signal = "SELL"
            reasons = sell_reasons

        # Update previous state
        self.prev_ma_short = ma_short
        self.prev_ma_long = ma_long
        if macd_histogram is not None:
            self.prev_macd_histogram = macd_histogram

        if signal:
            return {
                "signal": signal,
                "pair": self.pair,
                "price": current_price,
                "rsi": rsi,
                "ma_short": ma_short,
                "ma_long": ma_long,
                "macd_line": macd_line,
                "macd_signal": macd_signal,
                "macd_histogram": macd_histogram,
                "bb_upper": bb_upper,
                "bb_middle": bb_middle,
                "bb_lower": bb_lower,
                "volume": current_vol,
                "volume_avg": avg_vol,
                "reasons": reasons,
                "score": buy_score if signal == "BUY" else sell_score,
            }

        return None


def _fmt(value: float) -> str:
    """Format angka pendek untuk alasan sinyal."""
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.8f}"
