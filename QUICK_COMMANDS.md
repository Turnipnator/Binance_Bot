# 🚀 Quick Commands - Live Trading Bot

## 📊 MONITORING LOGS (Mac)

### Watch Live Logs (Recommended):
```bash
tail -f ./logs/trading_bot.log
```
**Press Ctrl+C to exit**

### View Last 50 Lines:
```bash
tail -50 ./logs/trading_bot.log
```

### View Last 100 Lines:
```bash
tail -100 ./logs/trading_bot.log
```

### Search Logs for Trades:
```bash
grep -i "trade\|position\|profit\|loss" ./logs/trading_bot.log | tail -20
```

### Search Logs for Errors:
```bash
grep -i "error\|warning" ./logs/trading_bot.log | tail -20
```

---

## 🤖 BOT CONTROL

### Check if Bot is Running:
```bash
ps aux | grep trading_bot
```

### Stop Bot Gracefully:
```bash
kill $(cat /tmp/trading_bot.pid)
```

### Stop Bot Immediately:
```bash
kill -9 $(cat /tmp/trading_bot.pid)
```

### Restart Bot:
```bash
kill $(cat /tmp/trading_bot.pid)
sleep 2
./start_live_trading.sh
```

---

## 📱 TELEGRAM COMMANDS

Send these to your bot in Telegram:

- `/start` - Welcome message
- `/status` - Current bot status and balance
- `/positions` - View all open positions
- `/pnl` - Profit/Loss reports (daily/weekly/monthly)
- `/balance` - Current account balance
- `/stop` - Pause trading (keeps positions open)
- `/resume` - Resume trading after pause
- `/emergency` - CLOSE ALL positions and stop bot
- `/help` - Show all commands

---

## 🔍 QUICK CHECKS

### Check Account Balance:
```bash
source venv/bin/activate && python test_live_connection.py
```

### View Bot Configuration:
```bash
cat .env | grep -v "^#" | grep -v "^$"
```

### Check Log File Size:
```bash
ls -lh ./logs/trading_bot.log
```

### Check How Long Bot Has Been Running:
```bash
ps -p $(cat /tmp/trading_bot.pid) -o etime=
```

---

## 🚨 EMERGENCY PROCEDURES

### If Bot Won't Stop:
```bash
killall -9 python
```

### If You Need to Close All Positions Manually:
1. Open Telegram and send: `/emergency`
2. Or login to Binance app/website and close manually
3. Then stop the bot: `kill $(cat /tmp/trading_bot.pid)`

### Check for Critical Errors:
```bash
tail -100 ./logs/trading_bot.log | grep -i "critical\|fatal\|emergency"
```

---

## 📈 PERFORMANCE MONITORING

### Today's Trades:
```bash
grep "$(date +%Y-%m-%d)" ./logs/trading_bot.log | grep -i "position opened\|position closed"
```

### Recent Trade Activity (Last Hour):
```bash
tail -500 ./logs/trading_bot.log | grep -i "BUY\|SELL\|profit\|loss"
```

### Check Portfolio Status via Telegram:
Send `/status` to your bot

---

## 🎯 BEST COMMAND FOR YOU

**To watch everything happening in real-time:**
```bash
tail -f ./logs/trading_bot.log
```

This will show you:
- Market analysis for each pair
- Entry/exit signals
- Trades executed
- P&L updates
- Any errors or warnings

**Press Ctrl+C when you want to stop watching**

---

## 📝 NOTES

- Bot PID: `24788` (saved in `/tmp/trading_bot.pid`)
- Logs: `./logs/trading_bot.log`
- Config: `.env`
- Balance: $500 USDT
- Max Trades: 3 concurrent
- Daily Target: +$25
- Daily Limit: -$15

**Bot is currently LIVE and scanning markets!** 🚀
