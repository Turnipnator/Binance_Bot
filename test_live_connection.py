#!/usr/bin/env python3
"""
Test Live Binance Connection
Verifies API keys work and checks account balance before live trading
"""
import sys
from loguru import logger
from config import Config
from binance_client import ResilientBinanceClient

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

def test_connection():
    """Test Binance API connection and permissions"""

    logger.info("="*60)
    logger.info("TESTING LIVE BINANCE CONNECTION")
    logger.info("="*60)

    if Config.TRADING_MODE != 'live':
        logger.error("❌ Trading mode is not set to 'live'")
        logger.error(f"   Current mode: {Config.TRADING_MODE}")
        return False

    logger.info(f"✅ Trading mode: {Config.TRADING_MODE}")

    # Initialize client
    try:
        client = ResilientBinanceClient(
            Config.BINANCE_API_KEY,
            Config.BINANCE_API_SECRET,
            testnet=False  # LIVE MODE
        )
        logger.success("✅ Client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize client: {e}")
        return False

    # Test 1: Server time sync
    logger.info("\n[1/5] Testing server time sync...")
    try:
        server_time = client.client.get_server_time()
        logger.success(f"✅ Server time: {server_time}")
    except Exception as e:
        logger.error(f"❌ Server time sync failed: {e}")
        return False

    # Test 2: Account info
    logger.info("\n[2/5] Fetching account info...")
    try:
        account = client.client.get_account()
        logger.success(f"✅ Account access OK")
        logger.info(f"   Can Trade: {account['canTrade']}")
        logger.info(f"   Can Withdraw: {account['canWithdraw']}")
        logger.info(f"   Can Deposit: {account['canDeposit']}")

        if not account['canTrade']:
            logger.error("❌ API key cannot trade! Enable 'Spot Trading' permission.")
            return False

        if account['canWithdraw']:
            logger.warning("⚠️  API key CAN WITHDRAW! This is dangerous.")
            logger.warning("   Recommended: Disable withdrawal permissions for safety")
    except Exception as e:
        logger.error(f"❌ Cannot access account: {e}")
        logger.error("   Check API key permissions:")
        logger.error("   - Enable 'Reading'")
        logger.error("   - Enable 'Spot Trading'")
        logger.error("   - DISABLE 'Withdrawals'")
        return False

    # Test 3: Get balances
    logger.info("\n[3/5] Checking account balances...")
    try:
        balances = {b['asset']: float(b['free']) for b in account['balances'] if float(b['free']) > 0}

        if not balances:
            logger.error("❌ No funds in account!")
            return False

        logger.success(f"✅ Found {len(balances)} assets with balance")

        # Show USDT balance
        usdt_balance = balances.get('USDT', 0)
        logger.info(f"\n   💰 USDT Balance: ${usdt_balance:,.2f}")

        if usdt_balance < 100:
            logger.warning(f"⚠️  USDT balance is low: ${usdt_balance:.2f}")
            logger.warning(f"   Configured initial balance: ${Config.INITIAL_BALANCE}")
            logger.warning("   You may not have enough to trade.")

        # Show other significant balances
        for asset, amount in sorted(balances.items(), key=lambda x: x[1], reverse=True)[:5]:
            if asset != 'USDT' and amount > 0:
                logger.info(f"   {asset}: {amount:.6f}")

    except Exception as e:
        logger.error(f"❌ Cannot get balances: {e}")
        return False

    # Test 4: Get market data
    logger.info("\n[4/5] Testing market data access...")
    try:
        btc_price = client.get_symbol_price('BTCUSDT')
        eth_price = client.get_symbol_price('ETHUSDT')

        if btc_price and eth_price:
            logger.success(f"✅ Market data OK")
            logger.info(f"   BTC: ${btc_price:,.2f}")
            logger.info(f"   ETH: ${eth_price:,.2f}")
        else:
            logger.error("❌ Failed to get market data")
            return False
    except Exception as e:
        logger.error(f"❌ Market data error: {e}")
        return False

    # Test 5: Trading pair filters
    logger.info("\n[5/5] Verifying trading pairs...")
    try:
        verified_pairs = []
        for symbol in Config.TRADING_PAIRS:
            try:
                price = client.get_symbol_price(symbol)
                if price:
                    verified_pairs.append(symbol)
                    logger.info(f"   ✅ {symbol}: ${price:,.4f}")
                else:
                    logger.warning(f"   ⚠️  {symbol}: No price data")
            except Exception as e:
                logger.error(f"   ❌ {symbol}: {e}")

        logger.success(f"✅ Verified {len(verified_pairs)}/{len(Config.TRADING_PAIRS)} trading pairs")

    except Exception as e:
        logger.error(f"❌ Failed to verify trading pairs: {e}")
        return False

    # Summary
    logger.info("\n" + "="*60)
    logger.info("CONNECTION TEST SUMMARY")
    logger.info("="*60)
    logger.success("✅ All tests passed!")
    logger.info(f"\n💰 Account Balance: ${usdt_balance:,.2f} USDT")
    logger.info(f"🎯 Initial Balance Config: ${Config.INITIAL_BALANCE}")
    logger.info(f"📊 Trading Pairs: {len(verified_pairs)} active")
    logger.info(f"⚠️  Max Risk Per Trade: ${Config.INITIAL_BALANCE * Config.MAX_RISK_PER_TRADE:.2f}")
    logger.info(f"⚠️  Daily Profit Target: ${Config.TARGET_DAILY_PROFIT}")
    logger.info(f"⚠️  Daily Loss Limit: ${Config.MAX_DAILY_LOSS}")
    logger.info(f"🔒 Max Concurrent Trades: {Config.MAX_CONCURRENT_TRADES}")

    logger.info("\n" + "="*60)
    logger.success("🚀 READY FOR LIVE TRADING!")
    logger.info("="*60)
    logger.warning("\n⚠️  THIS IS REAL MONEY! TRADE AT YOUR OWN RISK!")
    logger.info("\nTo start trading, run:")
    logger.info("  python trading_bot.py")
    logger.info("\nOr in background:")
    logger.info("  nohup python trading_bot.py > /tmp/trading_bot.out 2>&1 &")

    return True

if __name__ == "__main__":
    try:
        success = test_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nUnexpected error: {e}")
        sys.exit(1)
