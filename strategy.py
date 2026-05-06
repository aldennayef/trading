"""
Strategy Engine - Fibonacci (wajib) + Stochastic RSI + ADX + ATR + EMA 200
                  + RSI + MA + MACD + BB + Volume
"""
import math
from collections import deque

from config import (
    ADX_PERIOD,
    ADX_STRONG_TREND,
    ATR_PERIOD,
    BB_PERIOD,
    BB_STD_DEV,
    EMA_LONG_PERIOD,
    FIB_BUY_LEVELS,
    FIB_LEVELS,
    FIB_SELL_LEVELS,
    FIB_SWING_LOOKBACK,
    FIB_TOLERANCE,
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
    STOCH_RSI_OVERBOUGHT,
    STOCH_RSI_OVERSOLD,
    STOCH_RSI_PERIOD,
    STOCH_RSI_SMOOTH_D,
    STOCH_RSI_SMOOTH_K,
    VOLUME_MA_PERIOD,
    VOLUME_SPIKE_MULTIPLIER,
)


class TradingStrategy:
    """Menghitung indikator teknikal dan menghasilkan sinyal trading."""

    def __init__(self, pair: str):
        self.pair = pair.upper()
        self.closes = deque(maxlen=KLINE_BUFFER_SIZE)
        self.highs = deque(maxlen=KLINE_BUFFER_SIZE)
        self.lows = deque(maxlen=KLINE_BUFFER_SIZE)
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
            VOLUME_MA_PERIOD + 1,
            FIB_SWING_LOOKBACK,
            RSI_PERIOD + STOCH_RSI_PERIOD + STOCH_RSI_SMOOTH_K + STOCH_RSI_SMOOTH_D,
            ADX_PERIOD * 2 + 1,
            ATR_PERIOD + 1,
            EMA_LONG_PERIOD,
        )
        return len(self.closes) >= min_needed

    def add_price(
        self,
        close_price: float,
        volume: float = 0.0,
        high: float | None = None,
        low: float | None = None,
    ) -> None:
        """Tambahkan data candle baru."""
        self.closes.append(close_price)
        self.volumes.append(volume)
        self.highs.append(high if high is not None else close_price)
        self.lows.append(low if low is not None else close_price)

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
    # Indikator: Stochastic RSI
    # =========================================

    def _calculate_rsi_at(self, prices: list[float], end_idx: int) -> float | None:
        """Hitung RSI yang berakhir pada index tertentu."""
        start = end_idx - RSI_PERIOD
        if start < 0:
            return None
        deltas = [prices[i] - prices[i - 1] for i in range(start + 1, end_idx + 1)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains) / RSI_PERIOD if gains else 0
        avg_loss = sum(losses) / RSI_PERIOD if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_stochastic_rsi(self) -> tuple[float | None, float | None]:
        """
        Hitung Stochastic RSI (%K dan %D).

        Returns:
            (%K, %D) atau (None, None).
        """
        prices = list(self.closes)
        needed = RSI_PERIOD + STOCH_RSI_PERIOD + STOCH_RSI_SMOOTH_K + STOCH_RSI_SMOOTH_D
        if len(prices) < needed:
            return None, None

        # Hitung RSI series
        rsi_count = STOCH_RSI_PERIOD + STOCH_RSI_SMOOTH_K + STOCH_RSI_SMOOTH_D
        rsi_series = []
        for i in range(len(prices) - rsi_count, len(prices)):
            rsi_val = self._calculate_rsi_at(prices, i)
            if rsi_val is not None:
                rsi_series.append(rsi_val)

        if len(rsi_series) < STOCH_RSI_PERIOD:
            return None, None

        # Stochastic formula pada RSI
        stoch_raw = []
        for i in range(STOCH_RSI_PERIOD - 1, len(rsi_series)):
            window = rsi_series[i - STOCH_RSI_PERIOD + 1 : i + 1]
            min_rsi = min(window)
            max_rsi = max(window)
            if max_rsi == min_rsi:
                stoch_raw.append(50.0)
            else:
                stoch_raw.append(
                    (rsi_series[i] - min_rsi) / (max_rsi - min_rsi) * 100
                )

        if len(stoch_raw) < STOCH_RSI_SMOOTH_K:
            return None, None

        # %K = SMA of stoch_raw
        k_series = []
        for i in range(STOCH_RSI_SMOOTH_K - 1, len(stoch_raw)):
            k_series.append(
                sum(stoch_raw[i - STOCH_RSI_SMOOTH_K + 1 : i + 1]) / STOCH_RSI_SMOOTH_K
            )

        if len(k_series) < STOCH_RSI_SMOOTH_D:
            return None, None

        # %D = SMA of %K
        d_val = sum(k_series[-STOCH_RSI_SMOOTH_D:]) / STOCH_RSI_SMOOTH_D
        k_val = k_series[-1]

        return k_val, d_val

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

    def calculate_ema_200(self) -> float | None:
        """Hitung EMA 200 (filter trend jangka panjang)."""
        prices = list(self.closes)
        if len(prices) < EMA_LONG_PERIOD:
            return None
        ema_series = self._calculate_ema(prices, EMA_LONG_PERIOD)
        return ema_series[-1] if ema_series else None

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
    # Indikator: ADX (Average Directional Index)
    # =========================================

    def calculate_adx(self) -> tuple[float | None, float | None, float | None]:
        """
        Hitung ADX (Average Directional Index).

        Returns:
            (adx, plus_di, minus_di) atau (None, None, None).
        """
        n = ADX_PERIOD
        highs = list(self.highs)
        lows = list(self.lows)
        closes = list(self.closes)

        if len(closes) < n * 2 + 1:
            return None, None, None

        # True Range, +DM, -DM
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []

        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            tr_list.append(tr)

            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        if len(tr_list) < n * 2:
            return None, None, None

        # Smoothed TR, +DM, -DM (Wilder's smoothing)
        smoothed_tr = sum(tr_list[:n])
        smoothed_plus_dm = sum(plus_dm_list[:n])
        smoothed_minus_dm = sum(minus_dm_list[:n])

        dx_list = []
        for i in range(n, len(tr_list)):
            smoothed_tr = smoothed_tr - smoothed_tr / n + tr_list[i]
            smoothed_plus_dm = smoothed_plus_dm - smoothed_plus_dm / n + plus_dm_list[i]
            smoothed_minus_dm = (
                smoothed_minus_dm - smoothed_minus_dm / n + minus_dm_list[i]
            )

            if smoothed_tr == 0:
                continue

            plus_di = (smoothed_plus_dm / smoothed_tr) * 100
            minus_di = (smoothed_minus_dm / smoothed_tr) * 100

            di_sum = plus_di + minus_di
            if di_sum == 0:
                dx_list.append(0)
            else:
                dx_list.append(abs(plus_di - minus_di) / di_sum * 100)

        if len(dx_list) < n:
            return None, None, None

        # ADX = smoothed average of DX
        adx = sum(dx_list[:n]) / n
        for i in range(n, len(dx_list)):
            adx = (adx * (n - 1) + dx_list[i]) / n

        # Final +DI dan -DI
        if smoothed_tr == 0:
            return None, None, None

        final_plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        final_minus_di = (smoothed_minus_dm / smoothed_tr) * 100

        return adx, final_plus_di, final_minus_di

    # =========================================
    # Indikator: ATR (Average True Range)
    # =========================================

    def calculate_atr(self) -> float | None:
        """
        Hitung ATR (Average True Range).

        Returns:
            ATR value atau None.
        """
        highs = list(self.highs)
        lows = list(self.lows)
        closes = list(self.closes)

        if len(closes) < ATR_PERIOD + 1:
            return None

        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            tr_list.append(tr)

        if len(tr_list) < ATR_PERIOD:
            return None

        # Wilder's smoothing
        atr = sum(tr_list[:ATR_PERIOD]) / ATR_PERIOD
        for i in range(ATR_PERIOD, len(tr_list)):
            atr = (atr * (ATR_PERIOD - 1) + tr_list[i]) / ATR_PERIOD

        return atr

    # =========================================
    # Indikator: Fibonacci Retracement
    # =========================================

    def _find_swing_high(self, prices: list[float]) -> float:
        """Cari swing high (harga tertinggi) dari lookback window."""
        return max(prices[-FIB_SWING_LOOKBACK:])

    def _find_swing_low(self, prices: list[float]) -> float:
        """Cari swing low (harga terendah) dari lookback window."""
        return min(prices[-FIB_SWING_LOOKBACK:])

    def calculate_fibonacci(self) -> dict | None:
        """
        Hitung level Fibonacci Retracement.

        Returns:
            dict dengan swing_high, swing_low, levels, nearest_level,
            nearest_ratio, dan proximity. Atau None jika data kurang.
        """
        if len(self.closes) < FIB_SWING_LOOKBACK:
            return None

        prices = list(self.closes)
        swing_high = self._find_swing_high(prices)
        swing_low = self._find_swing_low(prices)

        if swing_high == swing_low:
            return None

        current_price = prices[-1]
        price_range = swing_high - swing_low

        levels = {}
        for ratio in FIB_LEVELS:
            levels[ratio] = swing_high - price_range * ratio

        nearest_ratio = None
        nearest_level = None
        min_distance = float("inf")

        for ratio, level_price in levels.items():
            distance = abs(current_price - level_price) / current_price
            if distance < min_distance:
                min_distance = distance
                nearest_ratio = ratio
                nearest_level = level_price

        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "levels": levels,
            "nearest_ratio": nearest_ratio,
            "nearest_level": nearest_level,
            "proximity": min_distance,
        }

    def _is_near_fib_level(
        self, current_price: float, fib_data: dict, target_levels: list[float]
    ) -> tuple[bool, float | None, float | None]:
        """
        Cek apakah harga dekat dengan salah satu level Fibonacci target.

        Returns:
            (is_near, nearest_ratio, nearest_level_price)
        """
        levels = fib_data["levels"]
        for ratio in target_levels:
            if ratio not in levels:
                continue
            level_price = levels[ratio]
            distance = abs(current_price - level_price) / current_price
            if distance <= FIB_TOLERANCE:
                return True, ratio, level_price

        return False, None, None

    # =========================================
    # Evaluasi Sinyal
    # =========================================

    def evaluate(self) -> dict | None:
        """
        Evaluasi sinyal trading.

        Filter utama (semua harus terpenuhi):
        1. Fibonacci Retracement — harga di level support/resistance
        2. EMA 200 — harga di atas EMA200 untuk BUY, di bawah untuk SELL
        3. ADX >= 25 — trend harus cukup kuat

        Indikator penguat (butuh min MIN_CONFIRMATIONS):
        1. RSI — oversold/overbought
        2. Stochastic RSI — timing entry
        3. MA Crossover — trend direction
        4. MACD — momentum
        5. Bollinger Bands — volatility
        6. Volume — konfirmasi kekuatan

        Returns:
            dict dengan sinyal atau None jika tidak ada sinyal.
        """
        if not self.ready:
            return None

        # Hitung semua indikator
        rsi = self.calculate_rsi()
        stoch_k, stoch_d = self.calculate_stochastic_rsi()
        ma_short = self.calculate_ma(MA_SHORT_PERIOD)
        ma_long = self.calculate_ma(MA_LONG_PERIOD)
        ema_200 = self.calculate_ema_200()
        macd_line, macd_signal, macd_histogram = self.calculate_macd()
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands()
        current_vol, avg_vol, vol_spike = self.calculate_volume_signal()
        adx, plus_di, minus_di = self.calculate_adx()
        atr = self.calculate_atr()
        fib_data = self.calculate_fibonacci()

        if rsi is None or ma_short is None or ma_long is None:
            return None

        current_price = self.closes[-1]

        # ===================================================
        # Filter 1: Fibonacci (WAJIB)
        # ===================================================
        fib_buy_ok = False
        fib_sell_ok = False
        fib_buy_ratio = None
        fib_buy_level = None
        fib_sell_ratio = None
        fib_sell_level = None

        if fib_data is not None:
            fib_buy_ok, fib_buy_ratio, fib_buy_level = self._is_near_fib_level(
                current_price, fib_data, FIB_BUY_LEVELS
            )
            fib_sell_ok, fib_sell_ratio, fib_sell_level = self._is_near_fib_level(
                current_price, fib_data, FIB_SELL_LEVELS
            )

        # ===================================================
        # Filter 2: EMA 200 (trend jangka panjang)
        # ===================================================
        ema_buy_ok = ema_200 is not None and current_price > ema_200
        ema_sell_ok = ema_200 is not None and current_price < ema_200

        # ===================================================
        # Filter 3: ADX (kekuatan trend)
        # ===================================================
        adx_ok = adx is not None and adx >= ADX_STRONG_TREND

        # === Sinyal BELI ===
        buy_score = 0
        buy_reasons = []

        if fib_buy_ok and ema_buy_ok and adx_ok:
            buy_reasons.append(
                f"Fib {fib_buy_ratio:.3f} Support ({_fmt(fib_buy_level)})"
            )
            buy_reasons.append(
                f"EMA 200: {_fmt(ema_200)} (Harga di atas = Uptrend)"
            )
            buy_reasons.append(f"ADX {adx:.1f} (Trend Kuat >= {ADX_STRONG_TREND})")

            # Stochastic RSI oversold
            if stoch_k is not None and stoch_k < STOCH_RSI_OVERSOLD:
                buy_score += 1
                buy_reasons.append(
                    f"Stoch RSI %K {stoch_k:.1f} (Oversold < {STOCH_RSI_OVERSOLD})"
                )

            # RSI oversold
            if rsi < RSI_OVERSOLD:
                buy_score += 1
                buy_reasons.append(f"RSI {rsi:.1f} (Oversold < {RSI_OVERSOLD})")

            # MA cross up
            if self.prev_ma_short is not None and self.prev_ma_long is not None:
                if ma_short > ma_long and self.prev_ma_short <= self.prev_ma_long:
                    buy_score += 1
                    buy_reasons.append(
                        f"MA Cross Up (MA{MA_SHORT_PERIOD} > MA{MA_LONG_PERIOD})"
                    )

            # Harga di atas MA short
            if current_price > ma_short:
                buy_score += 1
                buy_reasons.append("Harga di atas MA Short (Bullish)")

            # MACD
            macd_buy_counted = False
            if macd_histogram is not None and self.prev_macd_histogram is not None:
                if macd_histogram > 0 and self.prev_macd_histogram <= 0:
                    buy_score += 1
                    buy_reasons.append(
                        f"MACD Bullish Cross (Hist: {macd_histogram:.4f})"
                    )
                    macd_buy_counted = True

            if not macd_buy_counted and macd_line is not None and macd_signal is not None:
                if macd_line > macd_signal:
                    buy_score += 1
                    buy_reasons.append("MACD Line > Signal (Momentum Bullish)")

            # Bollinger Bands
            if bb_lower is not None and current_price <= bb_lower:
                buy_score += 1
                buy_reasons.append(
                    f"Harga di bawah BB Lower ({_fmt(current_price)} <= {_fmt(bb_lower)})"
                )

            # Volume spike
            if vol_spike:
                buy_score += 1
                buy_reasons.append(
                    f"Volume Spike ({current_vol:.2f} >= {VOLUME_SPIKE_MULTIPLIER}x avg)"
                )

        # === Sinyal JUAL ===
        sell_score = 0
        sell_reasons = []

        if fib_sell_ok and ema_sell_ok and adx_ok:
            sell_reasons.append(
                f"Fib {fib_sell_ratio:.3f} Resistance ({_fmt(fib_sell_level)})"
            )
            sell_reasons.append(
                f"EMA 200: {_fmt(ema_200)} (Harga di bawah = Downtrend)"
            )
            sell_reasons.append(f"ADX {adx:.1f} (Trend Kuat >= {ADX_STRONG_TREND})")

            # Stochastic RSI overbought
            if stoch_k is not None and stoch_k > STOCH_RSI_OVERBOUGHT:
                sell_score += 1
                sell_reasons.append(
                    f"Stoch RSI %K {stoch_k:.1f} (Overbought > {STOCH_RSI_OVERBOUGHT})"
                )

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

            # MACD
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

            # Bollinger Bands
            if bb_upper is not None and current_price >= bb_upper:
                sell_score += 1
                sell_reasons.append(
                    f"Harga di atas BB Upper ({_fmt(current_price)} >= {_fmt(bb_upper)})"
                )

            # Volume spike
            if vol_spike:
                sell_score += 1
                sell_reasons.append(
                    f"Volume Spike ({current_vol:.2f} >= {VOLUME_SPIKE_MULTIPLIER}x avg)"
                )

        # === Tentukan sinyal ===
        signal = None
        reasons = []
        if fib_buy_ok and ema_buy_ok and adx_ok and buy_score >= MIN_BUY_CONFIRMATIONS:
            signal = "BUY"
            reasons = buy_reasons
        elif fib_sell_ok and ema_sell_ok and adx_ok and sell_score >= MIN_SELL_CONFIRMATIONS:
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
                "stoch_k": stoch_k,
                "stoch_d": stoch_d,
                "ma_short": ma_short,
                "ma_long": ma_long,
                "ema_200": ema_200,
                "macd_line": macd_line,
                "macd_signal": macd_signal,
                "macd_histogram": macd_histogram,
                "bb_upper": bb_upper,
                "bb_middle": bb_middle,
                "bb_lower": bb_lower,
                "volume": current_vol,
                "volume_avg": avg_vol,
                "adx": adx,
                "plus_di": plus_di,
                "minus_di": minus_di,
                "atr": atr,
                "fib_data": fib_data,
                "fib_ratio": fib_buy_ratio if signal == "BUY" else fib_sell_ratio,
                "fib_level": fib_buy_level if signal == "BUY" else fib_sell_level,
                "reasons": reasons,
                "score": buy_score if signal == "BUY" else sell_score,
            }

        return None


def _fmt(value: float) -> str:
    """Format angka pendek untuk alasan sinyal."""
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.8f}"
