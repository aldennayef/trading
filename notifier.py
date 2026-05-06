"""
Telegram Notification Service
"""
import logging
from datetime import datetime, timezone

import aiohttp

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

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


async def notify_buy_signal(signal: dict, tp_price: float, cl_price: float) -> bool:
    """Kirim notifikasi sinyal BELI."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reasons = "\n".join(f"  • {r}" for r in signal["reasons"])

    message = (
        f"🟢 <b>SINYAL BELI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{signal['pair']}</b>\n"
        f"💰 Entry: <b>{_format_price(signal['price'])}</b>\n"
        f"🎯 TP: {_format_price(tp_price)}\n"
        f"🔴 CL: {_format_price(cl_price)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Indikator:\n{reasons}\n"
        f"📉 RSI: {signal['rsi']:.1f}\n"
        f"📊 MA Short: {_format_price(signal['ma_short'])}\n"
        f"📊 MA Long: {_format_price(signal['ma_long'])}\n"
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
    reasons = "\n".join(f"  • {r}" for r in signal["reasons"])

    message = (
        f"⚠️ <b>SINYAL JUAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Pair: <b>{signal['pair']}</b>\n"
        f"💰 Harga: <b>{_format_price(signal['price'])}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 Indikator:\n{reasons}\n"
        f"📊 RSI: {signal['rsi']:.1f}\n"
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
    message = (
        f"🤖 <b>Bot Trading Aktif!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Monitoring: {pairs_str}\n"
        f"⚙️ Strategi: RSI + MA Crossover\n"
        f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return await send_telegram(message)
