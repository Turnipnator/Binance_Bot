"""
Momentum Trading Strategy
Captures trending moves with multi-indicator confirmation
"""
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class MomentumSignal:
    """Represents a momentum trading signal"""
    symbol: str
    side: str  # 'BUY' or 'SELL'
    strength: float  # 0.0 to 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    indicators: Dict
    confidence: float


class MomentumStrategy:
    """
    Momentum strategy that identifies and trades strong trends

    Strategy Overview:
    - Identifies strong directional moves using multiple indicators
    - Enters when trend is confirmed by EMA alignment, MACD, RSI
    - Uses volume confirmation to filter false signals
    - Exits when momentum weakens or reversal signals appear
    """

    def __init__(self, symbol: str, allocation: float = 0.3, client=None, risk_manager=None):
        """
        Initialize momentum strategy

        Args:
            symbol: Trading pair symbol
            allocation: Portfolio allocation for this strategy
            client: Binance client for fetching higher timeframe data
            risk_manager: Risk manager instance for stop loss calculations
        """
        self.symbol = symbol
        self.allocation = allocation
        self.in_position = False
        self.entry_price = 0.0
        self.highest_price = 0.0
        self.client = client  # Store client for 4H data fetching
        self.risk_manager = risk_manager

        logger.info(f"Momentum strategy initialized for {symbol}")

    def analyze_momentum(self, technical_data: Dict) -> Dict:
        """
        Analyze momentum strength using multiple indicators

        Args:
            technical_data: Technical analysis data

        Returns:
            Dict with momentum analysis
        """
        indicators = technical_data

        # 1. Trend Analysis (EMA Alignment)
        ema_fast = indicators.get('ema_fast') or 0
        ema_slow = indicators.get('ema_slow') or 0
        ema_trend = indicators.get('ema_trend') or 0
        price = indicators.get('price') or 0

        # Check for strong uptrend (handle None values)
        try:
            trend_bullish = (
                price > ema_fast > ema_slow > ema_trend and
                all([price, ema_fast, ema_slow, ema_trend])  # Ensure no zeros/None
            )
        except (TypeError, ValueError):
            trend_bullish = False

        trend_strength = 0.0
        if trend_bullish:
            # Calculate strength based on EMA separation
            ema_separation = ((ema_fast - ema_trend) / ema_trend) * 100
            trend_strength = min(ema_separation / 5.0, 1.0)  # Normalize to 0-1

        # 2. Momentum Indicators
        rsi = indicators.get('rsi') or 50
        macd = indicators.get('macd') or 0
        macd_signal = indicators.get('macd_signal') or 0
        macd_histogram = indicators.get('macd_histogram') or 0

        # RSI momentum (ideally 50-70 for bullish momentum)
        rsi_momentum = 0.0
        try:
            if 50 < rsi < 70:
                rsi_momentum = 1.0
            elif 40 < rsi < 50:
                rsi_momentum = 0.5
            elif 70 < rsi < 80:
                rsi_momentum = 0.7  # Still bullish but entering overbought
        except (TypeError, ValueError):
            rsi_momentum = 0.0

        # MACD momentum (handle None values)
        try:
            macd_bullish = macd > macd_signal and macd_histogram > 0
            macd_strength = abs(macd_histogram) / abs(macd) if macd != 0 else 0
            macd_momentum = min(macd_strength, 1.0) if macd_bullish else 0.0
        except (TypeError, ValueError, ZeroDivisionError):
            macd_momentum = 0.0

        # 3. Volume Confirmation
        volume_ratio = indicators.get('volume_ratio') or 1.0
        try:
            volume_momentum = min(volume_ratio / 2.0, 1.0)  # Normalize
        except (TypeError, ValueError):
            volume_momentum = 0.0

        # 4. Price vs VWAP (handle None values)
        vwap = indicators.get('vwap') or price
        try:
            vwap_strength = 1.0 if price > vwap else 0.3
        except (TypeError, ValueError):
            vwap_strength = 0.3

        # Calculate overall momentum score
        momentum_score = (
            trend_strength * 0.35 +
            rsi_momentum * 0.25 +
            macd_momentum * 0.20 +
            volume_momentum * 0.10 +
            vwap_strength * 0.10
        )

        return {
            'momentum_score': momentum_score,
            'trend_bullish': trend_bullish,
            'trend_strength': trend_strength,
            'rsi_momentum': rsi_momentum,
            'macd_momentum': macd_momentum,
            'volume_momentum': volume_momentum,
            'vwap_strength': vwap_strength
        }

    def check_higher_timeframe_confirmation(self) -> Tuple[bool, str]:
        """
        Check 1H timeframe for trend confirmation.
        Requires price to be above the 1H EMA50 - filters out entries
        during bearish markets where brief 5m impulses trigger false signals.

        Returns:
            Tuple of (confirmed, reason)
        """
        if not self.client:
            logger.warning("No client available for 1H confirmation, skipping check")
            return True, "No client (bypassed)"

        try:
            import pandas as pd
            import pandas_ta as ta

            # Fetch 1H klines (last 100 candles = ~4 days)
            klines = self.client.get_historical_klines(
                symbol=self.symbol,
                interval='1h',
                limit=100
            )

            if not klines or len(klines) < 55:
                logger.warning(f"Insufficient 1H data for {self.symbol}: {len(klines) if klines else 0} candles")
                return True, "Insufficient 1H data (bypassed)"

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            # Calculate 1H EMA50
            df['ema50'] = ta.ema(df['close'], length=50)

            latest = df.iloc[-1]
            current_price = latest['close']
            ema50 = latest['ema50']

            if pd.isna(ema50):
                logger.debug(f"1H EMA50 is NaN for {self.symbol}, bypassing check")
                return True, "1H EMA50 not ready (bypassed)"

            if current_price > ema50:
                pct_above = ((current_price - ema50) / ema50) * 100
                logger.info(f"✅ 1H confirmation: {self.symbol} price ${current_price:.2f} above 1H EMA50 ${ema50:.2f} (+{pct_above:.1f}%)")
                return True, "1H trend confirmed"
            else:
                pct_below = ((ema50 - current_price) / ema50) * 100
                logger.info(f"❌ 1H rejection: {self.symbol} price ${current_price:.2f} below 1H EMA50 ${ema50:.2f} (-{pct_below:.1f}%)")
                return False, f"1H price below EMA50 (-{pct_below:.1f}%)"

        except Exception as e:
            logger.error(f"Error checking 1H confirmation for {self.symbol}: {e}")
            return True, f"1H check error (bypassed): {str(e)[:50]}"

    def should_enter_long(self, technical_data: Dict, min_score: float = 0.70) -> Tuple[bool, float, Dict]:
        """
        Determine if should enter long position

        Args:
            technical_data: Technical analysis data
            min_score: Minimum momentum score required

        Returns:
            Tuple of (should_enter, confidence, momentum_data)
        """
        from config import Config

        momentum_data = self.analyze_momentum(technical_data)
        momentum_score = momentum_data['momentum_score']

        # Check if already in position
        if self.in_position:
            return False, 0.0, momentum_data

        # Check minimum score
        if momentum_score < min_score:
            logger.debug(f"Momentum score too low: {momentum_score:.2f} < {min_score}")
            return False, momentum_score, momentum_data

        # Additional filters
        rsi = technical_data.get('rsi', 50)
        if rsi > Config.RSI_OVERBOUGHT:
            logger.debug(f"RSI overbought: {rsi:.1f}")
            return False, momentum_score, momentum_data

        # CRITICAL: TREND FILTER - Require BULLISH trend
        # Only trade when trend is clearly bullish - reject sideways AND bearish
        # This prevents weak signals in ranging or downtrending markets
        trend = technical_data.get('trend', 'sideways')
        if trend != 'bullish':
            logger.info(f"❌ Trend filter: {self.symbol} trend is {trend.upper()} - only BULLISH allowed (score was {momentum_score:.2f})")
            return False, momentum_score, momentum_data

        # Check trend
        if not momentum_data['trend_bullish']:
            logger.debug("Trend not bullish")
            return False, momentum_score, momentum_data

        # CRITICAL: Check volume BEFORE entering
        # Require 1.5x volume surge AND sustained volume over last 3 candles
        volume_ratio = technical_data.get('volume_ratio', 1.0)
        vol_min3 = technical_data.get('vol_min3', 0.0)
        if volume_ratio < 1.5:
            logger.debug(f"Insufficient volume for entry: {volume_ratio:.2f}x (need >= 1.5x)")
            return False, momentum_score, momentum_data
        if vol_min3 < 1.5:
            logger.debug(f"Insufficient sustained volume: vol_min3={vol_min3:.2f}x (need >= 1.5x sustained)")
            return False, momentum_score, momentum_data

        # 1H timeframe confirmation - reject entries when price is below 1H EMA50
        # Prevents entering on brief 5m bullish impulses in a larger bearish trend
        htf_confirmed, htf_reason = self.check_higher_timeframe_confirmation()
        if not htf_confirmed:
            logger.info(f"1H filter rejection for {self.symbol}: {htf_reason} (score was {momentum_score:.2f})")
            return False, momentum_score, momentum_data

        # All conditions met
        confidence = momentum_score
        logger.info(f"✅ Momentum entry signal: score={momentum_score:.2f}, confidence={confidence:.2f}, volume={volume_ratio:.2f}x, vol_min3={vol_min3:.2f}x")

        return True, confidence, momentum_data

    def should_exit_long(self, technical_data: Dict, current_price: float) -> Tuple[bool, str]:
        """
        Determine if should exit long position

        Args:
            technical_data: Technical analysis data
            current_price: Current market price

        Returns:
            Tuple of (should_exit, reason)
        """
        from config import Config

        if not self.in_position:
            return False, "No position"

        # Exit condition 1: RSI overbought
        rsi = technical_data.get('rsi', 50)
        if rsi > 75:
            return True, f"RSI overbought: {rsi:.1f}"

        # Exit condition 2: MACD bearish crossover
        macd = technical_data.get('macd', 0)
        macd_signal = technical_data.get('macd_signal', 0)
        if macd < macd_signal:
            return True, "MACD bearish crossover"

        # Exit condition 3: EMA crossover (fast below slow)
        ema_fast = technical_data.get('ema_fast', 0)
        ema_slow = technical_data.get('ema_slow', 0)
        if ema_fast < ema_slow:
            return True, "EMA bearish crossover"

        # Exit condition 4: Momentum weakening significantly
        momentum_data = self.analyze_momentum(technical_data)
        if momentum_data['momentum_score'] < 0.3:
            return True, f"Momentum weakened: {momentum_data['momentum_score']:.2f}"

        # Exit condition 5: Volume drying up
        volume_ratio = technical_data.get('volume_ratio', 1.0)
        if volume_ratio < 0.5:
            return True, f"Low volume: {volume_ratio:.2f}x"

        return False, "No exit signal"

    def calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        """
        Calculate stop loss for momentum trade

        Args:
            entry_price: Entry price
            atr: Average True Range

        Returns:
            Stop loss price
        """
        # Use risk manager's stop loss (per-symbol for meme coins)
        if self.risk_manager:
            stop_loss = self.risk_manager.calculate_atr_stop_loss(entry_price, atr, 'long', symbol=self.symbol)
            logger.debug(f"Using per-symbol stop from risk manager: {stop_loss:.8f}")
            return stop_loss

        # Fallback to ATR-based stop (shouldn't happen in production)
        from config import Config
        stop_multiplier = Config.ATR_STOP_MULTIPLIER * 0.8  # 20% tighter than default
        stop_loss = entry_price - (atr * stop_multiplier)

        logger.warning(f"Risk manager not available, using ATR-based stop: {stop_loss:.8f}")
        return stop_loss

    def calculate_take_profit(self, entry_price: float, stop_loss: float, risk_reward: float = 3.0) -> float:
        """
        Calculate take profit at 1.3% above entry price.
        Lock in small gains quickly rather than hoping for big moves.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price (unused, kept for compatibility)
            risk_reward: Risk-reward ratio (unused, kept for compatibility)

        Returns:
            Take profit price (1.3% above entry)
        """
        # 1.3% take profit - lock in gains quickly
        take_profit = entry_price * 1.013

        return take_profit

    def update_trailing_stop(self, current_price: float, atr: float) -> Optional[float]:
        """
        Update trailing stop for momentum trade

        Args:
            current_price: Current market price
            atr: Average True Range

        Returns:
            New trailing stop price or None
        """
        if not self.in_position:
            return None

        # Update highest price
        if current_price > self.highest_price:
            self.highest_price = current_price

        # Calculate trailing stop
        trailing_distance = atr * 1.5
        new_stop = self.highest_price - trailing_distance

        return new_stop

    def enter_position(self, entry_price: float):
        """Mark position as entered"""
        self.in_position = True
        self.entry_price = entry_price
        self.highest_price = entry_price
        logger.info(f"Momentum position entered at ${entry_price:.2f}")

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
        self.highest_price = 0.0

        logger.info(f"Momentum position exited at ${exit_price:.2f}, PnL: {pnl_pct:.2f}%")

        return pnl_pct

    def generate_signal(self, technical_data: Dict) -> Optional[MomentumSignal]:
        """
        Generate trading signal

        Args:
            technical_data: Technical analysis data

        Returns:
            MomentumSignal or None
        """
        should_enter, confidence, momentum_data = self.should_enter_long(technical_data)

        if not should_enter:
            return None

        price = technical_data.get('price', 0)
        atr = technical_data.get('atr', 0)

        stop_loss = self.calculate_stop_loss(price, atr)
        take_profit = self.calculate_take_profit(price, stop_loss)

        signal = MomentumSignal(
            symbol=self.symbol,
            side='BUY',
            strength=momentum_data['momentum_score'],
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators=technical_data,
            confidence=confidence
        )

        return signal


class BreakoutMomentumStrategy(MomentumStrategy):
    """
    Enhanced momentum strategy that focuses on breakouts
    """

    def __init__(self, symbol: str, allocation: float = 0.3):
        super().__init__(symbol, allocation)
        self.resistance_level = 0.0
        self.support_level = 0.0

    def identify_breakout(self, technical_data: Dict, lookback_high: float) -> Tuple[bool, str]:
        """
        Identify breakout from consolidation

        Args:
            technical_data: Technical analysis data
            lookback_high: Highest price in lookback period

        Returns:
            Tuple of (is_breakout, breakout_type)
        """
        price = technical_data.get('price', 0)
        volume_ratio = technical_data.get('volume_ratio', 1.0)

        # Breakout confirmation criteria
        # 1. Price above recent high
        # 2. Volume spike (2x or more)
        # 3. Momentum indicators supporting

        if price > lookback_high * 1.01:  # 1% above high
            if volume_ratio >= 2.0:  # Strong volume
                momentum_data = self.analyze_momentum(technical_data)
                if momentum_data['momentum_score'] > 0.6:
                    return True, "strong_breakout"
                else:
                    return True, "weak_breakout"

        return False, "no_breakout"


if __name__ == "__main__":
    """Test momentum strategy"""
    from config import Config

    logger.info("Testing Momentum Strategy")

    strategy = MomentumStrategy('BTCUSDT', allocation=Config.MOMENTUM_ALLOCATION)

    # Test with sample data
    test_data = {
        'price': 51000.0,
        'ema_fast': 50800.0,
        'ema_slow': 50500.0,
        'ema_trend': 49000.0,
        'rsi': 62.0,
        'macd': 150.0,
        'macd_signal': 120.0,
        'macd_histogram': 30.0,
        'volume_ratio': 1.8,
        'vwap': 50900.0,
        'atr': 500.0
    }

    print("\n" + "="*60)
    print("MOMENTUM STRATEGY TEST")
    print("="*60)

    # Analyze momentum
    momentum = strategy.analyze_momentum(test_data)
    print(f"\nMomentum Analysis:")
    print(f"  Overall Score: {momentum['momentum_score']:.2f}")
    print(f"  Trend Bullish: {momentum['trend_bullish']}")
    print(f"  Trend Strength: {momentum['trend_strength']:.2f}")
    print(f"  RSI Momentum: {momentum['rsi_momentum']:.2f}")
    print(f"  MACD Momentum: {momentum['macd_momentum']:.2f}")
    print(f"  Volume Momentum: {momentum['volume_momentum']:.2f}")

    # Check entry signal
    should_enter, confidence, _ = strategy.should_enter_long(test_data)
    print(f"\nEntry Signal:")
    print(f"  Should Enter: {should_enter}")
    print(f"  Confidence: {confidence:.2f}")

    if should_enter:
        signal = strategy.generate_signal(test_data)
        if signal:
            print(f"\nSignal Generated:")
            print(f"  Entry: ${signal.entry_price:,.2f}")
            print(f"  Stop Loss: ${signal.stop_loss:,.2f}")
            print(f"  Take Profit: ${signal.take_profit:,.2f}")
            print(f"  Risk: ${signal.entry_price - signal.stop_loss:,.2f}")
            print(f"  Reward: ${signal.take_profit - signal.entry_price:,.2f}")
            print(f"  R:R Ratio: 1:{(signal.take_profit - signal.entry_price) / (signal.entry_price - signal.stop_loss):.1f}")

    print("="*60 + "\n")
