"""
Main Trading Bot Orchestrator
Coordinates all strategies, risk management, and order execution
"""
import asyncio
import time
import os
import signal
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

from config import Config
from binance_client import ResilientBinanceClient
from utils.technical_analysis import TechnicalAnalysis
from utils.risk_manager import RiskManager
from strategies.grid_strategy import GridTradingStrategy, DynamicGridStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy
from telegram_bot import TelegramBot


# Process lock file to prevent multiple instances
LOCK_FILE = './data/bot.lock'


def acquire_lock():
    """
    Acquire process lock to prevent multiple bot instances

    Raises:
        Exception if another bot instance is already running
    """
    if os.path.exists(LOCK_FILE):
        # Check if the PID in lock file is still running
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())

            # Check if process is still running
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                raise Exception(
                    f"Bot already running! PID {pid} is still active.\n"
                    f"If you're sure no bot is running, delete the lock file: {LOCK_FILE}"
                )
            except OSError:
                # Process doesn't exist, lock file is stale
                logger.warning(f"Removing stale lock file (PID {pid} not running)")
                os.remove(LOCK_FILE)
        except Exception as e:
            if "Bot already running" in str(e):
                raise
            logger.warning(f"Error checking lock file: {e}, removing it")
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)

    # Create lock file
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

    logger.info(f"Process lock acquired (PID: {os.getpid()})")


def release_lock():
    """Release process lock"""
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            logger.info("Process lock released")
        except Exception as e:
            logger.error(f"Error releasing lock file: {e}")


# Configure rotating file logger to prevent disk space issues
if Config.LOG_TO_FILE:
    import os
    os.makedirs(os.path.dirname(Config.LOG_FILE_PATH), exist_ok=True)

    logger.add(
        Config.LOG_FILE_PATH,
        rotation="100 MB",      # Rotate when file reaches 100MB
        retention="10 days",     # Keep logs for 10 days
        compression="zip",       # Compress rotated logs to save space
        level=Config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        backtrace=True,         # Enable backtrace for debugging
        diagnose=True           # Enable diagnosis for detailed error info
    )
    logger.info(f"Log rotation configured: {Config.LOG_FILE_PATH} (100MB rotation, 10 day retention)")


class BinanceTradingBot:
    """
    Main trading bot that orchestrates all components

    Features:
    - Multi-strategy portfolio management
    - Real-time technical analysis
    - Advanced risk management
    - Position tracking and management
    - Performance monitoring
    """

    def __init__(self):
        """Initialize trading bot"""
        logger.info("="*60)
        logger.info("BINANCE TRADING BOT INITIALIZATION")
        logger.info("="*60)

        # Validate configuration
        if not Config.validate():
            raise ValueError("Invalid configuration")

        Config.display_config()

        # Initialize components with appropriate API credentials
        api_key, api_secret = Config.get_api_credentials()
        self.client = ResilientBinanceClient(
            api_key,
            api_secret,
            testnet=(Config.TRADING_MODE == 'paper')
        )

        self.risk_manager = RiskManager(Config.INITIAL_BALANCE)

        # Initialize Telegram bot (if enabled)
        self.telegram_bot = None
        if Config.ENABLE_TELEGRAM and Config.TELEGRAM_BOT_TOKEN:
            authorized_users = Config.get_telegram_users()
            if authorized_users:
                self.telegram_bot = TelegramBot(
                    Config.TELEGRAM_BOT_TOKEN,
                    authorized_users,
                    trading_bot=self
                )
                logger.info(f"Telegram bot initialized for {len(authorized_users)} users")
            else:
                logger.warning("Telegram enabled but no authorized users configured")
        else:
            logger.info("Telegram bot disabled")

        # Initialize strategies for each symbol
        self.strategies: Dict[str, Dict] = {}
        for symbol in Config.TRADING_PAIRS:
            self.strategies[symbol] = self._initialize_strategies(symbol)

        # Bot state
        self.is_running = False
        self.start_time = None
        self.daily_profit_target_met = False
        self.daily_loss_limit_reached = False

        logger.success("Trading bot initialized successfully!")

    def _initialize_strategies(self, symbol: str) -> Dict:
        """
        Initialize all strategies for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Dict of strategies
        """
        strategies = {}

        if Config.ENABLE_GRID_STRATEGY:
            grid_spacing = Config.get_grid_spacing(symbol)
            strategies['grid'] = DynamicGridStrategy(
                symbol=symbol,
                grid_spacing=grid_spacing,
                num_levels=Config.GRID_LEVELS,
                allocation=Config.GRID_ALLOCATION
            )

        if Config.ENABLE_MOMENTUM_STRATEGY:
            strategies['momentum'] = MomentumStrategy(
                symbol=symbol,
                allocation=Config.MOMENTUM_ALLOCATION,
                client=self.client,  # Pass client for 4H timeframe confirmation
                risk_manager=self.risk_manager  # Pass risk manager for fixed 5% stops
            )

        if Config.ENABLE_MEAN_REVERSION:
            strategies['mean_reversion'] = MeanReversionStrategy(
                symbol=symbol,
                allocation=Config.MEAN_REVERSION_ALLOCATION,
                risk_manager=self.risk_manager  # Pass risk manager for fixed 5% stops
            )

        logger.info(f"Strategies initialized for {symbol}: {list(strategies.keys())}")
        return strategies

    async def start(self):
        """Start the trading bot"""
        self.is_running = True
        self.start_time = datetime.now()

        logger.info("\n" + "="*60)
        logger.info("TRADING BOT STARTED")
        logger.info(f"Time: {self.start_time}")
        logger.info(f"Mode: {Config.TRADING_MODE.upper()}")
        logger.info("="*60 + "\n")

        # Verify account access
        await self._verify_account()

        # Start Telegram bot (if enabled)
        if self.telegram_bot:
            try:
                await self.telegram_bot.start_bot()
            except Exception as e:
                logger.error(f"Failed to start Telegram bot: {e}")
                logger.warning("Continuing without Telegram bot...")
                self.telegram_bot = None

        # Start trading loops for each symbol
        tasks = []
        for symbol in Config.TRADING_PAIRS:
            task = asyncio.create_task(self.trade_symbol(symbol))
            tasks.append(task)

        # Start monitoring task
        tasks.append(asyncio.create_task(self.monitor_performance()))

        # Run all tasks
        await asyncio.gather(*tasks)

    async def _verify_account(self):
        """Verify account access and display balance"""
        try:
            balances = self.client.get_account_balance()

            logger.info("Account verified successfully!")
            logger.info("Current balances:")

            # Display USDT balance
            if 'USDT' in balances:
                usdt_balance = balances['USDT']['total']
                logger.info(f"  USDT: ${usdt_balance:,.2f}")

                # Update risk manager balance (LIVE mode only)
                # In PAPER mode, we want to simulate trading with INITIAL_BALANCE from .env
                if Config.TRADING_MODE == 'live':
                    self.risk_manager.balance = usdt_balance
                    self.risk_manager.initial_balance = usdt_balance
                    logger.info(f"Balance synced from exchange: ${usdt_balance:,.2f}")
                else:
                    logger.info(f"Paper mode: Using simulated balance of ${self.risk_manager.balance:,.2f} (testnet has ${usdt_balance:,.2f})")

            # Display other significant balances
            for asset, balance in balances.items():
                if asset != 'USDT' and balance['total'] > 0.001:
                    logger.info(f"  {asset}: {balance['total']:.8f}")

        except Exception as e:
            logger.error(f"Failed to verify account: {e}")
            raise

    async def trade_symbol(self, symbol: str):
        """
        Main trading loop for a single symbol

        Args:
            symbol: Trading pair symbol
        """
        logger.info(f"Starting trading loop for {symbol}")

        while self.is_running:
            try:
                # Check daily limits
                if await self._check_daily_limits():
                    logger.warning("Daily limits reached, pausing trading")
                    await asyncio.sleep(60)  # Check again in 1 minute
                    continue

                # Get market data
                klines = self.client.get_historical_klines(symbol, '5m', limit=200)
                if not klines:
                    logger.warning(f"No klines data for {symbol}")
                    await asyncio.sleep(30)
                    continue

                # Prepare DataFrame
                df = TechnicalAnalysis.prepare_dataframe(klines)

                # Run technical analysis
                ta = TechnicalAnalysis(df)
                ta.calculate_all_indicators()

                # Get latest values
                latest_data = ta.get_latest_values()
                latest_data['trend'] = ta.identify_trend()
                latest_data['position_score'] = ta.calculate_position_score()

                # Get current price
                current_price = self.client.get_symbol_price(symbol)
                if not current_price:
                    await asyncio.sleep(30)
                    continue

                latest_data['price'] = current_price

                logger.debug(
                    f"{symbol}: Price=${current_price:.2f}, "
                    f"RSI={latest_data['rsi']:.1f}, "
                    f"Trend={latest_data['trend']}, "
                    f"Score={latest_data['position_score']:.1f}"
                )

                # Update existing positions
                await self._update_positions(symbol, latest_data, ta)

                # Check for new opportunities
                if len(self.risk_manager.positions) < Config.MAX_CONCURRENT_TRADES:
                    await self._check_entry_signals(symbol, latest_data, ta)

                # Wait before next iteration
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                import traceback
                logger.error(f"Error in trading loop for {symbol}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(60)

    async def _update_positions(self, symbol: str, latest_data: Dict, ta: TechnicalAnalysis):
        """
        Update and manage existing positions

        Args:
            symbol: Trading pair symbol
            latest_data: Latest technical data
            ta: TechnicalAnalysis instance
        """
        position = self.risk_manager.get_position(symbol)
        if not position:
            return

        current_price = latest_data['price']
        atr = latest_data['atr']

        # SANITY CHECK: Reject obviously bad price data
        # If price moved more than 5% from last known price in a single tick, it's likely bad API data
        last_known_price = position.current_price if position.current_price > 0 else position.entry_price
        price_change_pct = abs(current_price - last_known_price) / last_known_price * 100

        if price_change_pct > 5:
            logger.error(f"⚠️ BAD DATA REJECTED for {symbol}: Price ${current_price:.2f} is {price_change_pct:.1f}% from last price ${last_known_price:.2f} - ignoring this tick")
            return

        # Update position price (only after sanity check passes)
        self.risk_manager.update_position_price(symbol, current_price)

        # Check stop loss with CONFIRMATION requirement
        # Bad API data typically corrects within 1-2 ticks, so require 2 consecutive readings below stop
        if position.side == 'BUY' and current_price <= position.stop_loss:
            # Initialize or increment stop loss hit counter
            if not hasattr(self, '_stop_loss_confirmations'):
                self._stop_loss_confirmations = {}

            prev_count = self._stop_loss_confirmations.get(symbol, 0)
            self._stop_loss_confirmations[symbol] = prev_count + 1

            if self._stop_loss_confirmations[symbol] >= 2:
                # Confirmed - 2 consecutive ticks below stop
                logger.warning(f"Stop loss CONFIRMED for {symbol} at ${current_price:.2f} (2 consecutive ticks)")
                await self._close_position(symbol, position.stop_loss, "Stop loss")  # Exit at stop level, not bad price
                self._stop_loss_confirmations[symbol] = 0
                return
            else:
                logger.warning(f"⚠️ Stop loss triggered for {symbol} at ${current_price:.2f} - waiting for confirmation (1/2)")
                return
        else:
            # Price recovered or above stop - reset counter
            if hasattr(self, '_stop_loss_confirmations') and symbol in self._stop_loss_confirmations:
                if self._stop_loss_confirmations[symbol] > 0:
                    logger.info(f"✅ {symbol} price recovered to ${current_price:.2f} - stop loss NOT triggered (was bad data)")
                self._stop_loss_confirmations[symbol] = 0

        # SIMPLE TP/SL SYSTEM:
        # Take Profit: 1.3% - lock in gains quickly, re-enter if still bullish
        # Stop Loss: 5% - handled above

        TAKE_PROFIT_PCT = 1.3  # 1.3% take profit

        if position.side == 'BUY':
            current_profit_pct = ((current_price - position.entry_price) / position.entry_price) * 100

            # Take profit at 1.3%
            if current_profit_pct >= TAKE_PROFIT_PCT:
                take_profit_price = position.entry_price * (1 + TAKE_PROFIT_PCT / 100)
                logger.info(f"🎯 Take profit hit for {symbol} - exiting at ${take_profit_price:.2f} (+{TAKE_PROFIT_PCT}%)")
                await self._close_position(symbol, take_profit_price, "Take profit")
                return

            # Stop loss handled above (5% from entry)

        # Exits are now TP/SL only - no signal-based early exits
        # Entry filters remain comprehensive (momentum, trend, volume, etc.)
        # But once in a position, we ride to 1.3% TP or 5% SL

    async def _check_entry_signals(self, symbol: str, latest_data: Dict, ta: TechnicalAnalysis):
        """
        Check for new entry signals from strategies

        Args:
            symbol: Trading pair symbol
            latest_data: Latest technical data
            ta: TechnicalAnalysis instance
        """
        # Don't enter if already have position
        if self.risk_manager.get_position(symbol):
            return

        # Check cooldown period (prevents churning after losses)
        can_trade, reason = self.risk_manager.can_trade_symbol(symbol)
        if not can_trade:
            logger.debug(f"Cannot trade {symbol}: {reason}")
            return

        strategies = self.strategies[symbol]
        current_price = latest_data['price']
        atr = latest_data['atr']
        atr_pct = latest_data['atr_pct']

        # Check momentum strategy
        if 'momentum' in strategies:
            momentum_strat = strategies['momentum']
            if not momentum_strat.in_position:
                should_enter, confidence, _ = momentum_strat.should_enter_long(latest_data)

                if should_enter and confidence >= 0.65:  # Raised from 0.60 for higher quality entries
                    signal = momentum_strat.generate_signal(latest_data)
                    if signal:
                        await self._execute_entry(
                            symbol,
                            signal.entry_price,
                            signal.stop_loss,
                            signal.take_profit,
                            atr,
                            atr_pct,
                            f"Momentum (confidence: {confidence:.2f})"
                        )
                        return

        # Check mean reversion strategy
        if 'mean_reversion' in strategies:
            mr_strat = strategies['mean_reversion']
            if not mr_strat.in_position:
                should_enter, confidence, _ = mr_strat.should_enter_long(latest_data)

                if should_enter and confidence > 0.65:
                    signal = mr_strat.generate_signal(latest_data)
                    if signal:
                        await self._execute_entry(
                            symbol,
                            signal.entry_price,
                            signal.stop_loss,
                            signal.take_profit,
                            atr,
                            atr_pct,
                            f"Mean Reversion (confidence: {confidence:.2f})"
                        )
                        return

        # Check grid strategy
        if 'grid' in strategies:
            grid_strat = strategies['grid']
            if not grid_strat.active:
                should_enter, reason = grid_strat.should_enter_position(current_price, latest_data)

                if should_enter:
                    logger.info(f"Setting up grid for {symbol}: {reason}")
                    capital = self.risk_manager.balance * grid_strat.allocation
                    grid_strat.setup_grid(current_price, capital)
                    # Grid strategy places its own orders
                    # For now, we'll just log this
                    logger.info(f"Grid active for {symbol}")

    async def _execute_entry(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        atr: float,
        atr_pct: float,
        strategy_name: str
    ):
        """
        Execute entry into new position

        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            atr: Average True Range
            atr_pct: ATR percentage
            strategy_name: Name of strategy triggering entry
        """
        try:
            # Calculate position size
            position_size, position_value = self.risk_manager.calculate_position_size(
                symbol,
                entry_price,
                stop_loss,
                atr,
                atr_pct
            )

            # Check if position is allowed
            risk_amount = abs(entry_price - stop_loss) * position_size
            can_trade, reason = self.risk_manager.should_allow_new_position(
                symbol,
                position_value,
                risk_amount
            )

            if not can_trade:
                logger.warning(f"Position rejected for {symbol}: {reason}")
                return

            logger.info(
                f"\n{'='*60}\n"
                f"ENTRY SIGNAL: {symbol}\n"
                f"Strategy: {strategy_name}\n"
                f"Entry: ${entry_price:.2f}\n"
                f"Stop Loss: ${stop_loss:.2f} ({((stop_loss-entry_price)/entry_price*100):.2f}%)\n"
                f"Exit Strategy: 5% Trailing Stop (No fixed TP - let winners run!)\n"
                f"Position Size: {position_size:.6f} ({symbol.replace('USDT', '')})\n"
                f"Position Value: ${position_value:.2f}\n"
                f"Risk: ${risk_amount:.2f}\n"
                f"{'='*60}\n"
            )

            # Execute market buy order
            if Config.TRADING_MODE == 'live':
                order = self.client.place_market_order(symbol, 'BUY', position_size)

                if order:
                    fill_price = float(order['fills'][0]['price']) if order.get('fills') else entry_price

                    # Add position to risk manager
                    self.risk_manager.add_position(
                        symbol=symbol,
                        side='BUY',
                        entry_price=fill_price,
                        quantity=position_size,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        timestamp=time.time()
                    )

                    # Update strategy state
                    strategies = self.strategies[symbol]
                    if 'momentum' in strategy_name.lower() and 'momentum' in strategies:
                        strategies['momentum'].enter_position(fill_price)
                    elif 'reversion' in strategy_name.lower() and 'mean_reversion' in strategies:
                        mean_price = (stop_loss + take_profit) / 2
                        strategies['mean_reversion'].enter_position(fill_price, mean_price)

                    logger.success(f"Position opened: {symbol} @ ${fill_price:.2f}")

                    # Send Telegram notification
                    if self.telegram_bot:
                        await self.telegram_bot.notify_trade_opened(
                            symbol, 'BUY', fill_price, position_size,
                            stop_loss, take_profit, strategy_name
                        )
                else:
                    logger.error(f"Failed to execute entry order for {symbol}")

            else:
                # Paper trading mode
                logger.info(f"[PAPER TRADE] Would buy {position_size:.6f} {symbol} @ ${entry_price:.2f}")

                # Still track in risk manager for paper trading
                self.risk_manager.add_position(
                    symbol=symbol,
                    side='BUY',
                    entry_price=entry_price,
                    quantity=position_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    timestamp=time.time()
                )

                # Send Telegram notification (paper trading)
                if self.telegram_bot:
                    await self.telegram_bot.notify_trade_opened(
                        symbol, 'BUY', entry_price, position_size,
                        stop_loss, take_profit, f"{strategy_name} [PAPER]"
                    )

        except Exception as e:
            logger.error(f"Error executing entry for {symbol}: {e}")

    async def _close_position(self, symbol: str, exit_price: float, reason: str):
        """
        Close an existing position

        Args:
            symbol: Trading pair symbol
            exit_price: Exit price
            reason: Reason for closing
        """
        try:
            position = self.risk_manager.get_position(symbol)
            if not position:
                return

            # Check if we should attempt to close (prevents infinite retry loops)
            if not self.risk_manager.should_attempt_close(symbol):
                logger.error(f"Skipping close attempt for {symbol} - max retries exceeded")
                return

            logger.info(f"\nClosing position: {symbol} @ ${exit_price:.2f} - Reason: {reason}")

            # Execute market sell order
            if Config.TRADING_MODE == 'live':
                order = self.client.place_market_order(symbol, 'SELL', position.quantity)

                if order:
                    fill_price = float(order['fills'][0]['price']) if order.get('fills') else exit_price
                    realized_pnl = self.risk_manager.close_position(symbol, fill_price)

                    logger.success(
                        f"Position closed: {symbol} - "
                        f"PnL: ${realized_pnl:.2f} ({position.unrealized_pnl_pct:.2f}%)"
                    )

                    # Send Telegram notification
                    if self.telegram_bot and realized_pnl is not None:
                        await self.telegram_bot.notify_trade_closed(
                            symbol, position.entry_price, fill_price,
                            realized_pnl, position.unrealized_pnl_pct, reason
                        )
                else:
                    logger.error(f"Failed to execute exit order for {symbol}")

            else:
                # Paper trading mode
                logger.info(f"[PAPER TRADE] Would sell {position.quantity:.6f} {symbol} @ ${exit_price:.2f}")
                realized_pnl = self.risk_manager.close_position(symbol, exit_price)

                if realized_pnl:
                    logger.info(f"Paper trade PnL: ${realized_pnl:.2f}")

                    # Send Telegram notification (paper trading)
                    if self.telegram_bot:
                        await self.telegram_bot.notify_trade_closed(
                            symbol, position.entry_price, exit_price,
                            realized_pnl, position.unrealized_pnl_pct, f"{reason} [PAPER]"
                        )

            # Update strategy state
            strategies = self.strategies[symbol]
            if 'momentum' in strategies:
                strategies['momentum'].exit_position(exit_price)
            if 'mean_reversion' in strategies:
                strategies['mean_reversion'].exit_position(exit_price)

        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")

    async def _check_daily_limits(self) -> bool:
        """
        Check if daily profit/loss limits have been reached

        Returns:
            True if limits reached
        """
        daily_pnl = self.risk_manager.daily_pnl

        # Check profit target
        if daily_pnl >= Config.TARGET_DAILY_PROFIT:
            if not self.daily_profit_target_met:
                logger.success(
                    f"Daily profit target MET! ${daily_pnl:.2f} >= ${Config.TARGET_DAILY_PROFIT:.2f}"
                )
                self.daily_profit_target_met = True

                # Send Telegram notification
                if self.telegram_bot:
                    await self.telegram_bot.notify_daily_target_met(daily_pnl)

            return False  # Continue trading to maximize profit

        # Check loss limit
        if daily_pnl <= -Config.MAX_DAILY_LOSS:
            if not self.daily_loss_limit_reached:
                logger.error(
                    f"Daily loss limit REACHED! ${daily_pnl:.2f} <= -${Config.MAX_DAILY_LOSS:.2f}"
                )
                self.daily_loss_limit_reached = True

                # Send Telegram notification
                if self.telegram_bot:
                    await self.telegram_bot.notify_daily_loss_limit(daily_pnl)

            return True  # Stop trading

        return False

    async def monitor_performance(self):
        """Monitor and log performance metrics"""
        while self.is_running:
            await asyncio.sleep(300)  # Update every 5 minutes

            try:
                # Check for stale positions (safety mechanism) - now returns info for notifications
                stale_positions = self.risk_manager.check_stale_positions()

                # Send Telegram notifications for any stale positions that were closed
                if stale_positions and self.telegram_bot:
                    for pos_info in stale_positions:
                        try:
                            await self.telegram_bot.notify_trade_closed(
                                symbol=pos_info['symbol'],
                                entry_price=pos_info['entry_price'],
                                exit_price=pos_info['exit_price'],
                                pnl=pos_info['pnl'],
                                pnl_pct=pos_info['pnl_pct'],
                                reason=pos_info['reason']
                            )
                        except Exception as e:
                            logger.error(f"Failed to send stale position notification for {pos_info['symbol']}: {e}")

                summary = self.risk_manager.get_portfolio_summary()

                logger.info("\n" + "="*60)
                logger.info("PERFORMANCE UPDATE")
                logger.info("="*60)
                logger.info(f"Balance: ${summary['balance']:,.2f}")
                logger.info(f"Total PnL: ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)")
                logger.info(f"Daily PnL: ${summary['daily_pnl']:,.2f}")
                logger.info(f"Open Positions: {summary['open_positions']}")
                logger.info(f"Portfolio Heat: {summary['portfolio_heat']:.1%}")
                logger.info(f"Win Rate: {summary['win_rate']:.1f}%")
                logger.info(f"Total Trades: {summary['total_trades']}")
                logger.info("="*60 + "\n")

            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")

    async def stop(self):
        """Stop the trading bot gracefully"""
        logger.info("Stopping trading bot...")
        self.is_running = False

        # Stop Telegram bot
        if self.telegram_bot:
            await self.telegram_bot.stop_bot()

        # Display final statistics
        self.risk_manager.display_portfolio()

        # Release process lock
        release_lock()

        logger.info("Trading bot stopped successfully")


async def main():
    """Main entry point"""
    # Acquire process lock to prevent duplicate instances
    try:
        acquire_lock()
    except Exception as e:
        logger.error(f"Failed to acquire process lock: {e}")
        return

    bot = None
    try:
        bot = BinanceTradingBot()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("\nReceived keyboard interrupt...")
        if bot:
            await bot.stop()
        else:
            release_lock()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        if bot:
            await bot.stop()
        else:
            release_lock()


if __name__ == "__main__":
    asyncio.run(main())
