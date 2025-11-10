#!/bin/bash

# Binance Trading Bot - Quick Setup Script
echo "======================================"
echo "  Binance Trading Bot Setup"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "IMPORTANT: Edit .env file and add your Binance API credentials"
    echo "Run: nano .env  (or use your preferred editor)"
fi

# Create logs directory
mkdir -p logs

# Create data directory
mkdir -p data

echo ""
echo "======================================"
echo "  Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your Binance API keys"
echo "   nano .env"
echo ""
echo "2. Verify configuration:"
echo "   python config.py"
echo ""
echo "3. Test individual components:"
echo "   python utils/technical_analysis.py"
echo "   python utils/risk_manager.py"
echo ""
echo "4. Start the bot in paper trading mode:"
echo "   python trading_bot.py"
echo ""
echo "For live trading, change TRADING_MODE=live in .env"
echo ""
echo "Happy trading! 🚀"
