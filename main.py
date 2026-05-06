"""
Crypto Trading Bot - Entry Point

Bot trading cryptocurrency dengan notifikasi Telegram.
Menggunakan indikator RSI + Moving Average Crossover untuk
menghasilkan sinyal BUY, Take Profit, dan Cut Loss.
"""
import asyncio
import logging
import sys
import time

from binance_ws import connect_websocket, fetch_initial_klines
from config import LOG_LEVEL, SIGNAL_COOLDOWN, TRADING_PAIRS
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


async def on_kline_close(pair: str, close_price: float) -> None:
    """Callback saat candle kline close - evaluasi sinyal."""
    strategy = strategies.get(pair)
    if strategy is None:
        return

    strategy.add_price(close_price)

    if not strategy.ready:
        return

    signal = strategy.evaluate()
    if signal is None:
        return

    # Cooldown check
    now = time.time()
    last_time = last_signal_time.get(pair, 0)
    if now - last_time < SIGNAL_COOLDOWN:
        logger.debug("Cooldown active for %s, skip signal", pair)
        return

    if signal["signal"] == "BUY":
        # Jangan buka posisi jika sudah ada
        if position_manager.has_position(pair):
            logger.debug("Sudah ada posisi aktif untuk %s", pair)
            return

        pos = position_manager.open_position(pair, close_price)
        await notify_buy_signal(signal, pos.tp_price, pos.cl_price)
        last_signal_time[pair] = now
        logger.info("BUY signal for %s @ %.8f", pair, close_price)

    elif signal["signal"] == "SELL":
        await notify_sell_signal(signal)
        last_signal_time[pair] = now
        logger.info("SELL signal for %s @ %.8f", pair, close_price)


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

    for pair, closes in zip(TRADING_PAIRS, results):
        pair_upper = pair.upper()
        strategy = TradingStrategy(pair_upper)

        for price in closes:
            strategy.add_price(price)

        strategies[pair_upper] = strategy
        logger.info(
            "%s: loaded %d candles, ready=%s",
            pair_upper, len(closes), strategy.ready
        )


async def handle_telegram_commands() -> None:
    """
    Placeholder untuk Telegram command handler.
    Bisa dikembangkan untuk menerima command /status, /pairs, dll.
    """
    pass


async def main() -> None:
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Crypto Trading Bot Starting...")
    logger.info("Pairs: %s", ", ".join(p.upper() for p in TRADING_PAIRS))
    logger.info("=" * 50)

    # Initialize strategies dengan data historis
    await initialize_strategies()

    # Kirim notifikasi bot started
    await notify_bot_started(TRADING_PAIRS)

    # Tampilkan posisi aktif saat startup
    active_positions = position_manager.get_status()
    if active_positions:
        logger.info("Active positions: %d", len(active_positions))
        await notify_status(active_positions)

    # Jalankan WebSocket
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
