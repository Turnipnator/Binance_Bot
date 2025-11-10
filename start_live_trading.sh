#!/bin/bash
# Start Live Trading Bot
# This script starts the bot in the background and monitors initial startup

echo "🚀 Starting Binance Trading Bot (LIVE MODE)"
echo "============================================================"
echo "⚠️  WARNING: THIS IS REAL MONEY!"
echo "============================================================"
echo ""

# Activate virtual environment
source venv/bin/activate

# Start bot in background
echo "Starting bot..."
nohup python3 trading_bot.py > /tmp/trading_bot_startup.log 2>&1 &
BOT_PID=$!

echo "✅ Bot started with PID: $BOT_PID"
echo "📱 Check Telegram for notifications!"
echo ""

# Wait a bit for startup
echo "Waiting for bot to initialize..."
sleep 5

# Check if still running
if ps -p $BOT_PID > /dev/null; then
    echo "✅ Bot is running!"
    echo ""
    echo "📊 Monitor Commands:"
    echo "  • Check logs:     tail -f ./logs/trading_bot.log"
    echo "  • Check process:  ps aux | grep trading_bot"
    echo "  • Stop bot:       kill $BOT_PID"
    echo ""
    echo "📱 Telegram Commands:"
    echo "  • /status    - Current bot status"
    echo "  • /positions - Open positions"
    echo "  • /pnl       - Profit/Loss reports"
    echo "  • /stop      - Pause trading"
    echo "  • /emergency - Close all and stop"
    echo ""
    echo "💰 Starting Balance: \$500 USDT"
    echo "🎯 Daily Target: +\$25 (5%)"
    echo "🛑 Daily Limit: -\$15 (3%)"
    echo "🔒 Max Concurrent Trades: 3"
    echo ""
    echo "============================================================"
    echo "🚀 BOT IS LIVE! Watch Telegram for trade notifications!"
    echo "============================================================"
    echo ""
    echo "Bot PID saved to /tmp/trading_bot.pid"
    echo $BOT_PID > /tmp/trading_bot.pid
else
    echo "❌ Bot failed to start! Check logs:"
    echo "   tail -50 /tmp/trading_bot_startup.log"
    exit 1
fi
