# Binance Trading Bot

A momentum-based cryptocurrency trading bot for Binance Spot trading with Telegram integration.

## Features

- **Momentum Strategy** - Only trades when market conditions are optimal
- **Conservative Approach** - Designed to prioritize capital preservation
- **Telegram Control** - Monitor and control your bot from your phone
- **Risk Management** - Built-in stop losses, position sizing, and daily limits
- **Backtesting** - Test strategies against historical data
- **Docker Deployment** - Easy setup on any VPS

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/binance-trading-bot.git
   cd binance-trading-bot
   ```

2. **Configure your settings**
   ```bash
   cp .env.example .env
   nano .env  # Edit with your API keys
   ```

3. **Start the bot**
   ```bash
   docker compose up -d --build
   ```

4. **Verify it's running**
   ```bash
   docker ps  # Should show "healthy"
   ```

## Documentation

**New to this?** See the complete setup guide:

- **[Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md)** - Step-by-step instructions for absolute beginners

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | Current status and balance |
| `/health` | Quick health check |
| `/positions` | View open trades |
| `/pnl` | Profit/loss summary |
| `/trades` | Recent trade history |
| `/stats` | Lifetime statistics |
| `/explain` | Plain English status |
| `/stop` | Pause trading |
| `/resume` | Resume trading |
| `/emergency` | Close all positions |
| `/help` | Show all commands |

## Configuration

Edit `.env` to customize:

| Setting | Description | Default |
|---------|-------------|---------|
| `TRADING_PAIRS` | Coins to trade | BTC, ETH, SOL, BNB, AVAX |
| `TRADING_MODE` | `paper` or `live` | paper |
| `INITIAL_BALANCE` | Your USDT balance | 500 |
| `RISK_PER_TRADE` | % per trade | 2% |
| `TARGET_DAILY_PROFIT` | Daily goal (USD) | 25 |
| `MAX_DAILY_LOSS` | Stop trading limit | 20 |

See `.env.example` for all available options with explanations.

## Strategy Details

The bot uses a momentum strategy that only enters trades when:

- **EMA Stack** is bullish (8 > 21 > 50)
- **Momentum score** >= 0.70
- **Volume** >= 1.5x average
- **RSI** between 40-70 (not overbought/oversold)

**Exit conditions:**
- **Take Profit**: 1.3% gain
- **Stop Loss**: 5% trailing stop (follows price up, never down)

The bot is **LONG only** - it doesn't short. This is intentional as crypto markets have a bullish bias over time.

## Requirements

- VPS with Docker (Ubuntu 22.04 recommended)
- Binance account with API keys
- Telegram account
- ~$100+ USDT for trading (start small!)

## Project Structure

```
binance-trading-bot/
├── trading_bot.py          # Main bot orchestrator
├── telegram_bot.py         # Telegram integration
├── binance_client.py       # Binance API wrapper
├── config.py               # Configuration loader
├── strategies/
│   └── momentum_strategy.py  # Trading strategy
├── utils/
│   ├── risk_manager.py     # Position sizing & stops
│   ├── technical_analysis.py # Indicators
│   └── storage_manager.py  # Trade history
├── backtesting/            # Strategy backtesting tools
├── docs/                   # Documentation
├── docker-compose.yml      # Container config
├── Dockerfile              # Build instructions
└── .env.example            # Configuration template
```

## Customization

### Adding/Removing Trading Pairs

Edit `TRADING_PAIRS` in your `.env` file:
```bash
TRADING_PAIRS=BTCUSDT,ETHUSDT,SOLUSDT
```

### Adjusting Take Profit / Stop Loss

For most pairs, edit the strategy file. For meme coins, use the `.env`:
```bash
MEME_COINS_CONFIG=SHIBUSDT:3:2,BONKUSDT:3:2
```
Format: `SYMBOL:STOP_LOSS%:TAKE_PROFIT%`

### Risk Settings

```bash
RISK_PER_TRADE=0.02      # 2% per trade (conservative)
MAX_PORTFOLIO_RISK=0.15  # 15% max exposure
```

## Support

Having issues?

1. Check the [Troubleshooting Guide](docs/COMPLETE_SETUP_GUIDE.md#12-troubleshooting)
2. View logs: `docker logs --tail 100 binance-trading-bot`
3. Send `/health` to your Telegram bot

## Disclaimer

**Trading cryptocurrencies involves significant risk.** This software is provided as-is, with no guarantees of profit. Only trade with money you can afford to lose. Past performance does not guarantee future results.

The authors are not responsible for any financial losses incurred while using this software.

## License

MIT License - See [LICENSE](LICENSE) file for details.
