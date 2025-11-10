# Binance Trading Bot 🤖💰

A sophisticated, production-ready cryptocurrency trading bot for Binance that implements multiple strategies with advanced risk management.

## 🎯 Project Goals

- **Target Daily Profit**: $50+ per day
- **Max Daily Loss**: $30
- **Multi-Strategy Approach**: Grid Trading (50%), Momentum (30%), Mean Reversion (20%)
- **Advanced Risk Management**: ATR-based stops, dynamic position sizing, portfolio heat monitoring
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 🚀 Features

### 📱 Telegram Bot Integration (NEW!)

**Control and monitor your bot from anywhere!**

- **Remote Control**: Start/stop trading, emergency stop
- **Real-Time Notifications**: Trade opened/closed, profit targets, loss limits
- **Position Tracking**: View all open positions with live P&L
- **Performance Reports**: Daily/weekly/monthly/all-time P&L
- **Status Monitoring**: Check bot status, balance, and metrics
- **Multi-User Support**: Add multiple authorized Telegram users
- **Secure**: Only authorized users can control the bot

**See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for setup guide**

### Trading Strategies

1. **Grid Trading Strategy (50% allocation)**
   - Profits from price oscillations in ranging markets
   - Dynamic grid spacing based on volatility
   - Automatic grid adjustment for price movements
   - Best for: BTC, ETH in sideways markets

2. **Momentum Strategy (30% allocation)**
   - Captures strong trending moves
   - Multi-indicator confirmation (EMA, MACD, RSI, Volume)
   - Trailing stops for profit protection
   - Best for: Strong trending markets

3. **Mean Reversion Strategy (20% allocation)**
   - Exploits oversold/overbought conditions
   - Bollinger Band extremes with RSI/Stochastic confirmation
   - Targets return to mean prices
   - Best for: Volatile but ranging markets

### Risk Management

- **Dynamic Position Sizing**: ATR-based with volatility adjustment
- **Portfolio Heat Monitoring**: Maximum 15% total risk exposure
- **Kelly Criterion**: Optimized position sizing based on win rate
- **Stop Loss**: ATR-based dynamic stops (2.5x ATR default)
- **Take Profit**: Risk-reward ratio of 2:1 minimum
- **Trailing Stops**: Automatic profit protection
- **Daily Limits**: Stop trading at $30 loss, celebrate at $50+ profit

### Technical Analysis

- **Moving Averages**: EMA 20/50/200 for trend identification
- **RSI**: Momentum and overbought/oversold conditions
- **MACD**: Trend changes and momentum confirmation
- **Bollinger Bands**: Volatility and mean reversion signals
- **ATR**: Volatility measurement and stop placement
- **Volume Indicators**: OBV, VWAP, volume ratio for confirmation
- **Stochastic**: Additional overbought/oversold signals

### Trading Pairs

Pre-configured for 10 high-liquidity pairs:
- BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, AVAXUSDT
- NEARUSDT, APTUSDT, SEIUSDT, POLUSDT, ZECUSDT

## 📋 Prerequisites

- Python 3.8 or higher
- Binance account with API keys
- Initial capital (recommended $1,000+ for live trading)

## 🛠️ Installation

### 1. Clone or navigate to the project directory

```bash
cd /Users/paulturner/Binance_Bot
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Binance API credentials:

```bash
# Required
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Trading Mode (paper for testing, live for real trading)
TRADING_MODE=paper

# Initial Balance
INITIAL_BALANCE=10000
```

## 🔑 Getting Binance API Keys

1. Log in to [Binance](https://www.binance.com)
2. Go to Account → API Management
3. Create a new API key
4. **IMPORTANT Security Settings**:
   - ✅ Enable Spot Trading
   - ❌ Disable Futures/Margin if not needed
   - ✅ Enable IP whitelist (highly recommended)
   - ❌ Never enable withdrawals unless absolutely necessary

## 📱 Setting Up Telegram Bot (Optional but Recommended!)

Control your bot from your phone! See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for detailed instructions.

**Quick Setup:**
1. Message `@BotFather` on Telegram → `/newbot` → get your bot token
2. Message `@userinfobot` on Telegram → get your user ID
3. Add to `.env`:
   ```bash
   ENABLE_TELEGRAM=true
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_user_id_here
   ```
4. Start trading bot → you'll get a welcome message on Telegram!

**Features**: Remote control, real-time notifications, P&L reports, position tracking

## 🚦 Quick Start

### Paper Trading (Recommended for testing)

```bash
# Ensure TRADING_MODE=paper in .env
python trading_bot.py
```

### Live Trading (Use with caution)

```bash
# Change TRADING_MODE=live in .env
# Start with small capital
python trading_bot.py
```

## ⚙️ Configuration

Edit `.env` to customize bot behavior:

### Risk Management

```bash
MAX_RISK_PER_TRADE=0.02        # 2% risk per trade
MAX_PORTFOLIO_RISK=0.15        # 15% max total risk
MAX_CONCURRENT_TRADES=5        # Max open positions
```

### Daily Targets

```bash
TARGET_DAILY_PROFIT=50         # Target profit per day
MAX_DAILY_LOSS=30              # Max acceptable loss per day
```

### Strategy Allocation

```bash
GRID_ALLOCATION=0.5            # 50% to grid trading
MOMENTUM_ALLOCATION=0.3        # 30% to momentum
MEAN_REVERSION_ALLOCATION=0.2  # 20% to mean reversion
```

### Technical Indicators

```bash
RSI_PERIOD=14
RSI_OVERSOLD=35
RSI_OVERBOUGHT=70
EMA_FAST=20
EMA_SLOW=50
ATR_PERIOD=14
ATR_STOP_MULTIPLIER=2.5
```

## 📊 Project Structure

```
Binance_Bot/
├── trading_bot.py              # Main bot orchestrator
├── binance_client.py           # Binance API client with error handling
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── CLAUDE.md                   # Strategy documentation
├── README.md                   # This file
│
├── strategies/                 # Trading strategies
│   ├── grid_strategy.py        # Grid trading implementation
│   ├── momentum_strategy.py    # Momentum trading implementation
│   └── mean_reversion_strategy.py  # Mean reversion implementation
│
├── utils/                      # Utility modules
│   ├── technical_analysis.py   # TA indicators and signals
│   └── risk_manager.py         # Risk management system
│
├── logs/                       # Log files (auto-created)
├── data/                       # Data storage (optional)
└── tests/                      # Unit tests (future)
```

## 💡 Usage Examples

### Monitor Performance

The bot automatically logs performance updates every 5 minutes:

```
==============================================================
PERFORMANCE UPDATE
==============================================================
Balance: $10,450.00
Total PnL: $450.00 (4.50%)
Daily PnL: $75.00
Open Positions: 3
Portfolio Heat: 8.5%
Win Rate: 65.0%
Total Trades: 20
==============================================================
```

### View Individual Positions

Check logs for position details:

```
==============================================================
ENTRY SIGNAL: BTCUSDT
Strategy: Momentum (confidence: 0.75)
Entry: $50,000.00
Stop Loss: $49,250.00 (-1.50%)
Take Profit: $51,500.00 (3.00%)
Position Size: 0.020000 (BTC)
Position Value: $1,000.00
Risk: $15.00
==============================================================
```

## 🔍 Testing Strategies

### Test Individual Components

```bash
# Test technical analysis
python utils/technical_analysis.py

# Test risk manager
python utils/risk_manager.py

# Test grid strategy
python strategies/grid_strategy.py

# Test momentum strategy
python strategies/momentum_strategy.py

# Test mean reversion
python strategies/mean_reversion_strategy.py
```

## 📈 Performance Tracking

The bot tracks comprehensive metrics:

- **Total PnL**: Overall profit/loss
- **Daily PnL**: Today's profit/loss
- **Win Rate**: Percentage of winning trades
- **Portfolio Heat**: Current risk exposure
- **Open Positions**: Number of active trades
- **Sharpe Ratio**: Risk-adjusted returns (tracked over time)

## ⚠️ Important Safety Notes

### Before Going Live

1. **Test in Paper Mode**: Run for at least 1-2 weeks
2. **Start Small**: Use only 10-20% of intended capital initially
3. **Monitor Closely**: Check bot performance multiple times daily
4. **Set Alerts**: Configure Telegram/Discord alerts (optional)
5. **Understand Risks**: Crypto trading carries significant risk

### Risk Warnings

- **Never invest more than you can afford to lose**
- **Past performance doesn't guarantee future results**
- **Markets can be irrational and stay irrational**
- **Bot can experience losses despite risk management**
- **API keys should be secured with IP whitelisting**

### Daily Monitoring Checklist

- [ ] Check daily PnL
- [ ] Review open positions
- [ ] Verify portfolio heat is within limits
- [ ] Check for any error messages in logs
- [ ] Confirm API connection is stable
- [ ] Review closed trades for strategy performance

## 🐛 Troubleshooting

### Common Issues

**Bot won't start**
```bash
# Check configuration
python config.py

# Verify API keys
echo $BINANCE_API_KEY
```

**No trades executing**
```bash
# Check if conditions are too strict
# Review logs for rejection reasons
tail -f logs/trading_bot.log
```

**API rate limit errors**
```bash
# Bot has built-in rate limiting
# If persistent, reduce trading frequency
# Check MAX_CONCURRENT_TRADES setting
```

**Connection timeouts**
```bash
# Check internet connection
# Verify Binance API status
# Bot auto-retries with exponential backoff
```

## 📝 Logging

Logs are stored in `logs/trading_bot.log` with different levels:

- **INFO**: General bot operations
- **DEBUG**: Detailed technical analysis
- **WARNING**: Important notices (approaching limits)
- **ERROR**: Failures and exceptions
- **SUCCESS**: Successful trades and profit targets

## 🔄 Updates and Maintenance

### Regular Maintenance

1. **Review performance weekly**: Adjust strategy allocations if needed
2. **Update parameters**: Fine-tune based on market conditions
3. **Check dependencies**: Keep libraries updated
4. **Backup logs**: Archive old logs monthly
5. **Review code**: Stay updated with latest best practices

### Optimizing Performance

- Adjust RSI thresholds for different market conditions
- Modify grid spacing based on volatility
- Change ATR multiplier for tighter/wider stops
- Rebalance strategy allocations based on what's working

## 🤝 Contributing

This is a personal trading bot, but suggestions are welcome:

1. Test changes in paper mode thoroughly
2. Document any modifications
3. Share performance results
4. Respect risk management principles

## 📜 License

This project is for personal use. Use at your own risk.

## 🙏 Acknowledgments

- Strategy insights from CLAUDE.md comprehensive research
- Binance API documentation
- Python trading community
- pandas-ta for technical analysis indicators

## 📞 Support

For issues or questions:

1. Check logs first: `tail -f logs/trading_bot.log`
2. Review configuration: `python config.py`
3. Test components individually
4. Verify API connectivity

## 🎯 Next Steps

After successful paper trading:

1. ✅ Verify consistent profitability over 2+ weeks
2. ✅ Review win rate (target: >55%)
3. ✅ Confirm max drawdown is acceptable
4. ✅ Test with small live capital ($100-500)
5. ✅ Gradually scale up as confidence grows

---

**Remember: Trading cryptocurrencies carries substantial risk. This bot is a tool to assist trading, not a guarantee of profits. Always monitor your bot and never invest more than you can afford to lose.**

**Good luck, and may your profits exceed your expectations! 🚀💰**
