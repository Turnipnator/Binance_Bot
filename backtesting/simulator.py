"""
Trade Simulator for Backtesting
Simulates trades using the momentum strategy against historical data.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from loguru import logger
import pandas_ta as ta


@dataclass
class SimulatedTrade:
    """Represents a simulated trade."""
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0
    size_usdt: float = 200.0
    pnl_usdt: float = 0.0
    pnl_percent: float = 0.0
    exit_reason: str = ""
    is_win: bool = False
    highest_price: float = 0.0  # For trailing stop
    lowest_price: float = 0.0   # For shorts


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration_hours: float
    trades: List[SimulatedTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


class TradeSimulator:
    """
    Simulates momentum strategy trades on historical data.
    Replicates the exact logic from momentum_strategy.py.
    """

    # Strategy parameters (matching live bot)
    MOMENTUM_THRESHOLD = 0.70
    TAKE_PROFIT_PERCENT = 1.3      # 1.3% TP
    STOP_LOSS_PERCENT = 5.0        # 5% SL
    VOLUME_THRESHOLD = 1.5         # 1.5x volume required
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30

    def __init__(
        self,
        initial_balance: float = 1000.0,
        position_size_pct: float = 0.20,  # 20% per trade
        enable_shorting: bool = False,
        trading_fee_pct: float = 0.1      # 0.1% fee per trade
    ):
        """
        Initialize trade simulator.

        Args:
            initial_balance: Starting balance in USDT
            position_size_pct: Position size as % of balance
            enable_shorting: Whether to allow short trades
            trading_fee_pct: Trading fee percentage
        """
        self.initial_balance = initial_balance
        self.position_size_pct = position_size_pct
        self.enable_shorting = enable_shorting
        self.trading_fee_pct = trading_fee_pct

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators needed for momentum strategy.

        Args:
            df: OHLCV DataFrame

        Returns:
            DataFrame with indicators added
        """
        df = df.copy()

        # EMAs (8, 21, 50 for EMA stack)
        df['ema_fast'] = ta.ema(df['close'], length=8)
        df['ema_slow'] = ta.ema(df['close'], length=21)
        df['ema_trend'] = ta.ema(df['close'], length=50)

        # RSI
        df['rsi'] = ta.rsi(df['close'], length=14)

        # MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_histogram'] = macd['MACDh_12_26_9']

        # ATR
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # Volume moving average
        df['volume_ma'] = ta.sma(df['volume'], length=20)
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # VWAP (approximation using typical price * volume)
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()

        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bbands['BBU_20_2.0']
        df['bb_lower'] = bbands['BBL_20_2.0']
        df['bb_middle'] = bbands['BBM_20_2.0']

        # Trend classification
        df['trend'] = 'sideways'
        df.loc[(df['ema_fast'] > df['ema_slow']) & (df['ema_slow'] > df['ema_trend']), 'trend'] = 'bullish'
        df.loc[(df['ema_fast'] < df['ema_slow']) & (df['ema_slow'] < df['ema_trend']), 'trend'] = 'bearish'

        return df

    def calculate_momentum_score(self, row: pd.Series, direction: str = 'LONG') -> float:
        """
        Calculate momentum score for a candle.
        Replicates the logic from momentum_strategy.py

        Args:
            row: DataFrame row with indicators
            direction: 'LONG' or 'SHORT'

        Returns:
            Momentum score (0.0 to 1.0)
        """
        price = row['close']
        ema_fast = row['ema_fast']
        ema_slow = row['ema_slow']
        ema_trend = row['ema_trend']
        rsi = row['rsi']
        macd = row['macd']
        macd_signal = row['macd_signal']
        macd_histogram = row['macd_histogram']
        volume_ratio = row['volume_ratio']
        vwap = row['vwap']

        if direction == 'LONG':
            # Trend strength (bullish alignment)
            trend_bullish = (price > ema_fast > ema_slow > ema_trend)
            trend_strength = 0.0
            if trend_bullish and ema_trend > 0:
                ema_separation = ((ema_fast - ema_trend) / ema_trend) * 100
                trend_strength = min(ema_separation / 5.0, 1.0)

            # RSI momentum (50-70 ideal for longs)
            rsi_momentum = 0.0
            if 50 < rsi < 70:
                rsi_momentum = 1.0
            elif 40 < rsi < 50:
                rsi_momentum = 0.5
            elif 70 < rsi < 80:
                rsi_momentum = 0.7

            # MACD momentum
            macd_bullish = macd > macd_signal and macd_histogram > 0
            macd_momentum = 0.0
            if macd_bullish and macd != 0:
                macd_strength = abs(macd_histogram) / abs(macd)
                macd_momentum = min(macd_strength, 1.0)

        else:  # SHORT
            # Trend strength (bearish alignment)
            trend_bearish = (price < ema_fast < ema_slow < ema_trend)
            trend_strength = 0.0
            if trend_bearish and ema_trend > 0:
                ema_separation = ((ema_trend - ema_fast) / ema_trend) * 100
                trend_strength = min(ema_separation / 5.0, 1.0)

            # RSI momentum (30-50 ideal for shorts)
            rsi_momentum = 0.0
            if 30 < rsi < 50:
                rsi_momentum = 1.0
            elif 50 < rsi < 60:
                rsi_momentum = 0.5
            elif 20 < rsi < 30:
                rsi_momentum = 0.7

            # MACD momentum (bearish)
            macd_bearish = macd < macd_signal and macd_histogram < 0
            macd_momentum = 0.0
            if macd_bearish and macd != 0:
                macd_strength = abs(macd_histogram) / abs(macd)
                macd_momentum = min(macd_strength, 1.0)

        # Volume momentum
        volume_momentum = min(volume_ratio / 2.0, 1.0) if volume_ratio else 0.0

        # VWAP strength
        if direction == 'LONG':
            vwap_strength = 1.0 if price > vwap else 0.3
        else:
            vwap_strength = 1.0 if price < vwap else 0.3

        # Overall score
        momentum_score = (
            trend_strength * 0.35 +
            rsi_momentum * 0.25 +
            macd_momentum * 0.20 +
            volume_momentum * 0.10 +
            vwap_strength * 0.10
        )

        return momentum_score

    def check_entry_signal(
        self,
        row: pd.Series,
        direction: str = 'LONG'
    ) -> Tuple[bool, float]:
        """
        Check if entry conditions are met.

        Args:
            row: DataFrame row with indicators
            direction: 'LONG' or 'SHORT'

        Returns:
            Tuple of (should_enter, momentum_score)
        """
        momentum_score = self.calculate_momentum_score(row, direction)

        # Check momentum threshold
        if momentum_score < self.MOMENTUM_THRESHOLD:
            return False, momentum_score

        # Check trend alignment
        trend = row['trend']
        if direction == 'LONG' and trend != 'bullish':
            return False, momentum_score
        if direction == 'SHORT' and trend != 'bearish':
            return False, momentum_score

        # Check volume
        if row['volume_ratio'] < self.VOLUME_THRESHOLD:
            return False, momentum_score

        # Check RSI
        rsi = row['rsi']
        if direction == 'LONG' and rsi > self.RSI_OVERBOUGHT:
            return False, momentum_score
        if direction == 'SHORT' and rsi < self.RSI_OVERSOLD:
            return False, momentum_score

        return True, momentum_score

    def simulate(
        self,
        df: pd.DataFrame,
        symbol: str = 'BTCUSDT'
    ) -> BacktestResult:
        """
        Run backtest simulation on historical data.

        Args:
            df: OHLCV DataFrame
            symbol: Trading pair symbol

        Returns:
            BacktestResult with all metrics
        """
        # Calculate indicators
        df = self.calculate_indicators(df)

        # Drop rows with NaN
        df = df.dropna()

        if len(df) < 50:
            logger.warning(f"Insufficient data for backtesting: {len(df)} rows")
            return BacktestResult(
                symbol=symbol,
                start_date=df.index[0],
                end_date=df.index[-1],
                initial_balance=self.initial_balance,
                final_balance=self.initial_balance,
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, total_pnl=0, total_pnl_percent=0,
                max_drawdown=0, max_drawdown_percent=0,
                sharpe_ratio=0, profit_factor=0,
                avg_win=0, avg_loss=0, largest_win=0, largest_loss=0,
                avg_trade_duration_hours=0, trades=[], equity_curve=[]
            )

        # Initialize state
        balance = self.initial_balance
        trades: List[SimulatedTrade] = []
        equity_curve = [balance]
        current_trade: Optional[SimulatedTrade] = None
        peak_balance = balance

        # Iterate through candles
        for i, (timestamp, row) in enumerate(df.iterrows()):
            price = row['close']
            high = row['high']
            low = row['low']

            # If in a trade, check exit conditions
            if current_trade:
                # Update highest/lowest for trailing stop
                if current_trade.side == 'LONG':
                    if high > current_trade.highest_price:
                        current_trade.highest_price = high
                else:
                    if low < current_trade.lowest_price:
                        current_trade.lowest_price = low

                exit_price = None
                exit_reason = ""

                if current_trade.side == 'LONG':
                    # Check stop loss (5%)
                    if low <= current_trade.stop_loss:
                        exit_price = current_trade.stop_loss
                        exit_reason = "stop_loss"

                    # Check take profit (1.3%)
                    elif high >= current_trade.take_profit:
                        exit_price = current_trade.take_profit
                        exit_reason = "take_profit"

                else:  # SHORT
                    # Check stop loss
                    if high >= current_trade.stop_loss:
                        exit_price = current_trade.stop_loss
                        exit_reason = "stop_loss"

                    # Check take profit
                    elif low <= current_trade.take_profit:
                        exit_price = current_trade.take_profit
                        exit_reason = "take_profit"

                # Exit if triggered
                if exit_price:
                    current_trade.exit_time = timestamp
                    current_trade.exit_price = exit_price
                    current_trade.exit_reason = exit_reason

                    # Calculate P&L
                    if current_trade.side == 'LONG':
                        pnl_pct = ((exit_price - current_trade.entry_price) / current_trade.entry_price) * 100
                    else:
                        pnl_pct = ((current_trade.entry_price - exit_price) / current_trade.entry_price) * 100

                    # Apply fees
                    pnl_pct -= self.trading_fee_pct * 2  # Entry + exit fee

                    current_trade.pnl_percent = pnl_pct
                    current_trade.pnl_usdt = (pnl_pct / 100) * current_trade.size_usdt
                    current_trade.is_win = pnl_pct > 0

                    # Update balance
                    balance += current_trade.pnl_usdt

                    trades.append(current_trade)
                    current_trade = None

            # If not in a trade, check entry signals
            else:
                # Check LONG entry
                should_enter_long, score_long = self.check_entry_signal(row, 'LONG')

                if should_enter_long:
                    entry_price = price
                    position_size = balance * self.position_size_pct

                    current_trade = SimulatedTrade(
                        symbol=symbol,
                        side='LONG',
                        entry_time=timestamp,
                        entry_price=entry_price,
                        stop_loss=entry_price * (1 - self.STOP_LOSS_PERCENT / 100),
                        take_profit=entry_price * (1 + self.TAKE_PROFIT_PERCENT / 100),
                        size_usdt=position_size,
                        highest_price=entry_price,
                        lowest_price=entry_price
                    )

                # Check SHORT entry (if enabled)
                elif self.enable_shorting:
                    should_enter_short, score_short = self.check_entry_signal(row, 'SHORT')

                    if should_enter_short:
                        entry_price = price
                        position_size = balance * self.position_size_pct

                        current_trade = SimulatedTrade(
                            symbol=symbol,
                            side='SHORT',
                            entry_time=timestamp,
                            entry_price=entry_price,
                            stop_loss=entry_price * (1 + self.STOP_LOSS_PERCENT / 100),
                            take_profit=entry_price * (1 - self.TAKE_PROFIT_PERCENT / 100),
                            size_usdt=position_size,
                            highest_price=entry_price,
                            lowest_price=entry_price
                        )

            # Track equity
            equity_curve.append(balance)

        # Calculate metrics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.is_win)
        losing_trades = total_trades - winning_trades

        total_pnl = balance - self.initial_balance
        total_pnl_percent = (total_pnl / self.initial_balance) * 100

        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Average win/loss
        wins = [t.pnl_usdt for t in trades if t.is_win]
        losses = [t.pnl_usdt for t in trades if not t.is_win]

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Max drawdown
        equity = np.array(equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = peak - equity
        max_drawdown = np.max(drawdown)
        max_drawdown_percent = (max_drawdown / np.max(peak)) * 100 if np.max(peak) > 0 else 0

        # Sharpe ratio (simplified, assuming risk-free rate = 0)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0

        # Average trade duration
        durations = []
        for t in trades:
            if t.exit_time:
                duration = (t.exit_time - t.entry_time).total_seconds() / 3600
                durations.append(duration)
        avg_duration = np.mean(durations) if durations else 0

        return BacktestResult(
            symbol=symbol,
            start_date=df.index[0],
            end_date=df.index[-1],
            initial_balance=self.initial_balance,
            final_balance=balance,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration_hours=avg_duration,
            trades=trades,
            equity_curve=equity_curve
        )


if __name__ == '__main__':
    # Test the simulator
    from data_fetcher import DataFetcher

    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv('BTCUSDT', interval='1h', days=90)

    simulator = TradeSimulator(
        initial_balance=1000,
        enable_shorting=False  # LONG only like the live bot
    )

    result = simulator.simulate(df, 'BTCUSDT')

    print(f"\n{'='*60}")
    print("BACKTEST RESULTS - BTCUSDT (LONG ONLY)")
    print(f"{'='*60}")
    print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
    print(f"\nPerformance:")
    print(f"  Total P&L: ${result.total_pnl:.2f} ({result.total_pnl_percent:+.2f}%)")
    print(f"  Win Rate: {result.win_rate:.1f}%")
    print(f"  Total Trades: {result.total_trades}")
    print(f"  Winners: {result.winning_trades} | Losers: {result.losing_trades}")
    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown: ${result.max_drawdown:.2f} ({result.max_drawdown_percent:.1f}%)")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  Profit Factor: {result.profit_factor:.2f}")
    print(f"\nTrade Stats:")
    print(f"  Avg Win: ${result.avg_win:.2f}")
    print(f"  Avg Loss: ${result.avg_loss:.2f}")
    print(f"  Largest Win: ${result.largest_win:.2f}")
    print(f"  Largest Loss: ${result.largest_loss:.2f}")
    print(f"  Avg Duration: {result.avg_trade_duration_hours:.1f} hours")
    print(f"{'='*60}")
