#!/usr/bin/env python3
"""
Quick Setup Test Script
Verifies all components are working correctly before running the bot
"""
import sys
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_imports():
    """Test that all required modules can be imported"""
    logger.info("Testing imports...")

    try:
        import pandas
        import numpy
        import pandas_ta
        from binance import Client
        logger.success("✓ Core libraries imported successfully")
        return True
    except ImportError as e:
        logger.error(f"✗ Import error: {e}")
        logger.error("Run: pip install -r requirements.txt")
        return False


def test_config():
    """Test configuration loading"""
    logger.info("Testing configuration...")

    try:
        from config import Config

        if not Config.BINANCE_API_KEY:
            logger.warning("⚠ BINANCE_API_KEY not set in .env")
            logger.warning("  For paper trading, this is OK (will use testnet)")
            logger.warning("  For live trading, you MUST set API keys")
        else:
            logger.success("✓ API keys configured")

        if Config.validate():
            logger.success("✓ Configuration validated successfully")
            return True
        else:
            logger.error("✗ Configuration validation failed")
            return False

    except Exception as e:
        logger.error(f"✗ Configuration error: {e}")
        return False


def test_client():
    """Test Binance client connection"""
    logger.info("Testing Binance client...")

    try:
        from binance_client import ResilientBinanceClient
        from config import Config

        # Try to get BTC price (public API, doesn't require auth)
        client = ResilientBinanceClient("", "", testnet=True)
        price = client.get_symbol_price('BTCUSDT')

        if price:
            logger.success(f"✓ Binance connection working (BTC: ${price:,.2f})")
            return True
        else:
            logger.error("✗ Failed to get price from Binance")
            return False

    except Exception as e:
        logger.error(f"✗ Client error: {e}")
        return False


def test_technical_analysis():
    """Test technical analysis module"""
    logger.info("Testing technical analysis...")

    try:
        from utils.technical_analysis import TechnicalAnalysis
        from binance_client import ResilientBinanceClient

        client = ResilientBinanceClient("", "", testnet=True)
        klines = client.get_historical_klines('BTCUSDT', '5m', limit=100)

        if not klines:
            logger.error("✗ Failed to get klines data")
            return False

        df = TechnicalAnalysis.prepare_dataframe(klines)
        ta = TechnicalAnalysis(df)
        ta.calculate_all_indicators()

        latest = ta.get_latest_values()

        logger.success(f"✓ Technical analysis working (RSI: {latest['rsi']:.1f})")
        return True

    except Exception as e:
        logger.error(f"✗ Technical analysis error: {e}")
        return False


def test_risk_manager():
    """Test risk management module"""
    logger.info("Testing risk manager...")

    try:
        from utils.risk_manager import RiskManager
        from config import Config

        rm = RiskManager(Config.INITIAL_BALANCE)

        # Test position sizing
        size, value = rm.calculate_position_size(
            'BTCUSDT',
            entry_price=50000.0,
            stop_loss_price=49000.0,
            atr=500.0,
            volatility_pct=3.0
        )

        if size > 0 and value > 0:
            logger.success(f"✓ Risk manager working (Position size: {size:.6f} BTC, ${value:.2f})")
            return True
        else:
            logger.error("✗ Risk manager returned invalid values")
            return False

    except Exception as e:
        logger.error(f"✗ Risk manager error: {e}")
        return False


def test_strategies():
    """Test trading strategies"""
    logger.info("Testing strategies...")

    try:
        from strategies.momentum_strategy import MomentumStrategy
        from strategies.mean_reversion_strategy import MeanReversionStrategy
        from config import Config

        # Test momentum strategy
        momentum = MomentumStrategy('BTCUSDT')
        logger.success("✓ Momentum strategy initialized")

        # Test mean reversion strategy
        mean_rev = MeanReversionStrategy('BTCUSDT')
        logger.success("✓ Mean reversion strategy initialized")

        return True

    except Exception as e:
        logger.error(f"✗ Strategy error: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("BINANCE TRADING BOT - SETUP TEST")
    logger.info("="*60 + "\n")

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Binance Client", test_client),
        ("Technical Analysis", test_technical_analysis),
        ("Risk Manager", test_risk_manager),
        ("Strategies", test_strategies),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}")
            results.append((name, False))
        logger.info("")  # Blank line between tests

    # Summary
    logger.info("="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{name:.<30} {status}")

    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")
    logger.info("="*60)

    if passed == total:
        logger.success("\n🎉 All tests passed! Bot is ready to run.")
        logger.info("\nNext steps:")
        logger.info("1. Set your Binance API keys in .env (if not already done)")
        logger.info("2. Review and adjust settings in .env")
        logger.info("3. Start bot: python trading_bot.py")
        logger.info("\nFor live trading: Set TRADING_MODE=live in .env")
        return 0
    else:
        logger.error("\n⚠️  Some tests failed. Please fix the issues before running the bot.")
        logger.info("\nCommon fixes:")
        logger.info("- Install dependencies: pip install -r requirements.txt")
        logger.info("- Copy .env.example to .env: cp .env.example .env")
        logger.info("- Check your internet connection")
        return 1


if __name__ == "__main__":
    sys.exit(main())
