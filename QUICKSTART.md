# 🚀 Quick Start Guide

Get your Binance trading bot up and running in 5 minutes!

## Step 1: Initial Setup (2 minutes)

```bash
# Navigate to project directory
cd /Users/paulturner/Binance_Bot

# Run automated setup
./setup.sh
```

This will:
- Create virtual environment
- Install all dependencies
- Create `.env` file
- Set up directories

## Step 2: Configure API Keys (1 minute)

Edit the `.env` file:

```bash
nano .env
```

Add your Binance API keys (or leave empty for paper trading):

```bash
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
TRADING_MODE=paper  # Use 'paper' for testing, 'live' for real trading
```

**Don't have API keys?** That's OK! The bot can run in paper mode with testnet credentials.

## Step 3: Test Everything (1 minute)

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run test suite
python test_setup.py
```

You should see all tests pass ✓

## Step 4: Start Trading! (1 minute)

```bash
python trading_bot.py
```

That's it! Your bot is now running. 🎉

## What Happens Now?

The bot will:
1. ✅ Connect to Binance
2. ✅ Analyze 10 trading pairs (BTC, ETH, BNB, SOL, etc.)
3. ✅ Execute trades based on 3 strategies:
   - Grid Trading (50%)
   - Momentum (30%)
   - Mean Reversion (20%)
4. ✅ Manage risk automatically
5. ✅ Stop at $30 loss or celebrate at $50+ profit
6. ✅ Log everything to console and `logs/trading_bot.log`

## Monitoring Your Bot

Watch the live output in terminal:

```
==============================================================
PERFORMANCE UPDATE
==============================================================
Balance: $10,250.00
Total PnL: $250.00 (2.50%)
Daily PnL: $45.00
Open Positions: 2
Portfolio Heat: 6.5%
Win Rate: 68.0%
Total Trades: 12
==============================================================
```

## Quick Configuration Changes

### Change Trading Pairs

Edit `.env`:
```bash
TRADING_PAIRS=BTCUSDT,ETHUSDT,BNBUSDT  # Trade only these
```

### Adjust Risk

Edit `.env`:
```bash
MAX_RISK_PER_TRADE=0.01  # More conservative (1% per trade)
MAX_DAILY_LOSS=20        # Lower daily loss limit
```

### Change Targets

Edit `.env`:
```bash
TARGET_DAILY_PROFIT=100  # Aim for $100/day
MAX_DAILY_LOSS=50        # Accept up to $50 loss
```

## Stopping the Bot

Press `Ctrl+C` in the terminal. The bot will:
1. Close current operations gracefully
2. Display final statistics
3. Save all data

## Paper Trading vs Live Trading

### Paper Trading (Default)
- Uses Binance testnet
- No real money
- Perfect for testing
- Set: `TRADING_MODE=paper`

### Live Trading (Use Carefully!)
- Uses real Binance account
- Real money at risk
- Start small ($100-500)
- Set: `TRADING_MODE=live`

## Common First-Time Issues

**Bot won't start?**
```bash
python config.py  # Check configuration
```

**No trades happening?**
- Bot is waiting for optimal entry signals
- Check logs: `tail -f logs/trading_bot.log`
- Market conditions may not be suitable

**Import errors?**
```bash
pip install -r requirements.txt
```

## Next Steps

After running successfully in paper mode:

1. **Monitor for 1-2 weeks**: Verify consistent profitability
2. **Review performance**: Check win rate and drawdown
3. **Start small in live mode**: $100-500 initial capital
4. **Scale gradually**: Increase as confidence grows

## Getting Help

1. **Check logs**: `tail -f logs/trading_bot.log`
2. **Test components**: `python utils/technical_analysis.py`
3. **Review README**: Full documentation in `README.md`
4. **Check CLAUDE.md**: Strategy details and research

## Pro Tips

- 💡 Run bot on a VPS/cloud for 24/7 operation
- 💡 Set up Telegram alerts (optional, see README)
- 💡 Review performance daily
- 💡 Adjust strategies based on what works
- 💡 Keep a trading journal

## Safety Reminders

⚠️ **Never invest more than you can afford to lose**
⚠️ **Start in paper mode**
⚠️ **Monitor closely when going live**
⚠️ **Use IP whitelisting on Binance**
⚠️ **Never share API keys**

---

**Happy Trading! 🚀💰**

Questions? Check `README.md` for full documentation.
