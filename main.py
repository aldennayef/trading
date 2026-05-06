"""
Crypto Trading Bot - Entry Point

Bot trading cryptocurrency dengan notifikasi Telegram.
Confidence-based scoring (10 indikator) + LLM opsional.
"""
import asyncio
import logging
import sys
import time

from binance_ws import connect_websocket, fetch_initial_klines
from config import (
    ATR_CL_MULTIPLIER,
    ATR_TP_MULTIPLIER,
    CL_PERCENT,
    LLM_ENABLED,
    LOG_LEVEL,
    MIN_CONFIDENCE,
    SIGNAL_COOLDOWN,
    TP_PERCENT,
    TRADING_PAIRS,
)
from llm_analyzer import analyze_with_llm
from notifier import (
    notify_bot_started,
    notify_buy_signal,
    notify_cut_loss,
    notify_sell_signal,
    notify_status,
    notify_take_profit,
)
from position_manager import PositionManager
from strategy import TradingStrategy

# === Logging Setup ===
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

# === Global State ===
strategies: dict[str, TradingStrategy] = {}
position_manager = PositionManager()
last_signal_time: dict[str, float] = {}


async def on_kline_close(
    pair: str, high: float, low: float, close_price: float, volume: float
) -> None:
    """Callback saat candle kline close - evaluasi sinyal."""
    strategy = strategies.get(pair)
    if strategy is None:
        return

    strategy.add_price(close_price, volume, high=high, low=low)

    if not strategy.ready:
        return

    signal = strategy.evaluate()
    if signal is None:
        return

    confidence = signal["confidence"]

    # LLM boost (jika aktif dan confidence sudah cukup tinggi)
    llm_reason = ""
    if LLM_ENABLED and confidence < MIN_CONFIDENCE:
        llm_result = await analyze_with_llm(signal)
        if llm_result is not None:
            boost, llm_reason = llm_result
            confidence += boost
            signal["confidence"] = confidence
            signal["llm_boost"] = boost
            signal["llm_reason"] = llm_reason
            logger.info(
                "LLM boost for %s %s: +%.1f%% → %.1f%%",
                pair, signal["signal"], boost, confidence,
            )

    # Cek apakah confidence sudah cukup
    if confidence < MIN_CONFIDENCE:
        logger.debug(
            "Confidence %.1f%% < %.1f%% for %s %s, skip",
            confidence, MIN_CONFIDENCE, pair, signal["signal"],
        )
        return

    # Cooldown check
    now = time.time()
    last_time = last_signal_time.get(pair, 0)
    if now - last_time < SIGNAL_COOLDOWN:
        logger.debug("Cooldown active for %s, skip signal", pair)
        return

    if signal["signal"] == "BUY":
        if position_manager.has_position(pair):
            logger.debug("Sudah ada posisi aktif untuk %s", pair)
            return

        # ATR-based dynamic TP/CL
        atr = signal.get("atr")
        if atr is not None and close_price > 0:
            tp_pct = (atr * ATR_TP_MULTIPLIER / close_price) * 100
            cl_pct = (atr * ATR_CL_MULTIPLIER / close_price) * 100
        else:
            tp_pct = TP_PERCENT
            cl_pct = CL_PERCENT

        pos = position_manager.open_position(
            pair, close_price, tp_percent=tp_pct, cl_percent=cl_pct
        )
        await notify_buy_signal(signal, pos.tp_price, pos.cl_price)
        last_signal_time[pair] = now
        logger.info(
            "BUY signal for %s @ %.8f (confidence: %.1f%%, TP: %.2f%%, CL: %.2f%%)",
            pair, close_price, confidence, tp_pct, cl_pct,
        )

    elif signal["signal"] == "SELL":
        await notify_sell_signal(signal)
        last_signal_time[pair] = now
        logger.info(
            "SELL signal for %s @ %.8f (confidence: %.1f%%)",
            pair, close_price, confidence,
        )


async def on_price_update(pair: str, current_price: float) -> None:
    """Callback saat ada update harga - cek TP/CL posisi aktif."""
    result = position_manager.check_positions(pair, current_price)
    if result is None:
        return

    if result.get("reason") == "TAKE_PROFIT":
        await notify_take_profit(result)
        logger.info("TP hit for %s @ %.8f (PnL: %.2f%%)",
                     pair, current_price, result["pnl_percent"])

    elif result.get("reason") == "CUT_LOSS":
        await notify_cut_loss(result)
        logger.info("CL hit for %s @ %.8f (PnL: %.2f%%)",
                     pair, current_price, result["pnl_percent"])


async def initialize_strategies() -> None:
    """Initialize strategi dengan data historis."""
    logger.info("Initializing strategies with historical data...")

    tasks = [fetch_initial_klines(pair) for pair in TRADING_PAIRS]
    results = await asyncio.gather(*tasks)

    for pair, klines in zip(TRADING_PAIRS, results):
        pair_upper = pair.upper()
        strategy = TradingStrategy(pair_upper)

        for high, low, close_price, volume in klines:
            strategy.add_price(close_price, volume, high=high, low=low)

        # Bootstrap prev_ma and prev_macd_histogram state
        if strategy.ready:
            strategy.evaluate()

        strategies[pair_upper] = strategy
        logger.info(
            "%s: loaded %d candles, ready=%s",
            pair_upper, len(klines), strategy.ready
        )


async def handle_telegram_commands() -> None:
    """Placeholder untuk Telegram command handler."""
    pass


async def main() -> None:
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Crypto Trading Bot Starting...")
    logger.info("Pairs: %s", ", ".join(p.upper() for p in TRADING_PAIRS))
    logger.info("Strategy: Confidence-Based (10 indikator, min %.0f%%)", MIN_CONFIDENCE)
    if LLM_ENABLED:
        logger.info("LLM: Enabled (boost up to %.0f%%)", 10.0)
    else:
        logger.info("LLM: Disabled (set LLM_API_KEY to enable)")
    logger.info("=" * 50)

    await initialize_strategies()
    await notify_bot_started(TRADING_PAIRS)

    active_positions = position_manager.get_status()
    if active_positions:
        logger.info("Active positions: %d", len(active_positions))
        await notify_status(active_positions)

    logger.info("Starting WebSocket connection...")
    await connect_websocket(
        pairs=TRADING_PAIRS,
        on_kline_close=on_kline_close,
        on_price_update=on_price_update,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
