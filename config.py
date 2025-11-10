"""
Configuration Management for Binance Trading Bot
Loads and validates all configuration from environment variables
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Central configuration class for the trading bot"""

    # Binance API Credentials
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

    # Binance Testnet Credentials (for paper trading)
    BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY', '')
    BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET', '')

    # Trading Mode
    TRADING_MODE = os.getenv('TRADING_MODE', 'paper')  # paper or live

    @classmethod
    def get_api_credentials(cls):
        """Get appropriate API credentials based on trading mode"""
        if cls.TRADING_MODE == 'paper':
            # Use testnet keys for paper trading
            return cls.BINANCE_TESTNET_API_KEY, cls.BINANCE_TESTNET_API_SECRET
        else:
            # Use live keys for live trading
            return cls.BINANCE_API_KEY, cls.BINANCE_API_SECRET

    # Risk Management
    MAX_RISK_PER_TRADE = float(os.getenv('MAX_RISK_PER_TRADE', '0.02'))
    MAX_PORTFOLIO_RISK = float(os.getenv('MAX_PORTFOLIO_RISK', '0.15'))
    INITIAL_BALANCE = float(os.getenv('INITIAL_BALANCE', '10000'))

    # Daily Targets
    TARGET_DAILY_PROFIT = float(os.getenv('TARGET_DAILY_PROFIT', '50'))
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '30'))

    # Trading Pairs
    TRADING_PAIRS = os.getenv(
        'TRADING_PAIRS',
        'BTCUSDT,AVAXUSDT,ETHUSDT,ZECUSDT,BNBUSDT,POLUSDT,APTUSDT,SEIUSDT,NEARUSDT,SOLUSDT'
    ).split(',')

    MAX_CONCURRENT_TRADES = int(os.getenv('MAX_CONCURRENT_TRADES', '5'))

    # Strategy Enables
    ENABLE_GRID_STRATEGY = os.getenv('ENABLE_GRID_STRATEGY', 'true').lower() == 'true'
    ENABLE_MOMENTUM_STRATEGY = os.getenv('ENABLE_MOMENTUM_STRATEGY', 'true').lower() == 'true'
    ENABLE_MEAN_REVERSION = os.getenv('ENABLE_MEAN_REVERSION', 'true').lower() == 'true'

    # Strategy Allocation
    GRID_ALLOCATION = float(os.getenv('GRID_ALLOCATION', '0.5'))
    MOMENTUM_ALLOCATION = float(os.getenv('MOMENTUM_ALLOCATION', '0.3'))
    MEAN_REVERSION_ALLOCATION = float(os.getenv('MEAN_REVERSION_ALLOCATION', '0.2'))

    # Grid Trading Parameters
    GRID_SPACING_BTC = float(os.getenv('GRID_SPACING_BTC', '0.02'))
    GRID_SPACING_ALT = float(os.getenv('GRID_SPACING_ALT', '0.05'))
    GRID_LEVELS = int(os.getenv('GRID_LEVELS', '10'))

    # Technical Indicators
    RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
    RSI_OVERSOLD = float(os.getenv('RSI_OVERSOLD', '35'))
    RSI_OVERBOUGHT = float(os.getenv('RSI_OVERBOUGHT', '70'))
    EMA_FAST = int(os.getenv('EMA_FAST', '20'))
    EMA_SLOW = int(os.getenv('EMA_SLOW', '50'))
    EMA_TREND = int(os.getenv('EMA_TREND', '200'))
    MACD_FAST = int(os.getenv('MACD_FAST', '12'))
    MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
    MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))
    BB_PERIOD = int(os.getenv('BB_PERIOD', '20'))
    BB_STD = float(os.getenv('BB_STD', '2'))
    ATR_PERIOD = int(os.getenv('ATR_PERIOD', '14'))

    # Stop Loss & Take Profit
    ATR_STOP_MULTIPLIER = float(os.getenv('ATR_STOP_MULTIPLIER', '2.5'))
    TRAILING_STOP_ACTIVATION = float(os.getenv('TRAILING_STOP_ACTIVATION', '0.015'))
    TRAILING_STOP_DISTANCE = float(os.getenv('TRAILING_STOP_DISTANCE', '0.01'))
    MIN_RISK_REWARD_RATIO = float(os.getenv('MIN_RISK_REWARD_RATIO', '2.0'))

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
    LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', './logs/trading_bot.log')

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./trading_data.db')

    # Telegram Bot
    ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM', 'false').lower() == 'true'
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    # Parse chat IDs (supports multiple users)
    @classmethod
    def get_telegram_users(cls) -> List[int]:
        """Get list of authorized Telegram user IDs"""
        if not cls.TELEGRAM_CHAT_ID:
            return []
        try:
            return [int(id.strip()) for id in cls.TELEGRAM_CHAT_ID.split(',') if id.strip()]
        except ValueError:
            return []

    # Discord (alternative to Telegram)
    DISCORD_WEBHOOK = os.getenv('DISCORD_WEBHOOK', '')

    @classmethod
    def validate(cls) -> bool:
        """Validate critical configuration parameters"""
        errors = []

        if cls.TRADING_MODE == 'live' and (not cls.BINANCE_API_KEY or not cls.BINANCE_API_SECRET):
            errors.append("BINANCE_API_KEY and BINANCE_API_SECRET required for live trading")

        if cls.TRADING_MODE == 'paper' and (not cls.BINANCE_TESTNET_API_KEY or not cls.BINANCE_TESTNET_API_SECRET):
            errors.append("BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET required for paper trading")

        if cls.MAX_RISK_PER_TRADE > 0.05:
            errors.append("MAX_RISK_PER_TRADE should not exceed 5% (0.05)")

        if cls.MAX_PORTFOLIO_RISK > 0.25:
            errors.append("MAX_PORTFOLIO_RISK should not exceed 25% (0.25)")

        total_allocation = cls.GRID_ALLOCATION + cls.MOMENTUM_ALLOCATION + cls.MEAN_REVERSION_ALLOCATION
        if abs(total_allocation - 1.0) > 0.01:
            errors.append(f"Strategy allocations must sum to 1.0, currently: {total_allocation}")

        if errors:
            for error in errors:
                print(f"CONFIG ERROR: {error}")
            return False

        return True

    @classmethod
    def get_grid_spacing(cls, symbol: str) -> float:
        """Get appropriate grid spacing based on symbol"""
        if symbol in ['BTCUSDT', 'ETHUSDT']:
            return cls.GRID_SPACING_BTC
        return cls.GRID_SPACING_ALT

    @classmethod
    def display_config(cls):
        """Display current configuration (safe - no secrets)"""
        print("\n" + "="*60)
        print("BINANCE TRADING BOT CONFIGURATION")
        print("="*60)
        print(f"Trading Mode: {cls.TRADING_MODE.upper()}")
        print(f"Initial Balance: ${cls.INITIAL_BALANCE:,.2f}")
        print(f"Target Daily Profit: ${cls.TARGET_DAILY_PROFIT:,.2f}")
        print(f"Max Daily Loss: ${cls.MAX_DAILY_LOSS:,.2f}")
        print(f"\nTrading Pairs ({len(cls.TRADING_PAIRS)}):")
        for pair in cls.TRADING_PAIRS:
            print(f"  - {pair}")
        print(f"\nStrategy Allocation:")
        print(f"  Grid Trading: {cls.GRID_ALLOCATION*100:.0f}%")
        print(f"  Momentum: {cls.MOMENTUM_ALLOCATION*100:.0f}%")
        print(f"  Mean Reversion: {cls.MEAN_REVERSION_ALLOCATION*100:.0f}%")
        print(f"\nRisk Management:")
        print(f"  Max Risk Per Trade: {cls.MAX_RISK_PER_TRADE*100:.1f}%")
        print(f"  Max Portfolio Risk: {cls.MAX_PORTFOLIO_RISK*100:.1f}%")
        print(f"  Min Risk:Reward Ratio: 1:{cls.MIN_RISK_REWARD_RATIO}")
        print("="*60 + "\n")


# Validate configuration on import
if __name__ == "__main__":
    if Config.validate():
        print("Configuration validated successfully!")
        Config.display_config()
    else:
        print("Configuration validation failed!")
