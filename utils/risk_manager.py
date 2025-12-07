"""
Advanced Risk Management System
Implements position sizing, stop loss calculation, and portfolio risk monitoring
"""
import numpy as np
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from loguru import logger


@dataclass
class Position:
    """Represents an open trading position"""
    symbol: str
    side: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    timestamp: float
    current_price: float = 0.0
    highest_price: float = 0.0  # Track highest price for trailing stop

    @property
    def position_value(self) -> float:
        """Current position value"""
        return self.quantity * self.current_price if self.current_price > 0 else self.quantity * self.entry_price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss"""
        if self.current_price == 0:
            return 0.0
        if self.side == 'BUY':
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized PnL percentage"""
        if self.side == 'BUY':
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - self.current_price) / self.entry_price) * 100

    @property
    def risk_amount(self) -> float:
        """Amount at risk (distance to stop loss)"""
        return abs(self.entry_price - self.stop_loss) * self.quantity


class RiskManager:
    """
    Advanced risk management with:
    - ATR-based dynamic stop losses
    - Volatility-adjusted position sizing
    - Kelly Criterion optimization
    - Portfolio heat monitoring
    """

    def __init__(self, initial_balance: float):
        """
        Initialize risk manager

        Args:
            initial_balance: Starting account balance
        """
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.max_risk_per_trade = 0.02  # 2% per trade
        self.max_portfolio_risk = 0.15  # 15% total portfolio risk
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_trades = 0

        # Anti-churning controls
        self.cooldown_periods: Dict[str, datetime] = {}  # Track cooldown after losses
        self.symbol_trade_counts: Dict[str, int] = {}  # Track trades per symbol today
        self.cooldown_minutes = 20  # Wait 20 minutes after a loss before re-entering
        self.max_daily_trades = 25  # Maximum total trades per day
        self.max_symbol_trades_per_day = 3  # Maximum trades per symbol per day

        # Additional safeguards (prevent infinite retry loops)
        self.position_close_attempts: Dict[str, int] = {}  # Track failed close attempts
        self.max_close_attempts = 3  # Max retries before forcing position removal
        self.max_position_age_hours = 72  # Remove stale positions after 72 hours (3 days)

        # Persistent daily P&L tracking
        self.daily_pnl_file = './data/daily_pnl.json'
        self._load_daily_pnl()

        logger.info(f"Risk Manager initialized with balance: ${initial_balance:,.2f}")
        logger.info(f"Daily P&L loaded: ${self.daily_pnl:.2f} ({self.daily_trades} trades today)")

    def _load_daily_pnl(self):
        """Load daily P&L from persistent storage"""
        try:
            if os.path.exists(self.daily_pnl_file):
                with open(self.daily_pnl_file, 'r') as f:
                    data = json.load(f)

                # Check if it's from today
                saved_date = data.get('date', '')
                today = datetime.now().strftime('%Y-%m-%d')

                if saved_date == today:
                    # Load today's data
                    self.daily_pnl = data.get('daily_pnl', 0.0)
                    self.daily_trades = data.get('daily_trades', 0)
                    logger.info(f"Loaded daily P&L from file: ${self.daily_pnl:.2f}")
                else:
                    # Different day, reset and save
                    logger.info(f"New trading day detected (was {saved_date}, now {today})")
                    self.daily_pnl = 0.0
                    self.daily_trades = 0
                    # Reset cooldowns and trade counts for new day
                    self.cooldown_periods.clear()
                    self.symbol_trade_counts.clear()
                    self._save_daily_pnl()
            else:
                # File doesn't exist, create it
                logger.info("No daily P&L file found, creating new one")
                self._save_daily_pnl()
        except Exception as e:
            logger.error(f"Error loading daily P&L: {e}")
            self.daily_pnl = 0.0
            self.daily_trades = 0

    def _save_daily_pnl(self):
        """Save daily P&L to persistent storage"""
        try:
            data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'daily_pnl': self.daily_pnl,
                'daily_trades': self.daily_trades,
                'last_updated': datetime.now().isoformat(),
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'total_trades': self.total_trades
            }

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.daily_pnl_file), exist_ok=True)

            with open(self.daily_pnl_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved daily P&L: ${self.daily_pnl:.2f}")
        except Exception as e:
            logger.error(f"Error saving daily P&L: {e}")

    def sync_balance_from_exchange(self, client) -> bool:
        """
        Sync balance from exchange (Binance)

        Args:
            client: Binance client instance

        Returns:
            True if successful, False otherwise
        """
        try:
            real_balance = client.get_usdt_balance()
            if real_balance > 0:
                old_balance = self.balance
                self.balance = real_balance
                logger.info(f"Balance synced from exchange: ${old_balance:.2f} -> ${real_balance:.2f}")
                return True
            else:
                logger.warning("Could not sync balance from exchange (got 0)")
                return False
        except Exception as e:
            logger.error(f"Error syncing balance from exchange: {e}")
            return False

    def is_symbol_in_cooldown(self, symbol: str) -> bool:
        """
        Check if a symbol is in cooldown period after a loss

        Args:
            symbol: Trading pair symbol

        Returns:
            True if in cooldown, False otherwise
        """
        if symbol not in self.cooldown_periods:
            return False

        cooldown_until = self.cooldown_periods[symbol]
        now = datetime.now()

        if now < cooldown_until:
            remaining = (cooldown_until - now).total_seconds() / 60
            logger.debug(f"{symbol} in cooldown for {remaining:.1f} more minutes")
            return True
        else:
            # Cooldown expired, remove it
            del self.cooldown_periods[symbol]
            return False

    def can_trade_symbol(self, symbol: str) -> tuple[bool, str]:
        """
        Check if we can trade a symbol based on cooldown period

        Args:
            symbol: Trading pair symbol

        Returns:
            (can_trade, reason) tuple
        """
        # Check cooldown after previous loss
        if self.is_symbol_in_cooldown(symbol):
            remaining = (self.cooldown_periods[symbol] - datetime.now()).total_seconds() / 60
            return False, f"Symbol in cooldown ({remaining:.1f} min remaining)"

        return True, "OK"

    def _set_cooldown(self, symbol: str):
        """Set cooldown period for a symbol after a loss"""
        cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        self.cooldown_periods[symbol] = cooldown_until
        logger.info(f"Cooldown set for {symbol} until {cooldown_until.strftime('%H:%M:%S')} ({self.cooldown_minutes} min)")

    def should_attempt_close(self, symbol: str) -> bool:
        """
        Check if we should attempt to close a position (prevents infinite retry loops)

        Args:
            symbol: Trading pair symbol

        Returns:
            True if should attempt, False if max retries exceeded
        """
        attempts = self.position_close_attempts.get(symbol, 0)

        if attempts >= self.max_close_attempts:
            logger.error(
                f"Failed to close {symbol} {attempts} times - FORCING REMOVAL! "
                f"This prevents infinite retry loops."
            )
            # Force remove position to prevent churning
            if symbol in self.positions:
                del self.positions[symbol]
            # Reset attempt counter
            self.position_close_attempts[symbol] = 0
            return False

        return True

    def record_close_attempt(self, symbol: str, success: bool):
        """
        Record a position close attempt

        Args:
            symbol: Trading pair symbol
            success: Whether the close was successful
        """
        if success:
            # Reset counter on success
            if symbol in self.position_close_attempts:
                del self.position_close_attempts[symbol]
        else:
            # Increment failed attempt counter
            self.position_close_attempts[symbol] = self.position_close_attempts.get(symbol, 0) + 1
            logger.warning(
                f"Close attempt {self.position_close_attempts[symbol]}/{self.max_close_attempts} "
                f"failed for {symbol}"
            )

    def check_stale_positions(self) -> List[Dict]:
        """
        Check for and close positions that have been open too long (safety mechanism)
        Properly closes positions with current price to track PnL.

        Returns:
            List of closed stale position info dicts for Telegram notification
        """
        now = datetime.now().timestamp()
        stale_positions_info = []

        # First pass: identify stale positions
        stale_symbols = []
        for symbol, position in self.positions.items():
            age_hours = (now - position.timestamp) / 3600

            if age_hours > self.max_position_age_hours:
                stale_symbols.append((symbol, position, age_hours))

        # Second pass: properly close stale positions
        for symbol, position, age_hours in stale_symbols:
            logger.warning(
                f"Closing STALE position: {symbol} "
                f"(open for {age_hours:.1f} hours, max is {self.max_position_age_hours})"
            )

            # Use current_price if available, otherwise use entry_price
            exit_price = position.current_price if position.current_price > 0 else position.entry_price

            # Calculate PnL before closing
            position.current_price = exit_price
            pnl = position.unrealized_pnl
            pnl_pct = position.unrealized_pnl_pct

            # Store info for notification BEFORE closing
            stale_positions_info.append({
                'symbol': symbol,
                'entry_price': position.entry_price,
                'exit_price': exit_price,
                'quantity': position.quantity,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'age_hours': age_hours,
                'reason': f'Stale position ({age_hours:.1f}h > {self.max_position_age_hours}h max)'
            })

            # Properly close the position (tracks PnL, updates balance, etc.)
            try:
                self.close_position(symbol, exit_price)
                logger.warning(
                    f"Stale position closed: {symbol} - "
                    f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%) after {age_hours:.1f} hours"
                )
            except Exception as e:
                logger.error(f"Error closing stale position {symbol}: {e}")
                # Force remove if close fails
                if symbol in self.positions:
                    del self.positions[symbol]

            # Reset close attempts counter
            if symbol in self.position_close_attempts:
                del self.position_close_attempts[symbol]

        if stale_positions_info:
            logger.warning(f"Closed {len(stale_positions_info)} stale positions: {', '.join([p['symbol'] for p in stale_positions_info])}")

        return stale_positions_info

    def _increment_symbol_trades(self, symbol: str):
        """Increment trade count for a symbol"""
        self.symbol_trade_counts[symbol] = self.symbol_trade_counts.get(symbol, 0) + 1
        logger.debug(f"Trade count for {symbol}: {self.symbol_trade_counts[symbol]}/{self.max_symbol_trades_per_day}")

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        atr: float,
        volatility_pct: float
    ) -> Tuple[float, float]:
        """
        Calculate optimal position size using multiple factors

        Args:
            symbol: Trading pair symbol
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            atr: Average True Range
            volatility_pct: Current volatility percentage

        Returns:
            Tuple of (position_size_in_asset, position_value_in_usd)
        """
        from config import Config

        # Calculate basic risk amount
        risk_amount = self.balance * Config.MAX_RISK_PER_TRADE

        # Calculate stop distance
        stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price

        # Basic position size
        base_position_value = risk_amount / stop_distance_pct

        # Volatility adjustment
        volatility_adj = self.get_volatility_adjustment(volatility_pct)

        # Kelly Criterion adjustment (if we have enough trading history)
        kelly_factor = self.calculate_kelly_factor()

        # Calculate final position size
        adjusted_position_value = base_position_value * volatility_adj * kelly_factor

        # Check portfolio risk limits
        max_allowed_value = self.balance * Config.MAX_PORTFOLIO_RISK
        current_portfolio_risk = self.calculate_portfolio_heat()

        # Don't exceed portfolio risk limit
        available_risk = max_allowed_value - (current_portfolio_risk * self.balance)
        final_position_value = min(adjusted_position_value, available_risk)

        # Also check single position limit (10% max - reduced from 20% after losses)
        max_single_position = self.balance * 0.10
        final_position_value = min(final_position_value, max_single_position)

        # Calculate position size in asset
        position_size = final_position_value / entry_price

        logger.debug(
            f"Position sizing for {symbol}: "
            f"${final_position_value:.2f} ({position_size:.6f} {symbol})"
        )

        return position_size, final_position_value

    def calculate_atr_stop_loss(
        self,
        entry_price: float,
        atr: float,
        position_type: str = 'long'
    ) -> float:
        """
        Calculate FIXED 5% stop loss from entry

        NOTE: Changed from ATR-based to fixed 5% to ensure consistent risk per trade.
        The 5% trailing stop will then maintain this distance as price moves in profit.

        Args:
            entry_price: Entry price
            atr: Average True Range (not used, kept for compatibility)
            position_type: 'long' or 'short'

        Returns:
            Stop loss price
        """
        # Fixed 5% stop loss for all trades
        FIXED_STOP_PERCENT = 0.05  # 5%

        if position_type == 'long':
            stop_loss = entry_price * (1 - FIXED_STOP_PERCENT)
        else:
            stop_loss = entry_price * (1 + FIXED_STOP_PERCENT)

        logger.debug(f"Fixed 5% stop loss calculated: {stop_loss:.8f} (entry: {entry_price:.8f}, -{FIXED_STOP_PERCENT*100}%)")

        return stop_loss

    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        position_type: str = 'long',
        risk_reward_ratio: float = 2.0
    ) -> float:
        """
        Calculate take profit based on risk-reward ratio

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            position_type: 'long' or 'short'
            risk_reward_ratio: Desired risk:reward ratio

        Returns:
            Take profit price
        """
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = risk_distance * risk_reward_ratio

        if position_type == 'long':
            take_profit = entry_price + reward_distance
        else:
            take_profit = entry_price - reward_distance

        logger.debug(
            f"Take profit calculated: {take_profit:.8f} "
            f"(R:R = 1:{risk_reward_ratio})"
        )

        return take_profit

    def calculate_trailing_stop(
        self,
        current_price: float,
        highest_price: float,
        atr: float,
        position_type: str = 'long'
    ) -> float:
        """
        Calculate trailing stop with acceleration

        Args:
            current_price: Current market price
            highest_price: Highest price since entry (for long) or lowest (for short)
            atr: Average True Range
            position_type: 'long' or 'short'

        Returns:
            Trailing stop price
        """
        # 3% trailing stop - tighter to protect gains
        # Combined with breakeven stop at 2%, this prevents turning winners into losers
        TRAILING_STOP_PERCENT = 0.03  # 3%

        if position_type == 'long':
            # Long: Stop 3% below highest price reached
            trailing_stop = highest_price * (1 - TRAILING_STOP_PERCENT)
        else:
            # Short: Stop 3% above lowest price reached
            trailing_stop = highest_price * (1 + TRAILING_STOP_PERCENT)

        return trailing_stop

    def get_volatility_adjustment(self, volatility_pct: float) -> float:
        """
        Adjust position size based on current volatility

        Args:
            volatility_pct: Current volatility percentage

        Returns:
            Adjustment factor (0.5 - 1.0)
        """
        if volatility_pct > 8:  # High volatility
            return 0.5
        elif volatility_pct > 5:  # Medium volatility
            return 0.75
        else:  # Low volatility
            return 1.0

    def calculate_kelly_factor(self) -> float:
        """
        Calculate Kelly Criterion for position sizing optimization

        Returns:
            Kelly factor (capped at 0.20)
        """
        if self.total_trades < 20:
            return 0.5  # Conservative until we have more data

        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.5

        # Assume average win/loss ratios (can be tracked more precisely)
        avg_win = 0.025  # 2.5% average win
        avg_loss = 0.015  # 1.5% average loss

        # Kelly formula: win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        kelly_full = win_rate - ((1 - win_rate) / (avg_win / avg_loss))

        # Use fractional Kelly for safety (50%)
        kelly_factor = max(0.25, min(kelly_full * 0.5, 0.20))

        return kelly_factor

    def calculate_portfolio_heat(self) -> float:
        """
        Calculate total portfolio risk exposure

        Returns:
            Portfolio heat as percentage of balance
        """
        total_risk = 0.0

        for symbol, position in self.positions.items():
            risk_amount = position.risk_amount
            total_risk += risk_amount

        portfolio_heat = total_risk / self.balance if self.balance > 0 else 0.0

        return portfolio_heat

    def should_allow_new_position(
        self,
        symbol: str,
        position_value: float,
        risk_amount: float
    ) -> Tuple[bool, str]:
        """
        Determine if new position meets risk criteria

        Args:
            symbol: Trading pair symbol
            position_value: Value of proposed position
            risk_amount: Amount at risk

        Returns:
            Tuple of (allowed, reason)
        """
        from config import Config

        # Check if already have position
        if symbol in self.positions:
            return False, f"Already have open position in {symbol}"

        # Check portfolio heat
        current_heat = self.calculate_portfolio_heat()
        risk_pct = risk_amount / self.balance

        new_heat = current_heat + risk_pct
        if new_heat > Config.MAX_PORTFOLIO_RISK:
            return False, f"Portfolio heat limit exceeded ({new_heat:.1%} > {Config.MAX_PORTFOLIO_RISK:.1%})"

        # Check single position limit
        position_pct = position_value / self.balance
        if position_pct > 0.20:
            return False, f"Single position size limit exceeded ({position_pct:.1%} > 20%)"

        # Check max concurrent positions
        if len(self.positions) >= Config.MAX_CONCURRENT_TRADES:
            return False, f"Max concurrent trades reached ({Config.MAX_CONCURRENT_TRADES})"

        # Check daily loss limit
        if self.daily_pnl <= -Config.MAX_DAILY_LOSS:
            return False, f"Daily loss limit reached (${self.daily_pnl:.2f})"

        return True, "Position approved"

    def add_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float,
        timestamp: float
    ):
        """Add new position to tracking"""
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=timestamp,
            current_price=entry_price,
            highest_price=entry_price  # Initialize to entry price
        )

        self.positions[symbol] = position
        logger.info(f"Position added: {symbol} {side} @ {entry_price:.8f}")

    def update_position_price(self, symbol: str, current_price: float):
        """Update current price and track highest price for trailing stop"""
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = current_price

            # Track highest price for long positions (for trailing stop)
            if position.side == 'BUY':
                if current_price > position.highest_price:
                    position.highest_price = current_price
                    logger.debug(f"{symbol} new high: ${current_price:.2f}")
            # Track lowest price for short positions
            elif position.side == 'SELL':
                if position.highest_price == 0 or current_price < position.highest_price:
                    position.highest_price = current_price  # For shorts, this tracks the lowest

    def close_position(self, symbol: str, exit_price: float) -> Optional[float]:
        """
        Close position and calculate PnL with comprehensive error handling

        Args:
            symbol: Trading pair symbol
            exit_price: Exit price

        Returns:
            Realized PnL
        """
        if symbol not in self.positions:
            logger.warning(f"Attempted to close non-existent position: {symbol}")
            return None

        try:
            position = self.positions[symbol]
            position.current_price = exit_price

            # Calculate realized PnL
            realized_pnl = position.unrealized_pnl

            # Update statistics
            self.balance += realized_pnl
            self.daily_pnl += realized_pnl
            self.total_trades += 1
            self.daily_trades += 1

            if realized_pnl > 0:
                self.winning_trades += 1
                logger.success(f"Position closed: {symbol} - Profit: ${realized_pnl:.2f} ({position.unrealized_pnl_pct:.2f}%)")
            else:
                self.losing_trades += 1
                logger.warning(f"Position closed: {symbol} - Loss: ${realized_pnl:.2f} ({position.unrealized_pnl_pct:.2f}%)")
                # Set cooldown period after loss to prevent immediate re-entry
                self._set_cooldown(symbol)

            # Remove position (CRITICAL - must happen even if errors above)
            del self.positions[symbol]

            # Save daily P&L to persistent storage
            self._save_daily_pnl()

            # Record successful close
            self.record_close_attempt(symbol, success=True)

            return realized_pnl

        except Exception as e:
            logger.error(f"ERROR closing position {symbol}: {e}")

            # Record failed close attempt
            self.record_close_attempt(symbol, success=False)

            # Force remove position if we've tried too many times
            # (this prevents infinite retry loops like the SEIUSDT disaster)
            if self.position_close_attempts.get(symbol, 0) >= self.max_close_attempts:
                logger.error(f"Max close attempts reached for {symbol} - FORCING REMOVAL!")
                if symbol in self.positions:
                    del self.positions[symbol]
                self.position_close_attempts[symbol] = 0

            # Re-raise to alert calling code
            raise

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol"""
        return self.positions.get(symbol)

    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())

    def get_portfolio_summary(self) -> Dict:
        """
        Get comprehensive portfolio summary

        Returns:
            Dict with portfolio statistics
        """
        total_value = self.balance
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        portfolio_heat = self.calculate_portfolio_heat()

        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        return {
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'total_pnl': self.balance - self.initial_balance,
            'total_pnl_pct': ((self.balance - self.initial_balance) / self.initial_balance) * 100,
            'unrealized_pnl': total_unrealized,
            'portfolio_value': total_value + total_unrealized,
            'portfolio_heat': portfolio_heat,
            'open_positions': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate
        }

    def reset_daily_stats(self):
        """Reset daily statistics (call at start of new day)"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("Daily statistics reset")

    def display_portfolio(self):
        """Display portfolio status"""
        summary = self.get_portfolio_summary()

        print("\n" + "="*60)
        print("PORTFOLIO SUMMARY")
        print("="*60)
        print(f"Balance: ${summary['balance']:,.2f}")
        print(f"Total PnL: ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)")
        print(f"Unrealized PnL: ${summary['unrealized_pnl']:,.2f}")
        print(f"Portfolio Value: ${summary['portfolio_value']:,.2f}")
        print(f"\nRisk Metrics:")
        print(f"  Portfolio Heat: {summary['portfolio_heat']:.1%}")
        print(f"  Open Positions: {summary['open_positions']}")
        print(f"\nPerformance:")
        print(f"  Daily PnL: ${summary['daily_pnl']:,.2f}")
        print(f"  Daily Trades: {summary['daily_trades']}")
        print(f"  Total Trades: {summary['total_trades']}")
        print(f"  Win Rate: {summary['win_rate']:.1f}%")
        print("="*60 + "\n")


if __name__ == "__main__":
    """Test risk manager"""
    from config import Config

    logger.info("Testing Risk Manager")

    # Initialize risk manager
    rm = RiskManager(initial_balance=Config.INITIAL_BALANCE)

    # Test position sizing
    entry_price = 50000.0
    stop_loss = 48750.0
    atr = 500.0
    volatility = 3.5

    size, value = rm.calculate_position_size(
        'BTCUSDT',
        entry_price,
        stop_loss,
        atr,
        volatility
    )

    print(f"\nPosition Sizing Test:")
    print(f"  Entry: ${entry_price:,.2f}")
    print(f"  Stop Loss: ${stop_loss:,.2f}")
    print(f"  Position Size: {size:.6f} BTC")
    print(f"  Position Value: ${value:,.2f}")

    # Display portfolio
    rm.display_portfolio()
