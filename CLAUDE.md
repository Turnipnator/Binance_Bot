> **Common Patterns**: See `~/trading-bot-skill.md` for deployment, Docker, Telegram, and strategy patterns shared across all trading bots.

---

# Binance Trading Bot - Claude Code Instructions

## CRITICAL RULES

1. **DO NOT modify the trading strategy** - The momentum threshold (0.70), trailing TP (after 1.3%), SL (3%), sustained volume filter (vol_min3 >= 1.5x), and LONG-only approach are proven and must not be changed unless explicitly requested.

2. **Always backup before significant changes** - Use the backup commands in CLAUDE.local.md before modifying core logic.

3. **Test on VPS after changes** - Always verify the container is healthy after deployment.

---

## Project Overview

This is a cryptocurrency trading bot for Binance Spot trading. It uses a momentum-based strategy with strict risk management.

### Key Stats
- **Win Rate**: ~80% (backtest verified)
- **Strategy**: Momentum with EMA stack + sustained volume filter
- **Direction**: LONG only (shorts disabled - crypto has bullish bias)

---

## Project Structure

```
Binance_Bot/
├── trading_bot.py          # Main orchestrator - entry point
├── telegram_bot.py         # Telegram integration for monitoring/control
├── binance_client.py       # Binance API wrapper with retry logic
├── config.py               # Configuration from environment variables
├── strategies/
│   └── momentum_strategy.py  # THE strategy - don't touch unless asked
├── utils/
│   ├── risk_manager.py     # Position sizing, portfolio heat, stop losses
│   ├── technical_analysis.py # Indicators (RSI, MACD, Bollinger, etc.)
│   └── storage_manager.py  # Persistent trade history (new)
├── data/                   # Runtime data (persisted via Docker volume)
│   ├── positions.json      # Open positions
│   ├── daily_pnl.json      # Daily P&L tracking
│   ├── trades.json         # Historical trade records
│   ├── daily_stats.json    # Daily aggregated stats
│   └── lifetime_stats.json # All-time statistics
├── docker-compose.yml      # Container configuration
├── Dockerfile              # Build instructions
├── .env                    # Secrets and config (not in git)
└── CLAUDE.local.md         # VPS connection details (not in git)
```

---

## Trading Strategy (DO NOT MODIFY)

### Entry Criteria
- EMA Stack: Bullish trend (EMA 8 > 21 > 50)
- Momentum Score: >= 0.70
- Volume: >= 1.5x average (current candle)
- Sustained Volume: >= 1.5x average (minimum of last 3 candles)
- RSI: 40-70 range (not overbought/oversold)

### Exit Criteria
- Stop Loss: 3% from entry (default, meme coins may differ)
- Take Profit: Trailing after 1.3% - once price reaches +1.3%, trails with 1% stop from highest
- Lets winners run beyond 1.3% on strong trends

### Position Sizing
- Max single position: 20% of balance (~$200 with current balance)
- Volatility adjustment: 0.5x-1.0x based on market conditions
- Kelly factor: Disabled (returns 1.0)

---

## Configuration

### Environment Variables (.env)
```bash
# API Keys
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# Telegram
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# Trading
TRADING_MODE=live          # live or paper
TRADING_PAIRS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,ADAUSDT,...
RISK_PER_TRADE=0.03        # 3% risk per trade
MAX_PORTFOLIO_RISK=0.15    # 15% max portfolio heat
INITIAL_BALANCE=350        # Starting balance for tracking

# Targets
TARGET_DAILY_PROFIT=50
MAX_DAILY_LOSS=10
```

### Key Config Values in Code
- `MOMENTUM_THRESHOLD = 0.70` (in momentum_strategy.py)
- `volume_ratio < 1.5` - current candle volume filter (in momentum_strategy.py)
- `vol_min3 < 1.5` - sustained volume filter, min of last 3 candles (in momentum_strategy.py)
- `DEFAULT_STOP_LOSS_PCT = 3.0` - 3% stop loss (in config.py)
- `DEFAULT_TAKE_PROFIT_PCT = 1.3` - initial TP trigger, then trails (in config.py)
- `TRAILING_STOP_AFTER_TP = 1.0` - 1% trailing stop after TP hit (in trading_bot.py)
- `max_single_position = self.balance * 0.20` (in risk_manager.py)

---

## Deployment Workflow

See `CLAUDE.local.md` for VPS connection details and deployment commands.
This file is gitignored and contains sensitive server information.

### General Workflow
1. Make changes locally
2. Commit and push to GitHub
3. Sync VPS from GitHub
4. Rebuild and restart container
5. Verify container is healthy

---

## Telegram Commands

Current commands available to user:
- `/status` - Bot status, balance, P&L, win rate
- `/positions` - Open positions with live P&L
- `/pnl` - P&L reports (daily/weekly/monthly/all-time)
- `/balance` - Account balance breakdown
- `/stop` - Pause trading (keep positions)
- `/resume` - Resume trading
- `/emergency` - Close all positions immediately
- `/help` - Show commands

### Notifications
Bot automatically sends Telegram notifications for:
- Trade opened (entry price, size, stop loss, take profit)
- Trade closed (P&L, reason)
- Daily target reached
- Daily loss limit hit
- Errors

---

## Persistence Layer

The `StorageManager` class (utils/storage_manager.py) provides persistent storage:

### Trade Recording
Every closed trade is saved to `data/trades.json` with:
- Entry/exit prices and times
- P&L in USDT and percentage
- Duration, exit reason
- Win/loss status

### Statistics
- `daily_stats.json` - Per-day aggregated stats
- `lifetime_stats.json` - All-time win rate, streaks, best/worst trades

### Usage
```python
from utils.storage_manager import get_storage
storage = get_storage()
storage.save_trade({...})
stats = storage.get_lifetime_stats()
```

---

## Common Tasks

### Check why no trades are happening
```bash
# Look for signals close to threshold
docker logs binance-trading-bot 2>&1 | grep 'Momentum score too low: 0\.[5-6]' | tail -20
```
If scores are 0.3-0.5, market is consolidating. If 0.6+, close to triggering.

### Adjust position sizing
Edit `max_single_position` in `utils/risk_manager.py`:
```python
max_single_position = self.balance * 0.20  # 20% = ~$200 with $1000 balance
```

### Check live balance
```bash
docker logs binance-trading-bot 2>&1 | grep 'Balance:' | tail -3
```

### View open positions
```bash
cat /opt/Binance_Bot/data/positions.json
```

---

## Docker Configuration

### Logging (prevents disk fill)
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "5"
```
Max 50MB of logs retained.

### Health Check
Container is considered healthy if `data/bot.lock` exists (bot is running).

### Data Persistence
The `data/` directory is mounted as a volume - survives container rebuilds.

---

## Other Bots

For reference, other bots use similar patterns:
- **Enclave Bot**: TypeScript, similar strategy, Enclave exchange
- **Hyperliquid Bot**: TypeScript, wallet signing
- **Gold Bot**: Oanda forex

Each has its own container and doesn't interfere with others.

---

## Troubleshooting

### "Bot already running" error (COMMON)
This happens frequently after container rebuilds. **Always clear the lock file when redeploying:**
```bash
# On VPS - standard redeploy with lock file cleanup:
cd /opt/Binance_Bot && docker compose down && rm -f data/bot.lock && docker compose up -d

# If container is already running but showing lock errors:
rm -f data/bot.lock
docker compose restart
```

### Container keeps restarting
Check logs for the actual error:
```bash
docker logs --tail 100 binance-trading-bot
```

### API errors
Usually rate limiting or connection issues. The bot has built-in retry logic with exponential backoff.

### Balance not updating
The bot syncs balance from Binance periodically. Force sync by restarting or wait for next cycle.

---

## Future Enhancements (Planned)

### Phase 2: Enhanced Telegram Commands
- `/trades` - Show recent trade history
- `/stats` - Comprehensive lifetime statistics
- `/winners` / `/losers` - Filter by outcome
- `/export` - Download trade history as CSV
- `/explain` - Plain English status for non-technical users
- `/health` - Simple health check with recommendations

See `TELEGRAM_UX_ENHANCEMENT_SPEC.md` for full specification.
