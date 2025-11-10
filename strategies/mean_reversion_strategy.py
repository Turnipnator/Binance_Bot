"""
Mean Reversion Strategy
Exploits price extremes and volatility spikes to profit from returns to mean
"""
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class ReversionSignal:
    """Represents a mean reversion trading signal"""
    symbol: str
    side: str
    strength: float
    entry_price: float
    mean_price: float
    stop_loss: float
    take_profit: float
    reversion_distance: float
    confidence: float


class MeanReversionStrategy:
    """
    Mean reversion strategy that trades oversold/overbought conditions

    Strategy Overview:
    - Identifies price extremes using Bollinger Bands, RSI, Stochastic
    - Enters when price deviates significantly from mean
    - Exits when price returns close to mean or reversal fails
    - Works best in ranging, non-trending markets
    """

    def __init__(self, symbol: str, allocation: float = 0.2):
        """
        Initialize mean reversion strategy

        Args:
            symbol: Trading pair symbol
            allocation: Portfolio allocation for this strategy
        """
        self.symbol = symbol
        self.allocation = allocation
        self.in_position = False
        self.entry_price = 0.0
        self.mean_price = 0.0

        logger.info(f"Mean reversion strategy initialized for {symbol}")

    def calculate_price_deviation(self, technical_data: Dict) -> Dict:
        """
        Calculate how far price has deviated from mean

        Args:
            technical_data: Technical analysis data

        Returns:
            Dict with deviation metrics
        """
        price = technical_data.get('price', 0)
        bb_upper = technical_data.get('bb_upper', 0)
        bb_lower = technical_data.get('bb_lower', 0)
        bb_middle = technical_data.get('bb_middle', 0)
        vwap = technical_data.get('vwap', price)

        # Calculate Bollinger Band position (0 = lower band, 1 = upper band)
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_position = (price - bb_lower) / bb_range
        else:
            bb_position = 0.5

        # Distance from middle band
        distance_from_mean_pct = ((price - bb_middle) / bb_middle) * 100 if bb_middle > 0 else 0

        # Distance from VWAP
        distance_from_vwap_pct = ((price - vwap) / vwap) * 100 if vwap > 0 else 0

        # Determine if oversold or overbought
        is_oversold = bb_position < 0.1  # Below 10% of BB range
        is_overbought = bb_position > 0.9  # Above 90% of BB range

        return {
            'bb_position': bb_position,
            'distance_from_mean_pct': distance_from_mean_pct,
            'distance_from_vwap_pct': distance_from_vwap_pct,
            'is_oversold': is_oversold,
            'is_overbought': is_overbought,
            'mean_price': bb_middle
        }

    def analyze_reversion_opportunity(self, technical_data: Dict) -> Dict:
        """
        Analyze mean reversion opportunity

        Args:
            technical_data: Technical analysis data

        Returns:
            Dict with reversion analysis
        """
        deviation = self.calculate_price_deviation(technical_data)

        # RSI oversold/overbought
        rsi = technical_data.get('rsi', 50)
        rsi_oversold = rsi < 30
        rsi_overbought = rsi > 70

        # Stochastic oversold/overbought
        stoch_k = technical_data.get('stoch_k', 50)
        stoch_d = technical_data.get('stoch_d', 50)
        stoch_oversold = stoch_k < 20 and stoch_d < 20
        stoch_overbought = stoch_k > 80 and stoch_d > 80

        # Volume analysis (high volume on extremes is better)
        volume_ratio = technical_data.get('volume_ratio', 1.0)
        volume_confirmation = volume_ratio > 1.2

        # Calculate reversion score for long (buy oversold)
        long_score = 0.0
        if deviation['is_oversold']:
            long_score += 0.3
        if rsi_oversold:
            long_score += 0.3
        if stoch_oversold:
            long_score += 0.2
        if volume_confirmation:
            long_score += 0.2

        # Calculate reversion score for short (sell overbought)
        short_score = 0.0
        if deviation['is_overbought']:
            short_score += 0.3
        if rsi_overbought:
            short_score += 0.3
        if stoch_overbought:
            short_score += 0.2
        if volume_confirmation:
            short_score += 0.2

        return {
            'long_score': long_score,
            'short_score': short_score,
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': rsi_overbought,
            'stoch_oversold': stoch_oversold,
            'stoch_overbought': stoch_overbought,
            'volume_confirmation': volume_confirmation,
            'deviation': deviation
        }

    def should_enter_long(self, technical_data: Dict, min_score: float = 0.6) -> Tuple[bool, float, Dict]:
        """
        Determine if should enter long (buy oversold)

        Args:
            technical_data: Technical analysis data
            min_score: Minimum reversion score required

        Returns:
            Tuple of (should_enter, confidence, reversion_data)
        """
        if self.in_position:
            return False, 0.0, {}

        reversion = self.analyze_reversion_opportunity(technical_data)
        long_score = reversion['long_score']

        if long_score < min_score:
            return False, long_score, reversion

        # Additional filter: avoid in strong downtrends
        trend = technical_data.get('trend', 'sideways')
        if trend == 'bearish':
            ema_fast = technical_data.get('ema_fast', 0)
            ema_trend = technical_data.get('ema_trend', 0)
            # Only allow if not in severe downtrend
            if ema_fast < ema_trend * 0.97:  # More than 3% below trend EMA
                logger.debug("Strong downtrend, avoiding long")
                return False, long_score, reversion

        confidence = long_score
        logger.info(f"Mean reversion LONG signal: score={long_score:.2f}")

        return True, confidence, reversion

    def should_exit_long(self, technical_data: Dict, current_price: float) -> Tuple[bool, str]:
        """
        Determine if should exit long position

        Args:
            technical_data: Technical analysis data
            current_price: Current market price

        Returns:
            Tuple of (should_exit, reason)
        """
        if not self.in_position:
            return False, "No position"

        deviation = self.calculate_price_deviation(technical_data)

        # Exit when price returns near mean
        if abs(deviation['distance_from_mean_pct']) < 0.5:
            return True, "Price returned to mean"

        # Exit if RSI reaches neutral/overbought
        rsi = technical_data.get('rsi', 50)
        if rsi > 60:
            return True, f"RSI recovered: {rsi:.1f}"

        # Exit if BB position normalized
        if 0.4 < deviation['bb_position'] < 0.6:
            return True, "BB position normalized"

        # Exit if Stochastic shows overbought
        stoch_k = technical_data.get('stoch_k', 50)
        if stoch_k > 75:
            return True, f"Stochastic overbought: {stoch_k:.1f}"

        return False, "No exit signal"

    def calculate_stop_loss(self, entry_price: float, atr: float, side: str = 'long') -> float:
        """
        Calculate stop loss for mean reversion trade

        Args:
            entry_price: Entry price
            atr: Average True Range
            side: 'long' or 'short'

        Returns:
            Stop loss price
        """
        # Mean reversion uses tighter stops
        stop_multiplier = 2.0

        if side == 'long':
            stop_loss = entry_price - (atr * stop_multiplier)
        else:
            stop_loss = entry_price + (atr * stop_multiplier)

        return stop_loss

    def calculate_take_profit(self, entry_price: float, mean_price: float, side: str = 'long') -> float:
        """
        Calculate take profit targeting return to mean

        Args:
            entry_price: Entry price
            mean_price: Mean/target price
            side: 'long' or 'short'

        Returns:
            Take profit price
        """
        # Target is slightly before mean (80% of the way)
        distance_to_mean = abs(mean_price - entry_price)

        if side == 'long':
            take_profit = entry_price + (distance_to_mean * 0.8)
        else:
            take_profit = entry_price - (distance_to_mean * 0.8)

        return take_profit

    def is_suitable_market_condition(self, technical_data: Dict) -> Tuple[bool, str]:
        """
        Check if market conditions are suitable for mean reversion

        Args:
            technical_data: Technical analysis data

        Returns:
            Tuple of (is_suitable, reason)
        """
        # Mean reversion works best in:
        # 1. Ranging/sideways markets
        # 2. Moderate volatility
        # 3. Clear support/resistance

        trend = technical_data.get('trend', 'sideways')
        volatility = technical_data.get('atr_pct', 0)

        # Prefer sideways markets
        if trend == 'sideways':
            return True, "Sideways market ideal"

        # Can work in trending but not extreme trends
        if trend in ['bullish', 'bearish']:
            if volatility > 7.0:
                return False, "Too volatile for mean reversion"

            # Check if trend is strong
            ema_fast = technical_data.get('ema_fast', 0)
            ema_slow = technical_data.get('ema_slow', 0)
            ema_trend = technical_data.get('ema_trend', 0)

            ema_separation = abs((ema_fast - ema_trend) / ema_trend) * 100

            if ema_separation > 5.0:
                return False, "Trend too strong"

            return True, "Weak trend acceptable"

        return True, "Conditions suitable"

    def enter_position(self, entry_price: float, mean_price: float):
        """Mark position as entered"""
        self.in_position = True
        self.entry_price = entry_price
        self.mean_price = mean_price
        logger.info(f"Mean reversion position entered at ${entry_price:.2f}, target mean: ${mean_price:.2f}")

    def exit_position(self, exit_price: float) -> float:
        """
        Mark position as exited and calculate PnL

        Args:
            exit_price: Exit price

        Returns:
            PnL percentage
        """
        if not self.in_position:
            return 0.0

        pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100

        self.in_position = False
        self.entry_price = 0.0
        self.mean_price = 0.0

        logger.info(f"Mean reversion position exited at ${exit_price:.2f}, PnL: {pnl_pct:.2f}%")

        return pnl_pct

    def generate_signal(self, technical_data: Dict) -> Optional[ReversionSignal]:
        """
        Generate trading signal

        Args:
            technical_data: Technical analysis data

        Returns:
            ReversionSignal or None
        """
        # Check market conditions
        is_suitable, reason = self.is_suitable_market_condition(technical_data)
        if not is_suitable:
            logger.debug(f"Market not suitable: {reason}")
            return None

        # Check for long opportunity
        should_enter, confidence, reversion_data = self.should_enter_long(technical_data)

        if not should_enter:
            return None

        price = technical_data.get('price', 0)
        atr = technical_data.get('atr', 0)
        mean_price = reversion_data['deviation']['mean_price']

        stop_loss = self.calculate_stop_loss(price, atr, 'long')
        take_profit = self.calculate_take_profit(price, mean_price, 'long')

        # Calculate reversion distance
        reversion_distance = abs(price - mean_price) / mean_price

        signal = ReversionSignal(
            symbol=self.symbol,
            side='BUY',
            strength=reversion_data['long_score'],
            entry_price=price,
            mean_price=mean_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reversion_distance=reversion_distance,
            confidence=confidence
        )

        return signal


class BollingerReversionStrategy(MeanReversionStrategy):
    """
    Enhanced mean reversion focused on Bollinger Band extremes
    """

    def __init__(self, symbol: str, allocation: float = 0.2):
        super().__init__(symbol, allocation)
        self.bb_touch_count = 0

    def detect_bb_squeeze(self, technical_data: Dict) -> bool:
        """
        Detect Bollinger Band squeeze (low volatility period)

        Args:
            technical_data: Technical analysis data

        Returns:
            True if in squeeze
        """
        bb_width = technical_data.get('bb_width', 0)

        # BB width typically ranges from 0.01 to 0.10
        # Squeeze when < 0.02
        if bb_width < 0.02:
            logger.info(f"BB Squeeze detected: width={bb_width:.4f}")
            return True

        return False


if __name__ == "__main__":
    """Test mean reversion strategy"""
    from config import Config

    logger.info("Testing Mean Reversion Strategy")

    strategy = MeanReversionStrategy('ETHUSDT', allocation=Config.MEAN_REVERSION_ALLOCATION)

    # Test with oversold conditions
    test_data = {
        'price': 2850.0,
        'bb_upper': 2950.0,
        'bb_middle': 2900.0,
        'bb_lower': 2850.0,
        'bb_width': 0.034,
        'vwap': 2900.0,
        'rsi': 28.0,
        'stoch_k': 18.0,
        'stoch_d': 22.0,
        'volume_ratio': 1.5,
        'atr': 50.0,
        'atr_pct': 1.75,
        'trend': 'sideways',
        'ema_fast': 2880.0,
        'ema_slow': 2890.0,
        'ema_trend': 2870.0
    }

    print("\n" + "="*60)
    print("MEAN REVERSION STRATEGY TEST")
    print("="*60)

    # Analyze deviation
    deviation = strategy.calculate_price_deviation(test_data)
    print(f"\nPrice Deviation Analysis:")
    print(f"  BB Position: {deviation['bb_position']:.2f} (0=lower, 1=upper)")
    print(f"  Distance from Mean: {deviation['distance_from_mean_pct']:.2f}%")
    print(f"  Is Oversold: {deviation['is_oversold']}")
    print(f"  Is Overbought: {deviation['is_overbought']}")

    # Analyze reversion
    reversion = strategy.analyze_reversion_opportunity(test_data)
    print(f"\nReversion Opportunity:")
    print(f"  Long Score: {reversion['long_score']:.2f}")
    print(f"  Short Score: {reversion['short_score']:.2f}")
    print(f"  RSI Oversold: {reversion['rsi_oversold']}")
    print(f"  Stoch Oversold: {reversion['stoch_oversold']}")
    print(f"  Volume Confirmation: {reversion['volume_confirmation']}")

    # Check entry
    should_enter, confidence, _ = strategy.should_enter_long(test_data)
    print(f"\nEntry Signal:")
    print(f"  Should Enter: {should_enter}")
    print(f"  Confidence: {confidence:.2f}")

    if should_enter:
        signal = strategy.generate_signal(test_data)
        if signal:
            print(f"\nSignal Generated:")
            print(f"  Entry: ${signal.entry_price:,.2f}")
            print(f"  Mean Target: ${signal.mean_price:,.2f}")
            print(f"  Take Profit: ${signal.take_profit:,.2f}")
            print(f"  Stop Loss: ${signal.stop_loss:,.2f}")
            print(f"  Reversion Distance: {signal.reversion_distance*100:.2f}%")
            print(f"  Risk: ${signal.entry_price - signal.stop_loss:,.2f}")
            print(f"  Reward: ${signal.take_profit - signal.entry_price:,.2f}")

    print("="*60 + "\n")
