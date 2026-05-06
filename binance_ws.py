"""
Binance WebSocket Client - Menerima data harga real-time.
"""
import asyncio
import json
import logging

import aiohttp

from config import BINANCE_REST_BASE, BINANCE_WS_BASE, KLINE_BUFFER_SIZE, KLINE_INTERVAL, TRADING_PAIRS

logger = logging.getLogger(__name__)


async def fetch_initial_klines(
    pair: str, interval: str = KLINE_INTERVAL, limit: int = KLINE_BUFFER_SIZE
) -> list[tuple[float, float]]:
    """
    Fetch data kline historis dari REST API untuk mengisi buffer awal.

    Returns:
        List of (close_price, volume) tuples.
    """
    url = (
        f"{BINANCE_REST_BASE}/api/v3/klines"
        f"?symbol={pair.upper()}&interval={interval}&limit={limit}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error("Gagal fetch klines %s: %d", pair, resp.status)
                    return []
                data = await resp.json()
                # Exclude the last entry (current unclosed candle) to avoid
                # duplicating it when it later closes via WebSocket.
                # candle[4] = close price, candle[5] = volume
                klines = [
                    (float(candle[4]), float(candle[5]))
                    for candle in data[:-1]
                ]
                logger.info("Fetched %d klines for %s", len(klines), pair.upper())
                return klines
    except Exception:
        logger.exception("Error fetching klines for %s", pair)
        return []


def build_stream_url(pairs: list[str], interval: str = KLINE_INTERVAL) -> str:
    """Bangun URL WebSocket untuk multi-stream kline."""
    streams = [f"{pair.lower()}@kline_{interval}" for pair in pairs]
    return f"{BINANCE_WS_BASE}/stream?streams={'/'.join(streams)}"


async def connect_websocket(
    pairs: list[str],
    on_kline_close: object,
    on_price_update: object,
) -> None:
    """
    Konek ke Binance WebSocket dan proses data kline.

    Args:
        pairs: List pair yang dimonitor.
        on_kline_close: Callback async saat candle close (pair, close_price, volume).
        on_price_update: Callback async saat ada update harga (pair, price).
    """
    url = build_stream_url(pairs)
    retry_delay = 5

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                logger.info("Connecting to Binance WebSocket...")
                async with session.ws_connect(url, heartbeat=30) as ws:
                    logger.info("Connected to Binance WebSocket")
                    retry_delay = 5  # Reset retry delay on success

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            stream_data = data.get("data", {})

                            if stream_data.get("e") != "kline":
                                continue

                            kline = stream_data["k"]
                            pair = kline["s"]  # e.g. "BTCUSDT"
                            close_price = float(kline["c"])
                            volume = float(kline["v"])
                            is_closed = kline["x"]  # True jika candle sudah close

                            # Update harga real-time (untuk cek TP/CL)
                            await on_price_update(pair, close_price)

                            # Jika candle sudah close, proses untuk indikator
                            if is_closed:
                                await on_kline_close(pair, close_price, volume)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error("WebSocket error: %s", ws.exception())
                            break

                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.CLOSED,
                        ):
                            logger.warning("WebSocket closed")
                            break

        except aiohttp.ClientError:
            logger.exception("WebSocket connection error")
        except asyncio.CancelledError:
            logger.info("WebSocket task cancelled")
            return
        except Exception:
            logger.exception("Unexpected WebSocket error")

        logger.info("Reconnecting in %d seconds...", retry_delay)
        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 60)
