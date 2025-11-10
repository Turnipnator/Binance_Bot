"""
Grid Trading Strategy
Places buy and sell orders at regular intervals to profit from price oscillations
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from loguru import logger


@dataclass
class GridLevel:
    """Represents a single grid level"""
    price: float
    side: str  # 'BUY' or 'SELL'
    quantity: float
    order_id: Optional[int] = None
    filled: bool = False
    fill_price: Optional[float] = None


class GridTradingStrategy:
    """
    Implements grid trading strategy that profits from ranging markets

    Strategy Overview:
    - Places buy orders at intervals below current price
    - Places sell orders at intervals above current price
    - When a buy order fills, places a sell order at next grid level
    - Profits from price oscillations without predicting direction
    """

    def __init__(
        self,
        symbol: str,
        grid_spacing: float = 0.02,
        num_levels: int = 10,
        allocation: float = 0.5
    ):
        """
        Initialize grid trading strategy

        Args:
            symbol: Trading pair symbol
            grid_spacing: Spacing between grid levels (e.g., 0.02 = 2%)
            num_levels: Number of grid levels above and below
            allocation: Portfolio allocation for this strategy
        """
        self.symbol = symbol
        self.grid_spacing = grid_spacing
        self.num_levels = num_levels
        self.allocation = allocation
        self.grid_levels: List[GridLevel] = []
        self.active = False
        self.base_price = 0.0

        logger.info(
            f"Grid strategy initialized for {symbol}: "
            f"{num_levels} levels, {grid_spacing*100:.1f}% spacing"
        )

    def calculate_grid_levels(self, current_price: float, available_capital: float) -> List[GridLevel]:
        """
        Calculate all grid levels based on current price

        Args:
            current_price: Current market price
            available_capital: Available capital for grid

        Returns:
            List of grid levels
        """
        grid_levels = []
        self.base_price = current_price

        # Calculate capital per grid level
        total_levels = self.num_levels * 2  # Buy and sell sides
        capital_per_level = (available_capital * self.allocation) / self.num_levels

        # Create buy levels (below current price)
        for i in range(1, self.num_levels + 1):
            buy_price = current_price * (1 - self.grid_spacing * i)
            quantity = capital_per_level / buy_price

            grid_levels.append(GridLevel(
                price=buy_price,
                side='BUY',
                quantity=quantity
            ))

        # Create sell levels (above current price)
        for i in range(1, self.num_levels + 1):
            sell_price = current_price * (1 + self.grid_spacing * i)
            quantity = capital_per_level / current_price  # Based on initial capital

            grid_levels.append(GridLevel(
                price=sell_price,
                side='SELL',
                quantity=quantity
            ))

        # Sort by price
        grid_levels.sort(key=lambda x: x.price)

        logger.info(
            f"Grid levels calculated: {len(grid_levels)} levels "
            f"from ${grid_levels[0].price:.2f} to ${grid_levels[-1].price:.2f}"
        )

        return grid_levels

    def setup_grid(self, current_price: float, available_capital: float):
        """
        Setup the initial grid

        Args:
            current_price: Current market price
            available_capital: Available capital
        """
        self.grid_levels = self.calculate_grid_levels(current_price, available_capital)
        self.active = True
        logger.info(f"Grid setup complete for {self.symbol}")

    def get_next_order(self) -> Optional[GridLevel]:
        """
        Get next unfilled grid order

        Returns:
            Next grid level to place order
        """
        for level in self.grid_levels:
            if not level.filled and level.order_id is None:
                return level
        return None

    def mark_level_filled(self, order_id: int, fill_price: float):
        """
        Mark a grid level as filled

        Args:
            order_id: Order ID that was filled
            fill_price: Actual fill price
        """
        for level in self.grid_levels:
            if level.order_id == order_id:
                level.filled = True
                level.fill_price = fill_price
                logger.info(f"Grid level filled: {level.side} @ ${fill_price:.2f}")
                break

    def get_opposite_order(self, filled_level: GridLevel) -> Optional[GridLevel]:
        """
        Get the opposite grid order after a fill

        Args:
            filled_level: Grid level that was just filled

        Returns:
            Opposite grid level to place
        """
        if filled_level.side == 'BUY':
            # After buy, place sell at next higher level
            for level in self.grid_levels:
                if level.price > filled_level.price and level.side == 'SELL' and not level.filled:
                    return level

        elif filled_level.side == 'SELL':
            # After sell, place buy at next lower level
            for level in reversed(self.grid_levels):
                if level.price < filled_level.price and level.side == 'BUY' and not level.filled:
                    return level

        return None

    def should_adjust_grid(self, current_price: float, threshold: float = 0.10) -> bool:
        """
        Check if grid should be adjusted due to price movement

        Args:
            current_price: Current market price
            threshold: Price movement threshold (10% default)

        Returns:
            True if grid should be adjusted
        """
        if not self.base_price:
            return False

        price_change_pct = abs(current_price - self.base_price) / self.base_price

        if price_change_pct > threshold:
            logger.warning(
                f"Price moved {price_change_pct*100:.1f}% from grid base, "
                f"consider adjusting grid"
            )
            return True

        return False

    def adjust_grid(self, current_price: float, available_capital: float):
        """
        Adjust grid to current price level

        Args:
            current_price: Current market price
            available_capital: Available capital
        """
        logger.info(f"Adjusting grid for {self.symbol} to price ${current_price:.2f}")

        # Cancel unfilled orders (would be done in main bot)
        # Reset grid
        self.grid_levels = []
        self.setup_grid(current_price, available_capital)

    def get_grid_statistics(self) -> Dict:
        """
        Get statistics about current grid

        Returns:
            Dict with grid statistics
        """
        filled_buys = [l for l in self.grid_levels if l.side == 'BUY' and l.filled]
        filled_sells = [l for l in self.grid_levels if l.side == 'SELL' and l.filled]

        total_buy_volume = sum(l.quantity * l.fill_price for l in filled_buys if l.fill_price)
        total_sell_volume = sum(l.quantity * l.fill_price for l in filled_sells if l.fill_price)

        return {
            'symbol': self.symbol,
            'total_levels': len(self.grid_levels),
            'filled_levels': len([l for l in self.grid_levels if l.filled]),
            'filled_buys': len(filled_buys),
            'filled_sells': len(filled_sells),
            'total_buy_volume': total_buy_volume,
            'total_sell_volume': total_sell_volume,
            'grid_profit': total_sell_volume - total_buy_volume,
            'base_price': self.base_price,
            'grid_spacing': self.grid_spacing,
            'active': self.active
        }

    def should_enter_position(self, current_price: float, technical_data: Dict) -> Tuple[bool, str]:
        """
        Determine if conditions are right for grid trading

        Args:
            current_price: Current market price
            technical_data: Technical analysis data

        Returns:
            Tuple of (should_enter, reason)
        """
        # Grid trading works best in:
        # 1. Sideways/ranging markets
        # 2. Low to medium volatility
        # 3. Clear support/resistance levels

        trend = technical_data.get('trend', 'sideways')
        volatility = technical_data.get('atr_pct', 0)

        # Prefer sideways markets
        if trend == 'bullish' or trend == 'bearish':
            # Can still use grid in trending markets but with caution
            if volatility > 5.0:
                return False, "High volatility in trending market"

        # Avoid extremely high volatility
        if volatility > 8.0:
            return False, f"Volatility too high: {volatility:.1f}%"

        # Check if we have support/resistance data
        if 'support' in technical_data and 'resistance' in technical_data:
            support = technical_data['support']
            resistance = technical_data['resistance']

            # Calculate range
            price_range_pct = (resistance - support) / support

            # Grid works well in defined ranges
            if price_range_pct < 0.03:
                return False, "Price range too narrow"

            if price_range_pct > 0.25:
                return False, "Price range too wide"

        return True, "Conditions suitable for grid trading"

    def get_risk_parameters(self, current_price: float, atr: float) -> Dict:
        """
        Get risk parameters for grid strategy

        Args:
            current_price: Current market price
            atr: Average True Range

        Returns:
            Dict with stop loss and take profit levels
        """
        # Grid strategy typically has wider stops
        # Stop if price moves beyond grid range

        lowest_grid = min(l.price for l in self.grid_levels)
        highest_grid = max(l.price for l in self.grid_levels)

        # Set stops slightly beyond grid range
        stop_loss = lowest_grid * 0.95
        take_profit = highest_grid * 1.05

        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'grid_range_low': lowest_grid,
            'grid_range_high': highest_grid
        }


class DynamicGridStrategy(GridTradingStrategy):
    """
    Enhanced grid strategy that dynamically adjusts based on volatility
    """

    def __init__(self, symbol: str, grid_spacing: float = 0.02, num_levels: int = 10, allocation: float = 0.5):
        super().__init__(symbol, grid_spacing, num_levels, allocation)
        self.volatility_history = []

    def adjust_spacing_for_volatility(self, volatility_pct: float) -> float:
        """
        Adjust grid spacing based on current volatility

        Args:
            volatility_pct: Current volatility percentage

        Returns:
            Adjusted grid spacing
        """
        base_spacing = self.grid_spacing

        if volatility_pct < 2.0:
            # Low volatility - tighter grid
            return base_spacing * 0.75
        elif volatility_pct > 6.0:
            # High volatility - wider grid
            return base_spacing * 1.5
        else:
            return base_spacing

    def calculate_dynamic_grid(self, current_price: float, available_capital: float,
                              volatility_pct: float) -> List[GridLevel]:
        """
        Calculate grid with dynamic spacing

        Args:
            current_price: Current market price
            available_capital: Available capital
            volatility_pct: Current volatility

        Returns:
            List of grid levels
        """
        # Adjust spacing
        adjusted_spacing = self.adjust_spacing_for_volatility(volatility_pct)

        logger.info(
            f"Dynamic grid spacing: {adjusted_spacing*100:.2f}% "
            f"(volatility: {volatility_pct:.2f}%)"
        )

        # Temporarily update spacing
        original_spacing = self.grid_spacing
        self.grid_spacing = adjusted_spacing

        # Calculate grid
        grid_levels = self.calculate_grid_levels(current_price, available_capital)

        # Restore original spacing
        self.grid_spacing = original_spacing

        return grid_levels


if __name__ == "__main__":
    """Test grid strategy"""
    from config import Config

    logger.info("Testing Grid Trading Strategy")

    # Initialize strategy
    strategy = GridTradingStrategy(
        symbol='BTCUSDT',
        grid_spacing=Config.GRID_SPACING_BTC,
        num_levels=Config.GRID_LEVELS,
        allocation=Config.GRID_ALLOCATION
    )

    # Setup grid
    current_price = 50000.0
    capital = 10000.0

    strategy.setup_grid(current_price, capital)

    # Display grid
    print("\n" + "="*60)
    print("GRID TRADING STRATEGY")
    print("="*60)
    print(f"Symbol: {strategy.symbol}")
    print(f"Base Price: ${strategy.base_price:,.2f}")
    print(f"Grid Spacing: {strategy.grid_spacing*100:.1f}%")
    print(f"Total Levels: {len(strategy.grid_levels)}")
    print("\nGrid Levels:")

    buy_levels = [l for l in strategy.grid_levels if l.side == 'BUY']
    sell_levels = [l for l in strategy.grid_levels if l.side == 'SELL']

    print(f"\nBuy Levels ({len(buy_levels)}):")
    for level in buy_levels[:5]:
        print(f"  ${level.price:,.2f} - {level.quantity:.6f} BTC")

    print(f"\nSell Levels ({len(sell_levels)}):")
    for level in sell_levels[:5]:
        print(f"  ${level.price:,.2f} - {level.quantity:.6f} BTC")

    print("="*60 + "\n")

    # Test dynamic grid
    print("Testing Dynamic Grid Strategy:")
    dynamic_strategy = DynamicGridStrategy(
        symbol='ETHUSDT',
        grid_spacing=0.03,
        num_levels=8
    )

    # Test with different volatility levels
    for vol in [1.5, 4.0, 7.0]:
        spacing = dynamic_strategy.adjust_spacing_for_volatility(vol)
        print(f"  Volatility {vol:.1f}% -> Grid Spacing: {spacing*100:.2f}%")
