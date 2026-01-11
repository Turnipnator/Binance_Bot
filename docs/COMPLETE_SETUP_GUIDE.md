# Binance Trading Bot - Complete Setup Guide

> **For Complete Beginners** - This guide assumes you've never set up a server before. Every step is explained in detail.

---

## Table of Contents

1. [What You'll Need Before Starting](#1-what-youll-need-before-starting)
2. [Create Your Contabo VPS Server](#2-create-your-contabo-vps-server)
3. [Connect to Your Server](#3-connect-to-your-server)
4. [Install Required Software](#4-install-required-software)
5. [Get Your Binance API Keys](#5-get-your-binance-api-keys)
6. [Create Your Telegram Bot](#6-create-your-telegram-bot)
7. [Download and Configure the Bot](#7-download-and-configure-the-bot)
8. [Start the Bot](#8-start-the-bot)
9. [Verify Everything Works](#9-verify-everything-works)
10. [Customization Guide](#10-customization-guide)
11. [Daily Operations](#11-daily-operations)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What You'll Need Before Starting

Before we start, make sure you have:

| Item | Why You Need It | Cost |
|------|-----------------|------|
| **Binance Account** | To trade cryptocurrency | Free |
| **Telegram Account** | To control and monitor your bot | Free |
| **Contabo Account** | To run your bot 24/7 on a server | ~$6/month |
| **About 1-2 hours** | To complete this setup | - |

### Important Notes

- **Start with a small amount** - Test with $50-100 first until you're comfortable
- **This is real money** - The bot trades with real funds, so be careful
- **You can stop anytime** - Use the `/stop` command in Telegram to pause trading

---

## 2. Create Your Contabo VPS Server

A VPS (Virtual Private Server) is like a computer that runs 24/7 in a data center. Your bot will live here.

### Step 2.1: Create a Contabo Account

1. Go to [https://contabo.com](https://contabo.com)
2. Click **"Sign Up"** in the top right corner
3. Fill in your email and create a password
4. Verify your email by clicking the link they send you

### Step 2.2: Order Your VPS

1. Go to [https://contabo.com/en/vps/](https://contabo.com/en/vps/)
2. Choose **"VPS S"** (the cheapest option - it's plenty powerful enough)
   - 4 vCPU Cores
   - 8 GB RAM
   - 200 GB SSD
   - ~$6.99/month

3. Click **"Configure"**

### Step 2.3: Configure Your VPS

On the configuration page, select these options:

| Setting | What to Choose |
|---------|----------------|
| **Region** | Choose closest to you (or keep default) |
| **Storage Type** | SSD (default is fine) |
| **Image** | **Ubuntu 22.04** (IMPORTANT!) |
| **Password** | Create a STRONG password and **WRITE IT DOWN** |

> **CRITICAL**: Write down your password! You'll need it to connect to your server.

4. Click **"Next"** and complete payment
5. Wait for your server to be ready (usually 15-60 minutes)
6. You'll receive an email with your server's **IP Address** - save this!

Your email will contain something like:
```
IP Address: 123.456.78.90
Username: root
Password: (the one you created)
```

---

## 3. Connect to Your Server

Now we need to connect to your server. This is like remote-controlling another computer.

### For Windows Users

#### Step 3.1: Download PuTTY

1. Go to [https://www.putty.org/](https://www.putty.org/)
2. Click **"Download PuTTY"**
3. Download the **64-bit MSI installer**
4. Run the installer and click **Next** through all screens

#### Step 3.2: Connect with PuTTY

1. Open **PuTTY** (search for it in your Start menu)
2. In the **"Host Name"** box, type your server's IP address (from the email)
3. Make sure **Port** is `22`
4. Make sure **Connection type** is `SSH`
5. Click **"Open"**

6. If you see a security warning, click **"Accept"**

7. When it says `login as:`, type:
   ```
   root
   ```
   Press Enter

8. When it says `password:`, type your password (you won't see it as you type - this is normal!)
   Press Enter

**You're connected when you see something like:**
```
root@vps123456:~#
```

### For Mac Users

#### Step 3.1: Open Terminal

1. Press `Cmd + Space` to open Spotlight
2. Type `Terminal` and press Enter

#### Step 3.2: Connect via SSH

1. In Terminal, type this command (replace with YOUR IP address):
   ```bash
   ssh root@YOUR_IP_ADDRESS
   ```
   Example: `ssh root@123.456.78.90`

2. Press Enter

3. If asked "Are you sure you want to continue connecting?", type `yes` and press Enter

4. Type your password (you won't see it as you type - this is normal!)

**You're connected when you see something like:**
```
root@vps123456:~#
```

---

## 4. Install Required Software

Now we need to install Docker (the software that runs your bot).

**Copy and paste each command exactly**, then press Enter after each one.

> **Tip**: In PuTTY, right-click pastes. On Mac Terminal, use Cmd+V.

### Step 4.1: Update Your Server

```bash
apt update && apt upgrade -y
```

Wait for it to finish (might take 1-2 minutes). You'll see lots of text scrolling.

### Step 4.2: Install Docker

Copy and paste this entire block:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
```

Wait for it to finish (might take 2-3 minutes).

### Step 4.3: Install Docker Compose

```bash
apt install docker-compose-plugin -y
```

### Step 4.4: Verify Installation

```bash
docker --version
```

You should see something like: `Docker version 24.0.7, build afdd53b`

If you see a version number, Docker is installed correctly!

---

## 5. Get Your Binance API Keys

API keys let your bot trade on your behalf. Think of them like a special password just for the bot.

### Step 5.1: Log into Binance

1. Go to [https://www.binance.com](https://www.binance.com)
2. Log into your account

### Step 5.2: Create API Keys

1. Click your **profile icon** (top right)
2. Click **"API Management"**
3. Click **"Create API"**
4. Select **"System generated"**
5. Give it a label like `TradingBot`
6. Complete the security verification (email code, 2FA, etc.)

### Step 5.3: Configure API Permissions

On the API key page:

1. **Enable** these permissions:
   - [x] Enable Reading
   - [x] Enable Spot & Margin Trading

2. **Keep disabled**:
   - [ ] Enable Withdrawals (NEVER enable this!)
   - [ ] Enable Futures (not needed)

3. For **IP Access Restriction**:
   - Select **"Restrict access to trusted IPs only"**
   - Add your Contabo server's IP address (from your email)
   - This prevents anyone else from using your API keys

4. Click **"Save"**

### Step 5.4: Save Your Keys

You'll see two long strings of letters and numbers:

- **API Key**: `aBcDeFgHiJkLmNoPqRsTuVwXyZ123456...`
- **Secret Key**: `AbCdEfGhIjKlMnOpQrStUvWxYz789012...`

> **CRITICAL**:
> - Copy both keys and save them somewhere safe (like a password manager)
> - The Secret Key is only shown ONCE - if you lose it, you'll need to create new keys
> - NEVER share these keys with anyone!

---

## 6. Create Your Telegram Bot

The Telegram bot lets you control and monitor your trading bot from your phone.

### Step 6.1: Create the Bot

1. Open Telegram on your phone or computer
2. Search for **@BotFather** (the official bot for creating bots)
3. Start a chat with BotFather
4. Send this message:
   ```
   /newbot
   ```

5. BotFather will ask for a **name** - type something like:
   ```
   My Trading Bot
   ```

6. BotFather will ask for a **username** (must end in "bot") - type something like:
   ```
   MyTradingBot_12345_bot
   ```
   (Use numbers to make it unique)

7. BotFather will give you a **token** that looks like:
   ```
   7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

   **Save this token!** You'll need it later.

### Step 6.2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Start a chat and send any message
3. It will reply with your information, including your **ID**:
   ```
   Id: 123456789
   ```

   **Save this ID!** You'll need it later.

### Step 6.3: Start Your Bot

1. Search for your new bot by its username (e.g., @MyTradingBot_12345_bot)
2. Click **"Start"** or send `/start`

This activates the bot so it can send you messages.

---

## 7. Download and Configure the Bot

### Step 7.1: Download the Bot Code

Go back to your server terminal (PuTTY or Mac Terminal) and run:

```bash
cd /opt && git clone https://github.com/YOUR_USERNAME/Binance_Bot.git && cd Binance_Bot
```

> **Note**: Replace `YOUR_USERNAME` with the actual GitHub username where the bot is hosted.

### Step 7.2: Create Your Configuration File

The bot needs a configuration file called `.env`. Let's create it:

```bash
nano .env
```

This opens a text editor. Now paste the following (we'll edit the values):

```bash
# ===========================================
# BINANCE API CONFIGURATION
# ===========================================
BINANCE_API_KEY=paste_your_api_key_here
BINANCE_API_SECRET=paste_your_secret_key_here

# ===========================================
# TELEGRAM CONFIGURATION
# ===========================================
TELEGRAM_BOT_TOKEN=paste_your_telegram_token_here
TELEGRAM_CHAT_ID=paste_your_chat_id_here
ENABLE_TELEGRAM=true

# ===========================================
# TRADING CONFIGURATION
# ===========================================
TRADING_MODE=live
TRADING_PAIRS=BTCUSDT,ETHUSDT,SOLUSDT

# ===========================================
# RISK MANAGEMENT
# ===========================================
INITIAL_BALANCE=350
TARGET_DAILY_PROFIT=50
MAX_DAILY_LOSS=10
RISK_PER_TRADE=0.02
MAX_PORTFOLIO_RISK=0.15

# ===========================================
# STRATEGY SETTINGS
# ===========================================
STRATEGY_ALLOCATION=momentum:100
```

### Step 7.3: Edit the Configuration

Using your arrow keys, move through the file and replace:

1. `paste_your_api_key_here` with your Binance API Key
2. `paste_your_secret_key_here` with your Binance Secret Key
3. `paste_your_telegram_token_here` with your Telegram bot token
4. `paste_your_chat_id_here` with your Telegram chat ID
5. `INITIAL_BALANCE=350` - change 350 to match what you have in Binance (approximately)
6. `TRADING_PAIRS=BTCUSDT,ETHUSDT,SOLUSDT` - adjust if you want different pairs

### Step 7.4: Save the File

1. Press `Ctrl + X` (to exit)
2. Press `Y` (to save)
3. Press `Enter` (to confirm filename)

---

## 8. Start the Bot

### Step 8.1: Build and Start

Run this command:

```bash
docker compose up -d --build
```

This will take 2-5 minutes the first time. Wait for it to finish.

### Step 8.2: Check It's Running

```bash
docker ps
```

You should see something like:
```
CONTAINER ID   IMAGE                     STATUS                    NAMES
abc123def456   binance_bot-binance-bot   Up 30 seconds (healthy)   binance-trading-bot
```

If you see `(healthy)`, your bot is running!

---

## 9. Verify Everything Works

### Step 9.1: Check Telegram

1. Open Telegram
2. Go to your bot chat
3. Send: `/status`

You should receive a message showing your balance and bot status.

### Step 9.2: Check the Logs

```bash
docker logs --tail 50 binance-trading-bot
```

You should see the bot scanning markets and checking for signals.

### Step 9.3: Try Some Commands

In Telegram, try these commands:

| Command | What It Does |
|---------|--------------|
| `/help` | Show all commands |
| `/status` | Show current status and balance |
| `/health` | Quick health check |
| `/positions` | Show open positions |
| `/pnl` | Show profit/loss |

---

## 10. Customization Guide

### 10.1: Changing Trading Pairs

To change which cryptocurrencies the bot trades:

1. Connect to your server
2. Edit the configuration:
   ```bash
   nano /opt/Binance_Bot/.env
   ```
3. Find the line starting with `TRADING_PAIRS=`
4. Edit the pairs (comma-separated, no spaces):
   ```
   TRADING_PAIRS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,ADAUSDT
   ```

   **Available pairs** (examples):
   - Major: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`
   - Altcoins: `SOLUSDT`, `ADAUSDT`, `XRPUSDT`, `AVAXUSDT`
   - Meme coins: `SHIBUSDT`, `BONKUSDT` (higher risk!)

5. Save: `Ctrl+X`, then `Y`, then `Enter`
6. Restart the bot:
   ```bash
   cd /opt/Binance_Bot && docker compose down && docker compose up -d
   ```

### 10.2: Changing Take Profit (TP) and Stop Loss (SL)

The default settings are:
- **Take Profit**: 1.3% (bot sells when price goes up 1.3%)
- **Stop Loss**: 5% trailing (bot sells if price drops 5% from highest point)

To change these:

1. Edit the strategy file:
   ```bash
   nano /opt/Binance_Bot/strategies/momentum_strategy.py
   ```

2. Find these lines near the top:
   ```python
   TAKE_PROFIT_PCT = 1.3    # Take profit at 1.3% gain
   STOP_LOSS_PCT = 5.0      # Stop loss at 5% loss
   ```

3. Change the numbers as desired:
   - Lower TP (e.g., 1.0) = More frequent but smaller wins
   - Higher TP (e.g., 2.0) = Less frequent but larger wins
   - Lower SL (e.g., 3.0) = Less risk but more stop-outs
   - Higher SL (e.g., 7.0) = More room to move but larger potential losses

4. Save and restart the bot

### 10.3: Special Settings for Meme Coins

Meme coins (SHIB, BONK) are more volatile. To add custom settings:

1. Edit your `.env` file:
   ```bash
   nano /opt/Binance_Bot/.env
   ```

2. Add this line:
   ```
   MEME_COINS_CONFIG=SHIBUSDT:3:2,BONKUSDT:3:2
   ```

   Format: `SYMBOL:STOP_LOSS:TAKE_PROFIT`
   - This sets SHIB and BONK to 3% SL and 2% TP

3. Save and restart the bot

### 10.4: Adjusting Risk Per Trade

The bot uses a percentage of your balance per trade.

1. Edit `.env`:
   ```bash
   nano /opt/Binance_Bot/.env
   ```

2. Find `RISK_PER_TRADE=0.02` (2%)
3. Change to desired percentage:
   - `0.01` = 1% (conservative)
   - `0.02` = 2% (default)
   - `0.03` = 3% (aggressive)

4. Save and restart

---

## 11. Daily Operations

### Starting the Bot
```bash
cd /opt/Binance_Bot && docker compose up -d
```

### Stopping the Bot
```bash
cd /opt/Binance_Bot && docker compose down
```

### Restarting the Bot
```bash
cd /opt/Binance_Bot && docker compose restart
```

### Viewing Live Logs
```bash
docker logs -f binance-trading-bot
```
(Press `Ctrl+C` to stop viewing)

### Checking Bot Status
Via Telegram: Send `/status` to your bot

Via Terminal:
```bash
docker ps
```

---

## 12. Troubleshooting

### Problem: Bot keeps restarting

**Solution**: Clear the lock file and restart:
```bash
rm -f /opt/Binance_Bot/data/bot.lock
docker compose restart
```

### Problem: Telegram commands not working

**Solution**: Full restart:
```bash
cd /opt/Binance_Bot
docker compose down
rm -f data/bot.lock
docker compose up -d
```

### Problem: "API Key invalid" error

**Solutions**:
1. Check your API key and secret are correct in `.env`
2. Make sure your server's IP is whitelisted in Binance API settings
3. Check API permissions include "Spot Trading"

### Problem: Bot not making trades

**This is often normal!** The bot only trades when conditions are perfect.

Check the logs:
```bash
docker logs --tail 100 binance-trading-bot | grep -i "momentum"
```

If you see "Momentum score too low", the market conditions aren't right. This is the bot protecting your money!

### Problem: Can't connect to server

1. Check your IP address is correct
2. Check your password
3. Make sure the server is running (check Contabo dashboard)

### Getting Help

If you're stuck:
1. Check the logs: `docker logs --tail 100 binance-trading-bot`
2. Send `/health` in Telegram to check status
3. Restart the bot (see above)

---

## Quick Reference Card

### Essential Commands (run on server)

| Command | What It Does |
|---------|--------------|
| `docker ps` | Check if bot is running |
| `docker logs --tail 50 binance-trading-bot` | View recent logs |
| `docker compose restart` | Restart the bot |
| `docker compose down` | Stop the bot |
| `docker compose up -d` | Start the bot |
| `nano /opt/Binance_Bot/.env` | Edit configuration |

### Telegram Commands

| Command | What It Does |
|---------|--------------|
| `/help` | Show all commands |
| `/status` | Current status and balance |
| `/health` | Quick health check |
| `/positions` | Show open trades |
| `/pnl` | Show profit/loss |
| `/trades` | Recent trade history |
| `/stats` | Lifetime statistics |
| `/stop` | Pause trading |
| `/resume` | Resume trading |
| `/emergency` | Close all positions NOW |

---

*Last updated: January 2026*
