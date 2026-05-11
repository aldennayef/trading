"""Telegram Notification Service"""
import html
import logging
from datetime import datetime, timezone

import aiohttp

import config
from config import LLM_MODEL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _format_price(price: float) -> str:
    """Format harga sesuai besarnya."""
    if price >= 1:
        return f"${price:,.2f}"
    if price >= 0.01:
        return f"${price:,.4f}"
    return f"${price:,.8f}"


async def send_telegram(message: str) -> bool:
    """Kirim pesan ke Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram belum dikonfigurasi. Pesan: %s", message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.info("Telegram message sent")
                    return True
                body = await resp.text()
                logger.error("Telegram error %d: %s", resp.status, body)
                return False
    except Exception:
        logger.exception("Gagal kirim Telegram")
        return False


def _build_indicator_section(signal: dict) -> str:
    """Bangun bagian detail indikator untuk notifikasi."""
    parts: list[str] = []

    # Fibonacci
    if signal.get("fib_data") is not None:
        fib = signal["fib_data"]
        parts.append(
            f"📐 Fib: {_format_price(fib['swing_low'])} - "
            f"{_format_price(fib['swing_high'])}"
        )
        if signal.get("fib_ratio") is not None:
            parts.append(
                f"📐 Level: {signal['fib_ratio']:.3f} = "
                f"{_format_price(signal.get('fib_level', 0))}"
            )

    # Stochastic RSI
    if signal.get("stoch_k") is not None:
        parts.append(
            f"📊 Stoch RSI: %K {signal['stoch_k']:.1f} | "
            f"%D {signal['stoch_d']:.1f}"
        )

    # RSI
    if signal.get("rsi") is not None:
        parts.append(f"📉 RSI: {signal['rsi']:.1f}")

    # EMA 200
    if signal.get("ema_200") is not None:
        parts.append(f"📊 EMA 200: {_format_price(signal['ema_200'])}")

    # MA
    if signal.get("ma_short") is not None:
        parts.append(f"📊 MA Short: {_format_price(signal['ma_short'])}")
        parts.append(f"📊 MA Long: {_format_price(signal['ma_long'])}")

    # MACD
    if signal.get("macd_line") is not None:
        parts.append(
            f"📊 MACD: {signal['macd_line']:.4f} | "
            f"Signal: {signal['macd_signal']:.4f} | "
            f"Hist: {signal['macd_histogram']:.4f}"
        )

    # BB
    if signal.get("bb_upper") is not None:
        parts.append(
            f"📊 BB: Upper {_format_price(signal['bb_upper'])} | "
            f"Lower {_format_price(signal['bb_lower'])}"
        )

    # Volume
    if signal.get("volume") is not None and signal["volume"]:
        vol_str = f"📊 Volume: {signal['volume']:.2f}"
        if signal.get("volume_avg"):
            ratio = signal["volume"] / signal["volume_avg"]
            vol_str += f" ({ratio:.1f}x avg)"
        parts.append(vol_str)

    # ADX
    if signal.get("adx") is not None:
        parts.append(
            f"📊 ADX: {signal['adx']:.1f} | "
            f"+DI: {signal['plus_di']:.1f} | "
            f"-DI: {signal['minus_di']:.1f}"
        )

    # ATR
    if signal.get("atr") is not None:
        parts.append(f"📊 ATR: {_format_price(signal['atr'])}")

    return "\n".join(parts)


def _build_confidence_section(signal: dict) -> str:
    """Bangun bagian confidence score."""
    confidence = signal.get("confidence", 0)
    parts = [f"🎯 Confidence: <b>{confidence:.1f}%</b> (min {config.MIN_CONFIDENCE:.0f}%)"]

    # LLM status
    llm_status = signal.get("llm_status", "disabled")
    llm_labels = {
        "disabled": "Nonaktif (LLM_API_KEY kosong)",
        "not_needed": "Tidak diperlukan (confidence sudah cukup)",
        "used": "Aktif",
        "error": "Error (auto-skip)",
    }
    status_text = llm_labels.get(llm_status, llm_status)
    parts.append(f"🤖 LLM: {status_text}")

    # LLM boost detail
    llm_boost = signal.get("llm_boost")
    if llm_boost is not None:
        parts.append(f"🤖 LLM Boost: +{llm_boost:.1f}%")
        llm_reason = signal.get("llm_reason", "")
        if llm_reason:
            parts.append(f"🤖 Analisis: {html.escape(llm_reason[:100])}")

    # Indicator scores breakdown
    scores = signal.get("indicator_scores", {})
    if scores:
        score_parts = []
        for name, score in sorted(scores.items(), key=lambda x: -x[1]):
            bar = "█" * int(score * 5) + "░" * (5 - int(score * 5))
            score_parts.append(f"  {bar} {name}: {score:.0%}")
        parts.append("\n".join(score_parts))

    return "\n".join(parts)


async def notify_buy_signal(signal: dict, tp_price: float, cl_price: float) -> bool:
    """Kirim notifikasi sinyal BELI."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reasons = "\n".join(f"  • {html.escape(r)}" for r in signal["reasons"])
    confidence = signal.get("confidence", 0)

    indicator_section = _build_indicator_section(signal)
    confidence_section = _build_confidence_section(signal)

    message = (
        f"🟢 <b>SINYAL BELI</b> (Confidence: {confidence:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{signal['pair']}</b>\n"
        f"💰 Entry: <b>{_format_price(signal['price'])}</b>\n"
        f"🎯 TP: {_format_price(tp_price)} (ATR-based)\n"
        f"🔴 CL: {_format_price(cl_price)} (ATR-based)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Alasan:\n{reasons}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{confidence_section}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{indicator_section}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now}"
    )
    return await send_telegram(message)


async def notify_take_profit(record: dict) -> bool:
    """Kirim notifikasi Take Profit."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = (
        f"🎯 <b>TAKE PROFIT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{record['pair']}</b>\n"
        f"💰 Entry: {_format_price(record['entry_price'])}\n"
        f"💵 Close: <b>{_format_price(record['close_price'])}</b>\n"
        f"📈 PnL: <b>+{record['pnl_percent']:.2f}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now}"
    )
    return await send_telegram(message)


async def notify_cut_loss(record: dict) -> bool:
    """Kirim notifikasi Cut Loss."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = (
        f"🔴 <b>CUT LOSS</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{record['pair']}</b>\n"
        f"💰 Entry: {_format_price(record['entry_price'])}\n"
        f"💵 Close: <b>{_format_price(record['close_price'])}</b>\n"
        f"📉 PnL: <b>{record['pnl_percent']:.2f}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now}"
    )
    return await send_telegram(message)


async def notify_sell_signal(signal: dict) -> bool:
    """Kirim notifikasi sinyal JUAL (peringatan)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reasons = "\n".join(f"  • {html.escape(r)}" for r in signal["reasons"])
    confidence = signal.get("confidence", 0)

    indicator_section = _build_indicator_section(signal)
    confidence_section = _build_confidence_section(signal)

    message = (
        f"⚠️ <b>SINYAL JUAL</b> (Confidence: {confidence:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{signal['pair']}</b>\n"
        f"💰 Harga: <b>{_format_price(signal['price'])}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 Alasan:\n{reasons}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{confidence_section}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{indicator_section}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now}"
    )
    return await send_telegram(message)


async def notify_status(positions: list[dict]) -> bool:
    """Kirim status posisi aktif."""
    if not positions:
        return await send_telegram("📋 <b>Status:</b> Tidak ada posisi aktif.")

    lines = ["📋 <b>POSISI AKTIF</b>\n━━━━━━━━━━━━━━━━━━"]
    for pos in positions:
        lines.append(
            f"\n📊 <b>{pos['pair']}</b>\n"
            f"  Entry: {_format_price(pos['entry_price'])}\n"
            f"  TP: {_format_price(pos['tp_price'])}\n"
            f"  CL: {_format_price(pos['cl_price'])}"
        )
    return await send_telegram("\n".join(lines))


async def notify_bot_started(pairs: list[str]) -> bool:
    """Kirim notifikasi bot sudah running."""
    pairs_str = ", ".join(p.upper().replace("USDT", "/USDT") for p in pairs)
    if config.LLM_ENABLED:
        llm_status = f"Aktif (model: {LLM_MODEL})"
    else:
        llm_status = "Nonaktif (set LLM_API_KEY untuk aktifkan)"
    message = (
        f"🤖 <b>Bot Trading Aktif!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Monitoring: {pairs_str}\n"
        f"⚙️ Strategi: Confidence-Based (10 indikator)\n"
        f"🎯 Min Confidence: {MIN_CONFIDENCE:.0f}%\n"
        f"🤖 LLM: {llm_status}\n"
        f"📊 Indikator:\n"
        f"  • Fibonacci Retracement\n"
        f"  • EMA 200 + ADX + ATR\n"
        f"  • Stochastic RSI + RSI\n"
        f"  • MA Crossover + MACD\n"
        f"  • Bollinger Bands + Volume\n"
        f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return await send_telegram(message)
