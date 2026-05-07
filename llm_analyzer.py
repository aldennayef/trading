"""LLM Analyzer — Analisis sinyal trading dengan LLM (OpenAI-compatible)."""
import json
import logging
import re

import aiohttp

from config import LLM_API_KEY, LLM_BASE_URL, LLM_CONFIDENCE_BOOST, LLM_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a professional cryptocurrency technical analyst. "
    "Analyze the given indicators and provide your confidence (0-100) "
    "that the suggested trading signal is correct. "
    "Consider all indicators holistically. "
    "You MUST respond with ONLY a JSON object, no other text. "
    "Do NOT include any explanation, thinking, or markdown. "
    "Format: {\"confidence\": <number 0-100>, \"reason\": \"<brief reason>\"}"
)


def _extract_json(text: str) -> dict:
    """Extract JSON dari response LLM, bahkan jika ada teks tambahan."""
    # 1. Coba langsung parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Handle markdown code blocks: ```json ... ``` atau ``` ... ```
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Cari JSON object {...} di dalam teks
    brace_match = re.search(r"\{[^{}]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    # 4. Fallback: cari angka confidence dan teks reason manual
    conf_match = re.search(r"confidence[\w\"'\s:=]+?(\d+)", text, re.IGNORECASE)
    if not conf_match:
        conf_match = re.search(r"(\d+)\s*[/%]?\s*(?:confidence|confident)", text, re.IGNORECASE)
    reason_match = re.search(r"reason[\"'\s:=]+[\"']?(.+?)[\"'\n]", text, re.IGNORECASE)
    if conf_match:
        return {
            "confidence": int(conf_match.group(1)),
            "reason": reason_match.group(1) if reason_match else "",
        }

    raise ValueError(f"Cannot extract JSON from LLM response: {text[:200]}")


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
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
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
                message = data["choices"][0]["message"]

                # DeepSeek thinking models: jawaban bisa di reasoning_content
                content = (message.get("content") or "").strip()
                if not content:
                    content = (message.get("reasoning_content") or "").strip()
                if not content:
                    # Coba field lain yang mungkin digunakan provider
                    content = (message.get("reasoning") or "").strip()

                if not content:
                    logger.warning(
                        "LLM returned empty response for %s %s",
                        signal["pair"], signal["signal"],
                    )
                    return None

                result = _extract_json(content)
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

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM returned invalid JSON: %s", exc)
        return None
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("LLM response parsing error: %s", exc)
        return None
    except Exception:
        logger.exception("LLM analysis failed")
        return None
