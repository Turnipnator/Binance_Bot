"""
Mean Reversion Strategy
Exploits price extremes and volatility spikes to profit from returns to mean
"""
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from loguru import logger

# Liquid pairs only for the mean-reversion signal (excludes BONK/TAO where
# slippage is worst and the backtest is least trustworthy). See memory
# mean-reversion-signal-promising. Backtested 2026-07-02: PF 1.82 @0.2% fees.
MR_LIQUID_PAIRS = {
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'LINKUSDT',
    'LTCUSDT', 'ADAUSDT', 'AVAXUSDT', 'TRXUSDT', 'SUIUSDT',
}
MR_RSI_ENTRY = 30.0      # 15m RSI(14) oversold trigger
MR_STOP_PCT = 3.0        # 3% hard stop (backtested sl3 variant)
MR_MAX_HOLD_HOURS = 24   # time-stop


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

    def __init__(self, symbol: str, allocation: float = 0.2, risk_manager=None, client=None):
        """
        Initialize mean reversion strategy

        Args:
            symbol: Trading pair symbol
            allocation: Portfolio allocation for this strategy
            risk_manager: Risk manager instance for stop loss calculations
            client: Binance client for fetching 15m / BTC-daily data
        """
        self.symbol = symbol
        self.allocation = allocation
        self.in_position = False
        self.entry_price = 0.0
        self.mean_price = 0.0
        self.risk_manager = risk_manager
        self.client = client
        self._sig_cache = None  # stashed 15m computation to avoid double-fetch

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
        # VALIDATED mean-reversion pullback (backtested 2026-07-02, PF 1.82 @0.2% fees):
        # in a confirmed uptrend (pair 15m close > 15m EMA200 AND BTC > daily EMA50),
        # buy when 15m RSI(14) < 30. Liquid pairs only. Expensive 15m/BTC fetches are
        # gated behind cheap checks (liquid, flat, 5m RSI already soft-oversold).
        self._sig_cache = None
        if self.in_position:
            return False, 0.0, {}
        if self.symbol not in MR_LIQUID_PAIRS:
            return False, 0.0, {}
        rsi_5m = technical_data.get('rsi', 50)
        if rsi_5m is None or rsi_5m >= 40:   # cheap pre-gate, no fetch
            return False, 0.0, {}
        if not self.client:
            logger.warning(f"MR: no client for {self.symbol}, cannot confirm 15m signal")
            return False, 0.0, {}

        ind = self._fetch_15m_indicators()
        if ind is None:
            return False, 0.0, {}

        if not (ind['close'] > ind['ema200']):          # uptrend intact
            return False, 0.0, ind
        if not (ind['rsi'] < MR_RSI_ENTRY):             # oversold trigger
            return False, 0.0, ind
        if not self._btc_daily_regime_ok():             # market regime (fails closed)
            logger.info(f"MR {self.symbol}: 15m RSI {ind['rsi']:.1f} oversold in uptrend but BTC below daily EMA50 - skip")
            return False, 0.0, ind

        confidence = min(1.0, 0.75 + (MR_RSI_ENTRY - ind['rsi']) / 100.0)
        ind['confidence'] = confidence
        self._sig_cache = ind
        logger.info(f"✅ MR LONG signal {self.symbol}: 15m RSI={ind['rsi']:.1f}<30, close>EMA200, BTC regime ok (conf {confidence:.2f})")
        return True, confidence, ind

    def _fetch_15m_indicators(self) -> Optional[Dict]:
        """Fetch 15m klines and compute RSI(14), EMA20, EMA200 on the last bar."""
        try:
            import pandas as pd
            import pandas_ta as ta
            kl = self.client.get_historical_klines(symbol=self.symbol, interval='15m', limit=250)
            if not kl or len(kl) < 205:
                logger.debug(f"MR {self.symbol}: insufficient 15m data ({len(kl) if kl else 0})")
                return None
            df = pd.DataFrame(kl, columns=['t','o','h','l','c','v','ct','qv','n','tb','tq','ig'])
            for col in ['o','h','l','c']:
                df[col] = df[col].astype(float)
            df['ema200'] = ta.ema(df['c'], length=200)
            df['ema20'] = ta.ema(df['c'], length=20)
            df['rsi'] = ta.rsi(df['c'], length=14)
            last = df.iloc[-1]
            if pd.isna(last['ema200']) or pd.isna(last['ema20']) or pd.isna(last['rsi']):
                return None
            return {'rsi': float(last['rsi']), 'ema20': float(last['ema20']),
                    'ema200': float(last['ema200']), 'close': float(last['c'])}
        except Exception as e:
            logger.error(f"MR {self.symbol}: 15m fetch error: {e}")
            return None

    def _btc_daily_regime_ok(self) -> bool:
        """BTC above its daily EMA50. Fails CLOSED (no MR entry if unknown) -
        for a dip-buyer, uncertainty about the macro trend should block, not allow."""
        try:
            import pandas as pd
            import pandas_ta as ta
            kl = self.client.get_historical_klines(symbol='BTCUSDT', interval='1d', limit=100)
            if not kl or len(kl) < 55:
                return False
            df = pd.DataFrame(kl, columns=['t','o','h','l','c','v','ct','qv','n','tb','tq','ig'])
            df['c'] = df['c'].astype(float)
            df['ema50'] = ta.ema(df['c'], length=50)
            last = df.iloc[-1]
            return False if pd.isna(last['ema50']) else bool(last['c'] > last['ema50'])
        except Exception as e:
            logger.error(f"MR: BTC regime check error: {e}")
            return False

    def should_exit_reversion(self, current_price: float) -> Tuple[bool, str]:
        """Exit when 15m price reverts up to its EMA20 (the mean). Fails safe:
        on data error, HOLD (the hard stop + time-stop still protect the position)."""
        ind = self._fetch_15m_indicators()
        if ind is None:
            return False, "MR exit: 15m data unavailable (holding)"
        if current_price >= ind['ema20']:
            return True, "Mean reversion target (reverted to 15m EMA20)"
        return False, "MR: below mean, holding"

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
        # Use risk manager's stop loss (per-symbol for meme coins)
        if self.risk_manager:
            stop_loss = self.risk_manager.calculate_atr_stop_loss(entry_price, atr, side, symbol=self.symbol)
            logger.debug(f"Using per-symbol stop from risk manager: {stop_loss:.8f}")
            return stop_loss

        # Fallback to ATR-based stop (shouldn't happen in production)
        stop_multiplier = 2.0
        if side == 'long':
            stop_loss = entry_price - (atr * stop_multiplier)
        else:
            stop_loss = entry_price + (atr * stop_multiplier)

        logger.warning(f"Risk manager not available, using ATR-based stop: {stop_loss:.8f}")
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
        # Reuse the 15m computation stashed by should_enter_long in the same
        # scan cycle (the entry loop calls should_enter_long immediately before
        # this), avoiding a duplicate 15m/BTC fetch.
        ind = self._sig_cache
        if ind is None:
            should_enter, _conf, ind = self.should_enter_long(technical_data)
            if not should_enter:
                return None

        conf = ind.get('confidence', 0.75)
        price = technical_data.get('price', 0) or ind.get('close', 0)
        ema20 = ind.get('ema20', price)

        stop_loss = price * (1 - MR_STOP_PCT / 100.0)   # 3% hard stop (backtested)
        take_profit = ema20                              # target = reversion to 15m mean

        return ReversionSignal(
            symbol=self.symbol,
            side='BUY',
            strength=conf,
            entry_price=price,
            mean_price=ema20,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reversion_distance=abs(price - ema20) / ema20 if ema20 else 0.0,
            confidence=conf,
        )


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
