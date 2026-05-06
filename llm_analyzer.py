"""LLM Analyzer — Analisis sinyal trading dengan LLM (OpenAI-compatible)."""
import json
import logging

import aiohttp

from config import LLM_API_KEY, LLM_BASE_URL, LLM_CONFIDENCE_BOOST, LLM_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a professional cryptocurrency technical analyst. "
    "Analyze the given indicators and provide your confidence (0-100) "
    "that the suggested trading signal is correct. "
    "Consider all indicators holistically. "
    "Respond with ONLY a valid JSON object: "
    '{"confidence": <0-100>, "reason": "<brief reason in 1-2 sentences>"}'
)


def _build_prompt(signal: dict) -> str:
    """Bangun prompt analisis dari data sinyal."""
    direction = signal["signal"]
    pair = signal["pair"]
    price = signal["price"]

    lines = [
        f"Pair: {pair}",
        f"Suggested Signal: {direction}",
        f"Current Price: {price}",
        f"Technical Confidence (without LLM): {signal['confidence']:.1f}%",
        "",
        "=== Technical Indicators ===",
    ]

    if signal.get("rsi") is not None:
        lines.append(f"RSI(14): {signal['rsi']:.1f}")
    if signal.get("stoch_k") is not None:
        lines.append(
            f"Stochastic RSI: %K={signal['stoch_k']:.1f}, %D={signal['stoch_d']:.1f}"
        )
    if signal.get("ema_200") is not None:
        lines.append(f"EMA 200: {signal['ema_200']:.2f}")
        pos = "above" if price > signal["ema_200"] else "below"
        lines.append(f"Price is {pos} EMA 200")
    if signal.get("ma_short") is not None:
        lines.append(
            f"MA Short(7): {signal['ma_short']:.2f}, MA Long(25): {signal['ma_long']:.2f}"
        )
    if signal.get("macd_line") is not None:
        lines.append(
            f"MACD: {signal['macd_line']:.4f}, Signal: {signal['macd_signal']:.4f}, "
            f"Histogram: {signal['macd_histogram']:.4f}"
        )
    if signal.get("bb_upper") is not None:
        lines.append(
            f"Bollinger Bands: Upper={signal['bb_upper']:.2f}, "
            f"Lower={signal['bb_lower']:.2f}"
        )
    if signal.get("adx") is not None:
        lines.append(
            f"ADX: {signal['adx']:.1f}, +DI: {signal['plus_di']:.1f}, "
            f"-DI: {signal['minus_di']:.1f}"
        )
    if signal.get("atr") is not None:
        lines.append(f"ATR: {signal['atr']:.4f}")
    if signal.get("volume") is not None and signal.get("volume_avg"):
        ratio = signal["volume"] / signal["volume_avg"]
        lines.append(f"Volume: {signal['volume']:.2f} ({ratio:.1f}x average)")
    if signal.get("fib_ratio") is not None:
        lines.append(
            f"Fibonacci: near level {signal['fib_ratio']:.3f}"
        )

    # Indicator scores breakdown
    scores = signal.get("indicator_scores", {})
    if scores:
        lines.append("")
        lines.append("=== Indicator Scores (0.0-1.0) ===")
        for name, score in sorted(scores.items()):
            lines.append(f"  {name}: {score:.2f}")

    lines.append("")
    lines.append(
        f"Based on the above, how confident are you (0-100) "
        f"that {direction} is the correct action for {pair}?"
    )

    return "\n".join(lines)


async def analyze_with_llm(signal: dict) -> tuple[float, str] | None:
    """
    Kirim data sinyal ke LLM untuk analisis.

    Returns:
        (boost_value, reason) atau None jika gagal.
        boost_value: 0.0 sampai LLM_CONFIDENCE_BOOST.
    """
    if not LLM_API_KEY:
        return None

    prompt = _build_prompt(signal)
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 150,
    }

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{LLM_BASE_URL}/chat/completions"
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("LLM API error %d: %s", resp.status, body[:200])
                    return None

                data = await resp.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON dari response (handle markdown code blocks)
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                result = json.loads(content)
                llm_confidence = float(result.get("confidence", 0))
                reason = str(result.get("reason", ""))

                # Konversi 0-100 ke boost 0-LLM_CONFIDENCE_BOOST
                boost = (llm_confidence / 100.0) * LLM_CONFIDENCE_BOOST
                boost = max(0.0, min(float(LLM_CONFIDENCE_BOOST), boost))

                logger.info(
                    "LLM analysis for %s %s: confidence=%d, boost=%.1f, reason=%s",
                    signal["signal"],
                    signal["pair"],
                    llm_confidence,
                    boost,
                    reason[:80],
                )
                return boost, reason

    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON")
        return None
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("LLM response parsing error: %s", exc)
        return None
    except Exception:
        logger.exception("LLM analysis failed")
        return None
