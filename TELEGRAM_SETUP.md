# 📱 Telegram Bot Setup Guide

Control and monitor your trading bot from anywhere using Telegram!

## 🎯 Features

### Remote Control
- **Start/Stop Trading**: Control bot operations remotely
- **Emergency Stop**: Close all positions immediately
- **Resume Trading**: Restart after stopping

### Real-Time Monitoring
- **Position Tracking**: View all open positions with P&L
- **Status Updates**: Get comprehensive bot status
- **Balance Checking**: Check account balances

### P&L Reports
- **Daily P&L**: Today's profit/loss
- **Weekly P&L**: This week's performance
- **Monthly P&L**: This month's results
- **All-Time P&L**: Total performance since start

### Automatic Notifications
- **Trade Opened**: Get notified when positions open
- **Trade Closed**: Know when positions close with P&L
- **Daily Targets**: Alert when profit target is met
- **Daily Limits**: Warning when loss limit is reached
- **Errors**: Notification of any critical errors

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Choose a name for your bot (e.g., "My Trading Bot")
4. Choose a username (must end in 'bot', e.g., "mytrading_bot")
5. **Copy the bot token** - it looks like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-1234567
   ```

### Step 2: Get Your Chat ID

1. Search for `@userinfobot` on Telegram
2. Start a chat and it will show your user ID
3. **Copy your ID** - it's a number like:
   ```
   123456789
   ```

### Step 3: Configure the Bot

Edit your `.env` file:

```bash
# Enable Telegram
ENABLE_TELEGRAM=true

# Add your bot token from BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-1234567

# Add your user ID from @userinfobot
TELEGRAM_CHAT_ID=123456789
```

### Step 4: Install Dependencies

```bash
pip install python-telegram-bot==20.7
```

### Step 5: Start Your Bot!

```bash
python trading_bot.py
```

You should receive a welcome message on Telegram saying the bot has started!

## 📱 Using the Bot

### Available Commands

```
/start - Initialize bot and show welcome message
/status - Get current bot status and performance
/positions - View all open positions
/pnl - P&L reports (daily/weekly/monthly/all-time)
/balance - Check account balance
/stop - Stop trading (keeps positions open)
/resume - Resume trading
/emergency - Emergency stop (closes all positions)
/help - Show help message
```

### Example: Checking Status

1. Open your Telegram bot
2. Send `/status`
3. You'll receive:

```
✅ BOT STATUS: RUNNING

Account Summary:
💰 Balance: $10,450.00
📈 Total P&L: $450.00 (+4.50%)
📊 Daily P&L: $75.00

Risk Metrics:
🔥 Portfolio Heat: 8.5%
📍 Open Positions: 3
⏱️ Runtime: 5h 23m

Performance:
✅ Winning Trades: 18
❌ Losing Trades: 7
📊 Win Rate: 72.0%
🎯 Total Trades: 25

Daily Targets:
🎯 Profit: $75.00 / $50.00 (150%)
🛡️ Loss Limit: 0% used
```

### Example: Viewing Positions

Send `/positions` to see:

```
📊 OPEN POSITIONS

1. BTCUSDT
Entry: $50,000.00
Current: $50,750.00
Size: 0.020000
🟢 P&L: $15.00 (+1.50%)
Stop: $49,250.00
Target: $51,500.00

2. ETHUSDT
Entry: $2,900.00
Current: $2,950.00
Size: 0.500000
🟢 P&L: $25.00 (+1.72%)
Stop: $2,850.00
Target: $3,000.00

Total Unrealized P&L: $40.00
```

### Example: Getting P&L Report

1. Send `/pnl`
2. Choose time period from buttons:
   - 📅 Daily
   - 📊 Weekly
   - 📈 Monthly
   - 🏆 All Time

You'll receive detailed reports with win rates, trade counts, and performance metrics.

## 🔐 Security Features

### Authorized Users Only

Only users whose ID is in `TELEGRAM_CHAT_ID` can control the bot.

**Single User:**
```bash
TELEGRAM_CHAT_ID=123456789
```

**Multiple Users:**
```bash
TELEGRAM_CHAT_ID=123456789,987654321,555666777
```

### Confirmation Required

Dangerous actions require confirmation:
- Stopping the bot shows Yes/No buttons
- Emergency stop requires explicit confirmation
- Prevents accidental commands

### Private Bot

Your bot token should **never be shared**. Only you can interact with your bot.

## 📬 Automatic Notifications

You'll automatically receive notifications for:

### When Trades Open

```
🟢 TRADE OPENED

Symbol: BTCUSDT
Side: BUY
Strategy: Momentum (confidence: 0.75)
Entry: $50,000.00
Size: 0.020000
Stop Loss: $49,250.00
Take Profit: $51,500.00
Risk: $15.00
```

### When Trades Close

```
🎉 TRADE CLOSED

Symbol: BTCUSDT
Reason: Take profit
Entry: $50,000.00
Exit: $51,500.00
P&L: $30.00 (+3.00%)
```

### Daily Target Met

```
🎯 DAILY TARGET ACHIEVED!

Today's Profit: $75.00

Excellent work! 🚀
```

### Daily Loss Limit

```
🛑 DAILY LOSS LIMIT REACHED

Today's Loss: $-30.00

Trading stopped for today.
Will resume tomorrow.
```

## 🎮 Control Examples

### Stopping the Bot

1. Send `/stop`
2. Confirm with "✅ Yes, Stop"
3. Bot stops opening new positions
4. Existing positions remain monitored

### Emergency Stop

1. Send `/emergency`
2. **Confirm carefully** - this closes ALL positions
3. All positions closed at market prices
4. Bot stops trading

**⚠️ Use only in true emergencies!**

### Resuming

1. Send `/resume`
2. Bot resumes normal trading
3. Will start looking for new opportunities

## 🔧 Troubleshooting

### Bot Not Responding

**Check:**
1. Is `ENABLE_TELEGRAM=true` in .env?
2. Is `TELEGRAM_BOT_TOKEN` set correctly?
3. Is your `TELEGRAM_CHAT_ID` correct?
4. Did you install `python-telegram-bot`?

**Test:**
```bash
python telegram_bot.py
```

This runs the Telegram bot standalone for testing.

### Not Receiving Notifications

**Check:**
1. Have you started a chat with your bot?
2. Send `/start` to your bot first
3. Check if bot token is valid
4. Verify user ID matches `TELEGRAM_CHAT_ID`

### "Unauthorized" Message

**Your user ID is not in the authorized list.**

1. Get your correct ID from @userinfobot
2. Add it to `TELEGRAM_CHAT_ID` in .env
3. Restart the trading bot

### Multiple Users Not Working

**Format:**
```bash
# Correct (comma-separated, no spaces)
TELEGRAM_CHAT_ID=123456789,987654321

# Also correct (with spaces - will be trimmed)
TELEGRAM_CHAT_ID=123456789, 987654321, 555666777
```

## 📊 Advanced Tips

### Monitoring from Anywhere

- Add bot to your phone for mobile monitoring
- Check status during the day
- Get real-time trade notifications
- Review performance on the go

### Team Trading

- Add multiple user IDs for team access
- Each member gets notifications
- Anyone can check status
- All members can control bot (use carefully!)

### Notification Management

If notifications are too frequent:
1. Mute the Telegram chat
2. Check status manually with `/status`
3. Unmute when needed

### Regular Checks

Best practice:
- Morning: `/status` to check overnight performance
- Midday: `/positions` to see active trades
- Evening: `/pnl` for daily summary

## 🎯 Example Workflow

**Starting Your Day:**
```
/status    # Check overnight performance
/positions # See what's currently trading
```

**During Trading:**
```
[Automatic notifications arrive as trades happen]
```

**End of Day:**
```
/pnl       # Select "Daily" to see today's results
/balance   # Check current account balance
```

**When Needed:**
```
/stop      # Stop for the weekend
/resume    # Resume Monday morning
```

## ⚠️ Important Notes

### Do's ✅
- Keep your bot token secret
- Use strong API key restrictions
- Test with /start first
- Check status regularly
- Keep authorized users list updated

### Don'ts ❌
- Don't share your bot token
- Don't add unknown users
- Don't use emergency stop unless needed
- Don't ignore error notifications
- Don't forget to /resume after /stop

## 🚀 Next Steps

1. Set up your bot following steps above
2. Send `/start` to test connectivity
3. Try each command to familiarize yourself
4. Start paper trading and monitor via Telegram
5. When comfortable, switch to live trading

## 📞 Getting Help

If you're having issues:

1. **Check Logs:**
   ```bash
   tail -f logs/trading_bot.log
   ```

2. **Test Standalone:**
   ```bash
   python telegram_bot.py
   ```

3. **Verify Config:**
   ```bash
   python config.py
   ```

4. **Common Fixes:**
   - Restart the trading bot
   - Check .env file is saved
   - Verify bot token from BotFather
   - Confirm user ID from @userinfobot

---

**Enjoy remote control of your trading bot! 📱💰**

You can now monitor and manage your bot from anywhere in the world via Telegram!
