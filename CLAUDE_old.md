# Binance Trading Bot - Claude Instructions

## CRITICAL: Git Workflow

**MANDATORY for ALL code changes:**

1. Commit locally with descriptive message
2. Push to GitHub
3. Sync VPS if changes affect production

See **CLAUDE.local.md** for VPS connection details and commands.

---

## Current Bot Configuration

### Trading Parameters
- **Take Profit**: 1.3% (simple, lock in gains quickly)
- **Stop Loss**: 5% (fixed from entry)
- **Entry Threshold**: 0.60+ momentum score
- **Trend Filter**: Must be BULLISH (not sideways or bearish)

### Risk Limits
- **Daily Loss Limit**: -$50 (trading pauses when hit)
- **Daily Profit Target**: $50+ (no cap)
- **Max Risk Per Trade**: 2%
- **Max Portfolio Risk**: 15%
- **Max Concurrent Positions**: 5
- **Cooldown After Loss**: 20 minutes per symbol

### Trading Pairs
BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, AVAXUSDT, NEARUSDT, APTUSDT, SEIUSDT, ZECUSDT, POLUSDT

---

## Key Files

| File | Purpose |
|------|---------|
| `trading_bot.py` | Main bot loop, position management, TP/SL logic |
| `strategies/momentum_strategy.py` | Entry signals, filters, trend detection |
| `utils/risk_manager.py` | Position sizing, risk checks, position persistence |
| `binance_client.py` | Exchange API wrapper |
| `telegram_bot.py` | Notifications and commands |
| `config.py` | Configuration constants |

### Data Files
- `data/positions.json` - Open positions (survives restarts)
- `data/daily_pnl.json` - Daily P&L tracking

---

## Entry Signal Requirements

For a LONG position to open, ALL must be true:
1. Momentum score >= 0.60
2. Trend is BULLISH (not sideways/bearish)
3. 4H higher timeframe confirms trend
4. Volume > 1.5x average
5. Not in cooldown period
6. Daily loss limit not hit
7. Portfolio heat < 15%

---

## Recent Changes Log

- **Dec 18**: Added position persistence to JSON file
- **Dec 17**: Simplified to 1.3% TP / 5% SL system
- **Dec 17**: Fixed breakeven stop exit price bug
- **Dec 17**: Raised momentum threshold to 0.60, require BULLISH trend
