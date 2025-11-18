"""
Technical Analysis Module
Comprehensive indicator calculations and signal generation
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger
import pandas_ta as ta


class TechnicalAnalysis:
    """
    Advanced technical analysis with multi-indicator confirmation
    Implements trend, momentum, volatility, and volume indicators
    """

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with price data

        Args:
            df: DataFrame with columns: open, high, low, close, volume
        """
        self.df = df.copy()
        self.signals = {}
        self.indicators = {}

    @staticmethod
    def prepare_dataframe(klines: List[List]) -> pd.DataFrame:
        """
        Convert Binance klines to pandas DataFrame

        Args:
            klines: List of klines from Binance API

        Returns:
            DataFrame with OHLCV data
        """
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        return df[['open', 'high', 'low', 'close', 'volume']]

    def calculate_all_indicators(self):
        """Calculate all technical indicators"""
        self.calculate_moving_averages()
        self.calculate_rsi()
        self.calculate_macd()
        self.calculate_bollinger_bands()
        self.calculate_atr()
        self.calculate_volume_indicators()
        self.calculate_stochastic()
        logger.debug("All indicators calculated")

    def calculate_moving_averages(self):
        """Calculate EMA moving averages for trend identification"""
        from config import Config

        self.df['ema_fast'] = ta.ema(self.df['close'], length=Config.EMA_FAST)
        self.df['ema_slow'] = ta.ema(self.df['close'], length=Config.EMA_SLOW)
        self.df['ema_trend'] = ta.ema(self.df['close'], length=Config.EMA_TREND)

        # Calculate SMA for comparison
        self.df['sma_20'] = ta.sma(self.df['close'], length=20)
        self.df['sma_50'] = ta.sma(self.df['close'], length=50)

        logger.debug("Moving averages calculated")

    def calculate_rsi(self):
        """Calculate Relative Strength Index"""
        from config import Config

        self.df['rsi'] = ta.rsi(self.df['close'], length=Config.RSI_PERIOD)
        logger.debug("RSI calculated")

    def calculate_macd(self):
        """Calculate MACD indicator"""
        from config import Config

        macd = ta.macd(
            self.df['close'],
            fast=Config.MACD_FAST,
            slow=Config.MACD_SLOW,
            signal=Config.MACD_SIGNAL
        )

        self.df['macd'] = macd[f'MACD_{Config.MACD_FAST}_{Config.MACD_SLOW}_{Config.MACD_SIGNAL}']
        self.df['macd_signal'] = macd[f'MACDs_{Config.MACD_FAST}_{Config.MACD_SLOW}_{Config.MACD_SIGNAL}']
        self.df['macd_histogram'] = macd[f'MACDh_{Config.MACD_FAST}_{Config.MACD_SLOW}_{Config.MACD_SIGNAL}']

        logger.debug("MACD calculated")

    def calculate_bollinger_bands(self):
        """Calculate Bollinger Bands for volatility"""
        from config import Config

        bb = ta.bbands(self.df['close'], length=Config.BB_PERIOD, std=Config.BB_STD)

        # Handle different pandas-ta versions (column names changed in newer versions)
        bb_cols = bb.columns.tolist()
        upper_col = [c for c in bb_cols if c.startswith('BBU')][0]
        middle_col = [c for c in bb_cols if c.startswith('BBM')][0]
        lower_col = [c for c in bb_cols if c.startswith('BBL')][0]

        self.df['bb_upper'] = bb[upper_col]
        self.df['bb_middle'] = bb[middle_col]
        self.df['bb_lower'] = bb[lower_col]

        # Calculate BB width for volatility measurement
        self.df['bb_width'] = (self.df['bb_upper'] - self.df['bb_lower']) / self.df['bb_middle']

        logger.debug("Bollinger Bands calculated")

    def calculate_atr(self):
        """Calculate Average True Range for volatility and stop loss placement"""
        from config import Config

        self.df['atr'] = ta.atr(
            self.df['high'],
            self.df['low'],
            self.df['close'],
            length=Config.ATR_PERIOD
        )

        # Calculate ATR percentage
        self.df['atr_pct'] = (self.df['atr'] / self.df['close']) * 100

        logger.debug("ATR calculated")

    def calculate_volume_indicators(self):
        """Calculate volume-based indicators"""
        # On-Balance Volume
        self.df['obv'] = ta.obv(self.df['close'], self.df['volume'])

        # Volume Moving Average
        self.df['volume_sma'] = ta.sma(self.df['volume'], length=20)

        # Volume ratio
        self.df['volume_ratio'] = self.df['volume'] / self.df['volume_sma']

        # VWAP (Volume Weighted Average Price)
        self.df['vwap'] = ta.vwap(
            self.df['high'],
            self.df['low'],
            self.df['close'],
            self.df['volume']
        )

        logger.debug("Volume indicators calculated")

    def calculate_stochastic(self):
        """Calculate Stochastic Oscillator"""
        stoch = ta.stoch(self.df['high'], self.df['low'], self.df['close'])

        self.df['stoch_k'] = stoch['STOCHk_14_3_3']
        self.df['stoch_d'] = stoch['STOCHd_14_3_3']

        logger.debug("Stochastic calculated")

    def calculate_support_resistance(self, lookback: int = 50) -> Dict[str, float]:
        """
        Calculate dynamic support and resistance levels

        Args:
            lookback: Number of periods to look back

        Returns:
            Dict with support and resistance levels
        """
        recent_data = self.df.tail(lookback)

        # Calculate pivot points
        pivot = (recent_data['high'].iloc[-1] + recent_data['low'].iloc[-1] + recent_data['close'].iloc[-1]) / 3

        # Calculate support and resistance
        resistance = 2 * pivot - recent_data['low'].iloc[-1]
        support = 2 * pivot - recent_data['high'].iloc[-1]

        # Find swing highs and lows
        swing_highs = recent_data[recent_data['high'] == recent_data['high'].rolling(window=5, center=True).max()]['high']
        swing_lows = recent_data[recent_data['low'] == recent_data['low'].rolling(window=5, center=True).min()]['low']

        return {
            'resistance': float(resistance),
            'support': float(support),
            'pivot': float(pivot),
            'swing_high': float(swing_highs.mean()) if len(swing_highs) > 0 else float(resistance),
            'swing_low': float(swing_lows.mean()) if len(swing_lows) > 0 else float(support)
        }

    def generate_entry_signals(self) -> pd.Series:
        """
        Generate strong entry signals using multiple confirmations

        Returns:
            Series with signal strength (0-1)
        """
        from config import Config

        signals = pd.Series(0.0, index=self.df.index)

        # Fill NaN/None values in dataframe columns to prevent comparison errors
        df_filled = self.df.fillna(0)

        # Condition 1: EMA alignment (trend confirmation) - handle NaN
        trend_bullish = (
            (df_filled['ema_fast'] > df_filled['ema_slow']) &
            (df_filled['ema_slow'] > df_filled['ema_trend'])
        ).astype(int)

        # Condition 2: RSI in optimal range (not overbought)
        rsi_optimal = (
            (df_filled['rsi'] > Config.RSI_OVERSOLD) &
            (df_filled['rsi'] < Config.RSI_OVERBOUGHT)
        ).astype(int)

        # Condition 3: MACD bullish
        macd_bullish = (
            (df_filled['macd'] > df_filled['macd_signal']) &
            (df_filled['macd_histogram'] > 0)
        ).astype(int)

        # Condition 4: Price above VWAP
        price_strong = (df_filled['close'] > df_filled['vwap']).astype(int)

        # Condition 5: Volume confirmation
        volume_strong = (df_filled['volume_ratio'] > 1.2).astype(int)

        # Condition 6: Stochastic not overbought
        stoch_ok = (df_filled['stoch_k'] < 80).astype(int)

        # Calculate signal strength
        total_conditions = trend_bullish + rsi_optimal + macd_bullish + price_strong + volume_strong + stoch_ok
        signals = total_conditions / 6.0

        return signals

    def generate_exit_signals(self) -> pd.Series:
        """
        Generate exit signals

        Returns:
            Series with exit signal strength
        """
        from config import Config

        exit_signals = pd.Series(0.0, index=self.df.index)

        # Exit condition 1: RSI overbought
        rsi_overbought = (self.df['rsi'] > Config.RSI_OVERBOUGHT).astype(int)

        # Exit condition 2: MACD bearish crossover
        macd_bearish = (
            (self.df['macd'] < self.df['macd_signal']) &
            (self.df['macd_histogram'] < 0)
        ).astype(int)

        # Exit condition 3: Price near upper Bollinger Band
        near_upper_bb = (self.df['close'] > self.df['bb_upper'] * 0.98).astype(int)

        # Exit condition 4: Stochastic overbought
        stoch_overbought = (self.df['stoch_k'] > 80).astype(int)

        # Calculate exit strength
        total_exit_conditions = rsi_overbought + macd_bearish + near_upper_bb + stoch_overbought
        exit_signals = total_exit_conditions / 4.0

        return exit_signals

    def identify_trend(self) -> str:
        """
        Identify current market trend using 3-layer detection

        Layer 1: ATR-based range detection (catches tight ranges)
        Layer 2: Price structure analysis (higher highs/lower lows)
        Layer 3: EMA alignment (confirms direction)

        Returns:
            'bullish', 'bearish', or 'sideways'
        """
        import pandas as pd

        recent = self.df.tail(20)

        # Get values with None handling
        try:
            ema_fast = recent['ema_fast'].iloc[-1]
            ema_slow = recent['ema_slow'].iloc[-1]
            ema_trend = recent['ema_trend'].iloc[-1]
            current_price = recent['close'].iloc[-1]
            atr = recent['atr'].iloc[-1]

            # Check if any values are NaN
            if pd.isna(ema_fast) or pd.isna(ema_slow) or pd.isna(ema_trend) or pd.isna(atr):
                return 'sideways'

            # === LAYER 1: ATR-based Range Detection ===
            # If price is oscillating in a tight range relative to volatility = RANGING
            recent_10 = recent.tail(10)
            recent_high = recent_10['high'].max()
            recent_low = recent_10['low'].min()
            price_range_pct = (recent_high - recent_low) / current_price
            atr_pct = atr / current_price

            # If price range < 2x ATR, it's ranging/choppy
            if price_range_pct < (atr_pct * 2):
                return 'sideways'

            # === LAYER 2: Price Structure Analysis ===
            # Check if making higher highs AND higher lows (uptrend structure)
            # or lower highs AND lower lows (downtrend structure)
            first_half = recent.iloc[:10]
            second_half = recent.iloc[10:]

            first_half_high = first_half['high'].max()
            second_half_high = second_half['high'].max()
            first_half_low = first_half['low'].min()
            second_half_low = second_half['low'].min()

            higher_highs = second_half_high > first_half_high
            higher_lows = second_half_low > first_half_low
            lower_highs = second_half_high < first_half_high
            lower_lows = second_half_low < first_half_low

            # Determine price structure
            structure_bullish = higher_highs and higher_lows
            structure_bearish = lower_highs and lower_lows

            # Mixed/choppy structure - reject
            if not structure_bullish and not structure_bearish:
                return 'sideways'

            # === LAYER 3: EMA Alignment Confirmation ===
            ema_bullish = ema_fast > ema_slow > ema_trend
            ema_bearish = ema_fast < ema_slow < ema_trend

            # Only return bullish if ALL layers confirm
            if structure_bullish and ema_bullish:
                return 'bullish'
            elif structure_bearish and ema_bearish:
                return 'bearish'
            else:
                return 'sideways'

        except (TypeError, ValueError, IndexError):
            return 'sideways'

    def get_current_volatility(self) -> float:
        """
        Get current volatility level

        Returns:
            Volatility percentage
        """
        return float(self.df['atr_pct'].iloc[-1])

    def is_volatile_market(self, threshold: float = 3.0) -> bool:
        """
        Check if market is currently volatile

        Args:
            threshold: ATR percentage threshold

        Returns:
            True if volatile
        """
        return self.get_current_volatility() > threshold

    def get_latest_values(self) -> Dict:
        """
        Get latest values of all indicators

        Returns:
            Dict of latest indicator values
        """
        latest = self.df.iloc[-1]

        # Helper function to safely convert to float, handling NaN values
        def safe_float(value):
            if pd.isna(value):
                return 0.0
            return float(value)

        return {
            'price': safe_float(latest['close']),
            'ema_fast': safe_float(latest['ema_fast']),
            'ema_slow': safe_float(latest['ema_slow']),
            'ema_trend': safe_float(latest['ema_trend']),
            'rsi': safe_float(latest['rsi']),
            'macd': safe_float(latest['macd']),
            'macd_signal': safe_float(latest['macd_signal']),
            'macd_histogram': safe_float(latest['macd_histogram']),
            'bb_upper': safe_float(latest['bb_upper']),
            'bb_middle': safe_float(latest['bb_middle']),
            'bb_lower': safe_float(latest['bb_lower']),
            'atr': safe_float(latest['atr']),
            'atr_pct': safe_float(latest['atr_pct']),
            'volume_ratio': safe_float(latest['volume_ratio']),
            'vwap': safe_float(latest['vwap']),
            'stoch_k': safe_float(latest['stoch_k']),
            'stoch_d': safe_float(latest['stoch_d'])
        }

    def calculate_position_score(self) -> float:
        """
        Calculate overall position score (0-100)

        Returns:
            Position score
        """
        signals = self.generate_entry_signals()
        latest_signal = signals.iloc[-1]

        # Get trend strength
        trend = self.identify_trend()
        trend_score = 1.0 if trend == 'bullish' else 0.5 if trend == 'sideways' else 0.0

        # Combine with volume and volatility
        volume_score = min(self.df['volume_ratio'].iloc[-1] / 2.0, 1.0)

        # Calculate final score
        final_score = (latest_signal * 0.5 + trend_score * 0.3 + volume_score * 0.2) * 100

        return float(final_score)


if __name__ == "__main__":
    """Test technical analysis module"""
    from binance_client import ResilientBinanceClient
    from config import Config

    logger.info("Testing Technical Analysis Module")

    # Initialize client
    client = ResilientBinanceClient(
        Config.BINANCE_API_KEY,
        Config.BINANCE_API_SECRET,
        testnet=True
    )

    # Get historical data
    klines = client.get_historical_klines('BTCUSDT', '5m', limit=200)
    df = TechnicalAnalysis.prepare_dataframe(klines)

    # Initialize TA
    ta_analyzer = TechnicalAnalysis(df)
    ta_analyzer.calculate_all_indicators()

    # Get signals
    entry_signals = ta_analyzer.generate_entry_signals()
    trend = ta_analyzer.identify_trend()
    score = ta_analyzer.calculate_position_score()
    latest_values = ta_analyzer.get_latest_values()

    print("\n" + "="*60)
    print("TECHNICAL ANALYSIS RESULTS")
    print("="*60)
    print(f"Current Trend: {trend.upper()}")
    print(f"Position Score: {score:.1f}/100")
    print(f"Latest Signal Strength: {entry_signals.iloc[-1]:.2f}")
    print(f"\nKey Indicators:")
    print(f"  Price: ${latest_values['price']:,.2f}")
    print(f"  RSI: {latest_values['rsi']:.2f}")
    print(f"  MACD: {latest_values['macd']:.4f}")
    print(f"  ATR %: {latest_values['atr_pct']:.2f}%")
    print(f"  Volume Ratio: {latest_values['volume_ratio']:.2f}x")
    print("="*60)
