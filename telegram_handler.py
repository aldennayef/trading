"""Telegram Bot Handler — Menu interaktif untuk analisis on-demand."""
import asyncio
import html
import logging
from datetime import datetime, timezone

import aiohttp

from binance_ws import fetch_initial_klines
from config import (
    KLINE_BUFFER_SIZE,
    LLM_ENABLED,
    MIN_CONFIDENCE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TRADING_PAIRS,
)
from llm_analyzer import analyze_with_llm
from notifier import _build_confidence_section, _build_indicator_section, _format_price
from strategy import TradingStrategy

logger = logging.getLogger(__name__)

# 1 bulan data = 720 candle 1h (30 hari x 24 jam)
HISTORY_INTERVAL = "1h"
HISTORY_LIMIT = 720

# Track last update_id for polling
_last_update_id = 0


def _pair_label(pair: str) -> str:
    """Format pair untuk label tombol, misal btcusdt -> BTC/USDT."""
    return pair.upper().replace("USDT", "/USDT")


async def _send_message(
    chat_id: str | int, text: str, reply_markup: dict | None = None
) -> bool:
    """Kirim pesan Telegram ke chat_id tertentu."""
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                logger.error("Telegram send error %d: %s", resp.status, body)
                return False
    except Exception:
        logger.exception("Gagal kirim pesan Telegram")
        return False


async def _answer_callback(callback_query_id: str, text: str = "") -> None:
    """Answer callback query agar tombol tidak loading terus."""
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("answerCallbackQuery error %d: %s", resp.status, body)
    except Exception:
        logger.exception("Error answering callback query")


def _build_menu_keyboard() -> dict:
    """Bangun inline keyboard dengan tombol untuk setiap coin."""
    buttons = []
    row: list[dict] = []
    for pair in TRADING_PAIRS:
        label = _pair_label(pair)
        row.append({"text": label, "callback_data": f"analyze:{pair}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return {"inline_keyboard": buttons}


async def _analyze_pair(pair: str) -> dict:
    """
    Fetch 1 bulan data historis dan jalankan strategy engine.

    Returns:
        Dict dengan hasil analisis atau error.
    """
    pair_upper = pair.upper()
    logger.info("Fetching 1-month history for %s...", pair_upper)

    klines = await fetch_initial_klines(
        pair, interval=HISTORY_INTERVAL, limit=HISTORY_LIMIT
    )

    if not klines:
        return {"error": f"Gagal mengambil data historis untuk {pair_upper}"}

    strategy = TradingStrategy(pair_upper)
    for high, low, close_price, volume in klines:
        strategy.add_price(close_price, volume, high=high, low=low)

    if not strategy.ready:
        return {
            "error": f"Data tidak cukup untuk analisis {pair_upper} "
            f"({len(klines)} candle)"
        }

    signal = strategy.evaluate()

    # Get current price from last candle
    last_price = klines[-1][2]  # close price

    if signal is None:
        # No signal — confidence too low for both BUY and SELL
        # Re-evaluate to get raw scores for display
        return {
            "pair": pair_upper,
            "price": last_price,
            "signal": "HOLD",
            "confidence": 0.0,
            "candles": len(klines),
            "reasons": ["Tidak ada sinyal kuat — indikator belum sepakat"],
            "indicator_scores": {},
        }

    # LLM boost if applicable
    if not LLM_ENABLED:
        signal["llm_status"] = "disabled"
    elif signal["confidence"] >= MIN_CONFIDENCE:
        signal["llm_status"] = "not_needed"
    else:
        llm_result = await analyze_with_llm(signal)
        if llm_result is not None:
            boost, llm_reason = llm_result
            signal["confidence"] += boost
            signal["llm_boost"] = boost
            signal["llm_reason"] = llm_reason
            signal["llm_status"] = "used"
        else:
            signal["llm_status"] = "error"

    signal["candles"] = len(klines)
    return signal


def _format_analysis_result(result: dict) -> str:
    """Format hasil analisis menjadi pesan Telegram."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if "error" in result:
        return (
            f"❌ <b>Error Analisis</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{html.escape(result['error'])}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {now}"
        )

    pair = result.get("pair", "???")
    price = result.get("price", 0)
    signal_type = result.get("signal", "HOLD")
    confidence = result.get("confidence", 0)
    candles = result.get("candles", 0)

    # Signal emoji and label
    if signal_type == "BUY":
        emoji = "🟢"
        label = "REKOMENDASI: <b>BUY</b>"
    elif signal_type == "SELL":
        emoji = "🔴"
        label = "REKOMENDASI: <b>SELL</b>"
    else:
        emoji = "⚪"
        label = "REKOMENDASI: <b>HOLD</b>"

    header = (
        f"{emoji} <b>Analisis {_pair_label(pair.lower())}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{pair}</b>\n"
        f"💰 Harga: <b>{_format_price(price)}</b>\n"
        f"📅 Data: {candles} candle (1H, ~30 hari)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{label}\n"
    )

    if signal_type == "HOLD":
        body = (
            f"🎯 Confidence: <b>Di bawah threshold</b>\n"
            f"ℹ️ Tidak ada sinyal kuat BUY atau SELL.\n"
            f"Semua indikator belum memberikan sinyal yang cukup "
            f"kuat (min {MIN_CONFIDENCE:.0f}%).\n"
        )
        return (
            f"{header}"
            f"{body}"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {now}"
        )

    # BUY or SELL with full details
    reasons = result.get("reasons", [])
    reasons_str = "\n".join(f"  • {html.escape(r)}" for r in reasons)

    confidence_section = _build_confidence_section(result)
    indicator_section = _build_indicator_section(result)

    direction = "📈" if signal_type == "BUY" else "📉"

    return (
        f"{header}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{direction} Alasan:\n{reasons_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{confidence_section}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{indicator_section}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now}"
    )


async def _handle_menu_command(chat_id: str | int) -> None:
    """Kirim menu pilihan coin."""
    text = (
        "📊 <b>Pilih Coin untuk Analisis</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Klik tombol di bawah untuk menganalisis coin.\n"
        "Bot akan mengambil data <b>1 bulan</b> ke belakang "
        "dan memberikan rekomendasi BUY/SELL/HOLD.\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    keyboard = _build_menu_keyboard()
    await _send_message(chat_id, text, reply_markup=keyboard)


async def _handle_analyze_callback(
    chat_id: str | int, callback_query_id: str, pair: str
) -> None:
    """Handle klik tombol analisis — fetch data & kirim hasil."""
    await _answer_callback(callback_query_id, f"Menganalisis {pair.upper()}...")

    # Kirim pesan "sedang menganalisis"
    loading_text = (
        f"⏳ <b>Menganalisis {_pair_label(pair)}...</b>\n"
        f"Mengambil data 1 bulan dan menjalankan 10 indikator.\n"
        f"Mohon tunggu beberapa detik..."
    )
    await _send_message(chat_id, loading_text)

    result = await _analyze_pair(pair)
    message = _format_analysis_result(result)
    await _send_message(chat_id, message)

    # Re-send menu for easy next selection
    keyboard = _build_menu_keyboard()
    await _send_message(
        chat_id,
        "📊 Pilih coin lain untuk analisis:",
        reply_markup=keyboard,
    )


async def poll_telegram_updates() -> None:
    """
    Long-polling Telegram updates untuk handle command dan callback.

    Runs forever alongside the WebSocket connection.
    """
    global _last_update_id

    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN kosong, Telegram handler disabled")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    logger.info("Telegram command handler started (polling)")

    while True:
        try:
            params = {
                "offset": _last_update_id + 1,
                "timeout": 30,
                "allowed_updates": ["message", "callback_query"],
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                    if resp.status != 200:
                        logger.error("getUpdates error %d", resp.status)
                        await asyncio.sleep(5)
                        continue
                    data = await resp.json()

            updates = data.get("result", [])
            for update in updates:
                update_id = update["update_id"]
                _last_update_id = max(_last_update_id, update_id)

                # Handle /menu or /analyze command
                message = update.get("message")
                if message:
                    text = message.get("text", "")
                    chat_id = message["chat"]["id"]
                    if text.lower() in ("/menu", "/analyze", "/start"):
                        await _handle_menu_command(chat_id)
                    continue

                # Handle callback query (button click)
                callback = update.get("callback_query")
                if callback:
                    cb_data = callback.get("data", "")
                    chat_id = callback["message"]["chat"]["id"]
                    cb_id = callback["id"]

                    if cb_data.startswith("analyze:"):
                        pair = cb_data.split(":", 1)[1]
                        await _handle_analyze_callback(chat_id, cb_id, pair)

        except asyncio.CancelledError:
            logger.info("Telegram handler cancelled")
            return
        except asyncio.TimeoutError:
            # Normal for long-polling, just continue
            continue
        except Exception:
            logger.exception("Error in Telegram polling")
            await asyncio.sleep(5)
