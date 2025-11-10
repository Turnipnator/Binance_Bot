# Binance Trading Bot - VPS Deployment Guide

## Overview

This guide covers deploying the Binance trading bot to your VPS using Docker, alongside the Enclave bot that's already running at `/Users/paulturner/enclavebot-master`.

## Prerequisites

On your VPS, ensure you have:
- Docker Engine (version 20.10+)
- Docker Compose (version 2.0+)
- Git (for version control)
- At least 512MB free RAM
- At least 2GB free disk space

### Check Prerequisites

```bash
docker --version
docker-compose --version
free -h  # Check available RAM
df -h    # Check disk space
```

### Install Docker (if needed)

```bash
# Update package list
sudo apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Add your user to docker group (optional, avoids using sudo)
sudo usermod -aG docker $USER
newgrp docker
```

## Step 1: Copy Bot to VPS

### Option A: Using rsync (recommended)

From your local machine:

```bash
# Copy entire bot directory to VPS
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude 'logs' --exclude 'data' \
  /Users/paulturner/Binance_Bot/ \
  your-vps-user@your-vps-ip:/home/your-vps-user/Binance_Bot/
```

### Option B: Using Git

```bash
# On VPS, clone from your repository
cd /home/your-vps-user/
git clone your-repo-url Binance_Bot
cd Binance_Bot
```

## Step 2: Configure Environment Variables

```bash
cd /home/your-vps-user/Binance_Bot

# Copy example env file
cp .env.example .env

# Edit with your settings
nano .env
```

### Required Configuration

```bash
# Binance API Credentials (TESTNET for paper trading)
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here

# Trading Mode
TRADING_MODE=paper  # Keep as 'paper' for testnet

# Risk Management
MAX_RISK_PER_TRADE=0.02
MAX_PORTFOLIO_RISK=0.15
INITIAL_BALANCE=350  # Testnet balance

# Daily Limits
TARGET_DAILY_PROFIT=50
MAX_DAILY_LOSS=10

# Trading Pairs
TRADING_PAIRS=BTCUSDT,AVAXUSDT,ETHUSDT,ZECUSDT,BNBUSDT,POLUSDT,APTUSDT,SEIUSDT,NEARUSDT,SOLUSDT
MAX_CONCURRENT_TRADES=5

# Strategy Configuration
ENABLE_MOMENTUM_STRATEGY=true
MOMENTUM_ALLOCATION=0.3
MOMENTUM_THRESHOLD=0.75  # Tightened for quality (top 25% signals only)
VOLUME_THRESHOLD=2.0     # Require 2x volume surge

# Stop Loss & Trailing Stop
ATR_STOP_MULTIPLIER=2.5
TRAILING_STOP_PERCENT=5
TRAILING_STOP_ACTIVATION=0.005

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
ENABLE_TELEGRAM=true

# Logging
LOG_LEVEL=INFO
```

Save and exit (Ctrl+X, then Y, then Enter).

## Step 3: Build Docker Image

```bash
cd /home/your-vps-user/Binance_Bot

# Build the image
docker build -t binance-bot:latest .

# Verify the image was created
docker images | grep binance-bot
```

Expected output:
```
binance-bot   latest   abc123def456   2 minutes ago   250MB
```

## Step 4: Start the Bot

```bash
# Start in detached mode
docker-compose up -d

# Verify container is running
docker-compose ps
```

Expected output:
```
NAME                    STATUS              PORTS
binance-trading-bot     Up 10 seconds
```

## Step 5: Verify Bot is Working

### Check Logs

```bash
# View real-time logs
docker-compose logs -f

# View last 50 lines
docker-compose logs --tail=50

# View logs from specific time
docker-compose logs --since 10m
```

Look for:
```
INFO - Trading bot initialized successfully
INFO - Starting momentum strategy with threshold 0.75
INFO - Telegram notifications enabled
INFO - Bot is now running - Press Ctrl+C to stop
```

### Check Telegram

You should receive a startup message in Telegram:
```
🤖 BOT STARTED
Mode: PAPER
Balance: $350.00
Strategies: Momentum (0.75 threshold, 2.0x volume)
Daily Loss Limit: $10.00
Trailing Stop: 5%
```

### Monitor Performance

```bash
# Check bot health
docker-compose exec binance-bot python -c "import os; print('Healthy' if os.path.exists('data/bot.lock') else 'Not running')"

# View daily performance file
docker-compose exec binance-bot cat data/daily_pnl.json
```

## Managing Multiple Bots (Binance + Enclave)

### Directory Structure

```
/home/your-vps-user/
├── Binance_Bot/          # This bot
│   ├── docker-compose.yml
│   ├── .env
│   └── logs/
└── enclavebot-master/    # Existing Enclave bot
    ├── docker-compose.yml
    ├── .env
    └── logs/
```

### View All Running Containers

```bash
# List all containers
docker ps

# Expected output shows both bots:
# binance-trading-bot
# enclave-trading-bot
```

### Network Isolation

Each bot runs on its own network:
- Binance bot: `trading-network`
- Enclave bot: `enclave-network`

This prevents conflicts and ensures isolation.

### Resource Usage

```bash
# Check resource usage
docker stats

# Expected per bot:
# CPU: 5-15%
# RAM: 100-200MB
# Total: ~300-400MB for both bots
```

## Common Commands

### Start/Stop/Restart

```bash
cd /home/your-vps-user/Binance_Bot

# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Rebuild and restart (after code changes)
docker-compose up -d --build
```

### Logs and Debugging

```bash
# Live logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Logs from last hour
docker-compose logs --since 1h

# Save logs to file
docker-compose logs > bot-logs-$(date +%Y%m%d).txt
```

### Execute Commands Inside Container

```bash
# Open shell inside container
docker-compose exec binance-bot /bin/bash

# Run Python commands
docker-compose exec binance-bot python -c "import sys; print(sys.version)"

# Check environment variables
docker-compose exec binance-bot env | grep TRADING
```

### Update Bot Code

```bash
cd /home/your-vps-user/Binance_Bot

# Pull latest code (if using Git)
git pull

# Rebuild and restart
docker-compose up -d --build

# Verify new code is running
docker-compose logs --tail=20
```

### Backup Data

```bash
# Backup logs and data
tar -czf binance-bot-backup-$(date +%Y%m%d).tar.gz \
  /home/your-vps-user/Binance_Bot/logs \
  /home/your-vps-user/Binance_Bot/data

# Copy to safe location
mv binance-bot-backup-*.tar.gz ~/backups/
```

## Monitoring and Maintenance

### Daily Checks

```bash
# Check bot is running
docker ps | grep binance-bot

# Check today's performance
docker-compose exec binance-bot cat data/daily_pnl.json

# Check recent trades
docker-compose logs --tail=50 | grep "TRADE"
```

### Weekly Maintenance

```bash
# Clean up old logs
find /home/your-vps-user/Binance_Bot/logs -name "*.log" -mtime +7 -delete

# Check disk usage
du -sh /home/your-vps-user/Binance_Bot/

# Update dependencies (if needed)
docker-compose up -d --build
```

### System Health Monitoring

```bash
# Docker health check status
docker inspect binance-trading-bot | grep -A 5 Health

# Container uptime
docker ps --format "table {{.Names}}\t{{.Status}}"

# Resource limits
docker inspect binance-trading-bot | grep -A 10 Resources
```

## Troubleshooting

### Bot Not Starting

```bash
# Check logs for errors
docker-compose logs

# Common issues:
# 1. Missing .env file
cp .env.example .env
nano .env

# 2. Invalid API keys
docker-compose exec binance-bot python -c "import os; print(os.getenv('BINANCE_API_KEY'))"

# 3. Port conflicts
docker-compose down
docker ps -a  # Check no orphaned containers
docker-compose up -d
```

### Bot Stops Trading

```bash
# Check if daily loss limit hit
docker-compose exec binance-bot cat data/daily_pnl.json

# If date is old, restart to reset
docker-compose restart

# Check logs for errors
docker-compose logs --tail=100 | grep -i error
```

### High Memory Usage

```bash
# Check current usage
docker stats binance-trading-bot --no-stream

# Restart to clear memory
docker-compose restart

# Reduce memory limits in docker-compose.yml if needed
nano docker-compose.yml
# Edit: memory: 512M -> 256M
docker-compose up -d
```

### Connection Issues

```bash
# Check network connectivity
docker-compose exec binance-bot ping -c 3 testnet.binance.vision

# Check DNS resolution
docker-compose exec binance-bot nslookup testnet.binance.vision

# Restart networking
docker-compose down
docker-compose up -d
```

### Database/Data Corruption

```bash
# Stop bot
docker-compose down

# Backup current data
cp data/daily_pnl.json data/daily_pnl.json.bak
cp data/positions.json data/positions.json.bak

# Reset data (if needed)
echo '{"date":"'$(date +%Y-%m-%d)'","daily_pnl":0.0,"daily_trades":0,"winning_trades":0,"losing_trades":0,"total_trades":0}' > data/daily_pnl.json

# Restart
docker-compose up -d
```

### View Full Container Details

```bash
# Inspect container
docker inspect binance-trading-bot

# Check environment variables
docker inspect binance-trading-bot | grep -A 50 Env

# Check volume mounts
docker inspect binance-trading-bot | grep -A 10 Mounts
```

## Performance Tuning

### Expected Performance (Paper Trading)

With tightened filters (0.75 momentum, 2.0x volume):
- **Trades per day**: 1-3 (down from 10-20)
- **Win rate**: 40-50%+ (up from 9-16%)
- **Average trade**: -2% to +8%
- **Daily PnL**: -$10 to +$50 target

### Adjust Strategy Parameters

Edit `.env` file:

```bash
nano .env

# For more aggressive trading:
MOMENTUM_THRESHOLD=0.65  # More signals
VOLUME_THRESHOLD=1.5     # Lower volume requirement

# For more conservative trading:
MOMENTUM_THRESHOLD=0.80  # Fewer, higher quality signals
VOLUME_THRESHOLD=2.5     # Require stronger volume surge

# After changes:
docker-compose restart
```

### Monitor Strategy Effectiveness

```bash
# Check win rate over last 24 hours
docker-compose logs --since 24h | grep "TRADE CLOSED" | wc -l

# Calculate simple win rate
docker-compose exec binance-bot python -c "
import json
with open('data/daily_pnl.json') as f:
    data = json.load(f)
    if data['total_trades'] > 0:
        win_rate = (data['winning_trades'] / data['total_trades']) * 100
        print(f'Win Rate: {win_rate:.1f}%')
        print(f'Total Trades: {data[\"total_trades\"]}')
        print(f'Daily PnL: \${data[\"daily_pnl\"]:.2f}')
"
```

## Switching from Paper to Live Trading

**WARNING**: Only switch to live trading after:
1. At least 2 weeks of successful paper trading
2. Consistent positive daily PnL
3. Win rate above 40%
4. Understanding all risks involved

```bash
# Stop bot
docker-compose down

# Edit .env
nano .env

# Change:
TRADING_MODE=live
BINANCE_API_KEY=your_live_api_key
BINANCE_API_SECRET=your_live_api_secret
INITIAL_BALANCE=350  # Your actual balance

# Restart with live trading
docker-compose up -d

# IMMEDIATELY verify correct mode
docker-compose logs --tail=20 | grep "TRADING_MODE"
```

## Security Best Practices

1. **API Keys**: Use read+trade permissions only, NO withdrawals
2. **IP Whitelist**: Whitelist your VPS IP on Binance
3. **Key Rotation**: Rotate API keys monthly
4. **Environment Files**: Never commit `.env` to Git
5. **Firewall**: Configure UFW firewall on VPS
6. **Updates**: Keep Docker and system updated

```bash
# Set up firewall
sudo ufw allow ssh
sudo ufw enable

# Regular updates
sudo apt-get update && sudo apt-get upgrade
docker system prune -a  # Clean unused images
```

## Support and Logs

If issues persist:

1. **Collect logs**: `docker-compose logs > full-logs.txt`
2. **Check daily PnL**: `cat data/daily_pnl.json`
3. **System info**: `docker stats; free -h; df -h`
4. **Bot config**: `cat .env | grep -v SECRET`

## Quick Reference

```bash
# Start bot
cd ~/Binance_Bot && docker-compose up -d

# Stop bot
cd ~/Binance_Bot && docker-compose down

# View logs
cd ~/Binance_Bot && docker-compose logs -f

# Check status
docker ps | grep binance

# Daily PnL
docker-compose exec binance-bot cat data/daily_pnl.json

# Restart
cd ~/Binance_Bot && docker-compose restart
```
