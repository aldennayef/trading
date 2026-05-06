---
name: testing-crypto-bot
description: Test the crypto trading bot end-to-end. Use when verifying strategy engine, WebSocket connectivity, position management, or Telegram notification changes.
---

# Testing the Crypto Trading Bot

## Overview
This is a Python CLI application (no GUI). All testing is shell-based — no screen recording needed.

## Devin Secrets Needed
- `TELEGRAM_BOT_TOKEN` — Telegram bot token from @BotFather (needed for notification testing)
- `TELEGRAM_CHAT_ID` — Telegram chat ID from @userinfobot (needed for notification testing)

Without these secrets, the bot will still run but log warnings instead of sending Telegram messages. Strategy engine and position management can be tested without them.

## Binance API Access

**Important:** The main Binance API (`api.binance.com`, `stream.binance.com`) might be geo-restricted from the test server. If you get a 451 error or a message about restricted locations:

- **REST alternative:** `https://data-api.binance.vision`
- **WebSocket alternative:** `wss://data-stream.binance.vision`

To test with these, temporarily patch `config.py` values in your test scripts:
```python
import config
config.BINANCE_REST_BASE = 'https://data-api.binance.vision'
config.BINANCE_WS_BASE = 'wss://data-stream.binance.vision'
```

Check connectivity first:
```bash
curl -s "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=3" | python3 -m json.tool
```

## Setup
```bash
cd /path/to/trading
pip install -r requirements.txt
```

## Key Test Areas

### 1. Strategy Engine (strategy.py)
- Feed known price series, verify RSI matches manual calculation
- Verify `strategy.ready` requires enough data points (RSI_PERIOD + 1 = 15 and MA_LONG_PERIOD = 25)
- BUY signal needs >= 2 confirmations (RSI < 30, MA cross up, price > MA short)
- Single confirmation should return `None`

### 2. Position Manager (position_manager.py)
- TP triggers at entry * 1.03 (default +3%)
- CL triggers at entry * 0.98 (default -2%)
- Test exact boundary values (e.g., $102.99 should NOT trigger, $103.00 should)
- Verify persistence: open position, create new PositionManager, verify it loads
- Clean up `positions.json` after tests

### 3. Unclosed Candle Fix (binance_ws.py)
- `fetch_initial_klines(pair, limit=N)` should return N-1 entries (last unclosed candle excluded)
- This prevents duplicate data when that candle later closes via WebSocket

### 4. Bot Startup E2E (main.py)
- Run bot with patched endpoints for ~25 seconds, verify:
  - Log shows "Fetched N klines" for each pair
  - Log shows "ready=True" for each pair
  - Log shows "Connected to Binance WebSocket"
  - Telegram warning logged (not crash) when unconfigured
  - `strategy.evaluate()` is called during init to bootstrap `prev_ma` state

## Running the Bot
```bash
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
python main.py
```

## Notes
- Python 3.10+ required (uses `float | None` type hints)
- The bot uses `asyncio` — test scripts should use `asyncio.run()`
- Default pairs: BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT, SHIBUSDT
- For faster testing, reduce `config.TRADING_PAIRS` to 1-2 pairs
