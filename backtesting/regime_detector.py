"""
Market Regime Detector
Classifies market conditions to dynamically adjust strategy behavior.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger
import pandas_ta as ta


class MarketRegime(Enum):
    """Market regime classification."""
    STRONG_BULL = "strong_bull"      # Strong uptrend - aggressive longs
    BULL = "bull"                     # Uptrend - normal longs
    SIDEWAYS = "sideways"             # Ranging - reduce size or sit out
    BEAR = "bear"                     # Downtrend - shorts if enabled
    STRONG_BEAR = "strong_bear"       # Strong downtrend - aggressive shorts


@dataclass
class RegimeAnalysis:
    """Result of regime analysis."""
    regime: MarketRegime
    confidence: float           # 0-1 confidence in classification
    trend_strength: float       # -1 to 1 (negative = bearish)
    volatility: str            # 'low', 'normal', 'high'
    volatility_percentile: float
    recommended_direction: str  # 'LONG', 'SHORT', 'NONE'
    recommended_size_mult: float  # Position size multiplier (0.5 - 1.5)
    btc_correlation: Optional[float] = None  # Correlation with BTC
    details: Dict = None


class RegimeDetector:
    """
    Detects market regime using multiple indicators and timeframes.
    Used to dynamically adjust trading behavior.
    """

    def __init__(self):
        """Initialize regime detector."""
        pass

    def detect_regime(
        self,
        df: pd.DataFrame,
        higher_tf_df: Optional[pd.DataFrame] = None
    ) -> RegimeAnalysis:
        """
        Detect current market regime.

        Args:
            df: OHLCV DataFrame (primary timeframe, e.g., 1H)
            higher_tf_df: Higher timeframe data (e.g., daily) for confirmation

        Returns:
            RegimeAnalysis with regime classification
        """
        df = df.copy()

        # Calculate indicators
        df = self._add_indicators(df)

        # Get latest values
        latest = df.iloc[-1]

        # 1. Trend Analysis (EMA-based)
        trend_strength = self._calculate_trend_strength(df)

        # 2. Volatility Analysis
        volatility, vol_percentile = self._calculate_volatility(df)

        # 3. Momentum Analysis
        momentum = self._calculate_momentum(df)

        # 4. Higher Timeframe Confirmation (if available)
        htf_trend = 0.0
        if higher_tf_df is not None and len(higher_tf_df) > 50:
            htf_df = self._add_indicators(higher_tf_df)
            htf_trend = self._calculate_trend_strength(htf_df)

        # 5. Classify Regime
        regime, confidence = self._classify_regime(
            trend_strength, momentum, volatility, htf_trend
        )

        # 6. Generate Recommendations
        direction, size_mult = self._generate_recommendations(
            regime, confidence, volatility
        )

        details = {
            'trend_strength': trend_strength,
            'momentum': momentum,
            'volatility_percentile': vol_percentile,
            'htf_trend': htf_trend,
            'ema_fast': latest.get('ema_20', 0),
            'ema_slow': latest.get('ema_50', 0),
            'ema_200': latest.get('ema_200', 0),
            'rsi': latest.get('rsi', 50),
            'adx': latest.get('adx', 0),
        }

        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility=volatility,
            volatility_percentile=vol_percentile,
            recommended_direction=direction,
            recommended_size_mult=size_mult,
            details=details
        )

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicators needed for regime detection."""
        df = df.copy()

        # EMAs
        df['ema_20'] = ta.ema(df['close'], length=20)
        df['ema_50'] = ta.ema(df['close'], length=50)
        df['ema_200'] = ta.ema(df['close'], length=200)

        # RSI
        df['rsi'] = ta.rsi(df['close'], length=14)

        # ADX (trend strength)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx['ADX_14']
        df['di_plus'] = adx['DMP_14']
        df['di_minus'] = adx['DMN_14']

        # ATR for volatility
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['atr_percent'] = (df['atr'] / df['close']) * 100

        # MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']

        # Rate of Change
        df['roc'] = ta.roc(df['close'], length=10)

        return df

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """
        Calculate trend strength from -1 (strong bear) to +1 (strong bull).
        """
        latest = df.iloc[-1]
        price = latest['close']
        ema_20 = latest['ema_20']
        ema_50 = latest['ema_50']
        ema_200 = latest['ema_200']
        adx = latest['adx']
        di_plus = latest['di_plus']
        di_minus = latest['di_minus']

        # Skip if indicators not ready
        if pd.isna(ema_200) or pd.isna(adx):
            return 0.0

        # EMA alignment score
        ema_score = 0.0
        if price > ema_20 > ema_50 > ema_200:
            ema_score = 1.0  # Perfect bullish alignment
        elif price < ema_20 < ema_50 < ema_200:
            ema_score = -1.0  # Perfect bearish alignment
        elif price > ema_50 > ema_200:
            ema_score = 0.5  # Bullish but not perfect
        elif price < ema_50 < ema_200:
            ema_score = -0.5  # Bearish but not perfect
        # else: sideways (0.0)

        # ADX direction
        adx_direction = 0.0
        if adx > 25:  # Trending
            if di_plus > di_minus:
                adx_direction = min(adx / 50, 1.0)
            else:
                adx_direction = -min(adx / 50, 1.0)

        # Price position relative to EMAs
        price_position = 0.0
        if ema_200 > 0:
            deviation = ((price - ema_200) / ema_200) * 100
            price_position = np.clip(deviation / 20, -1, 1)

        # Combined trend strength
        trend_strength = (
            ema_score * 0.4 +
            adx_direction * 0.3 +
            price_position * 0.3
        )

        return np.clip(trend_strength, -1, 1)

    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """Calculate momentum score from -1 to +1."""
        latest = df.iloc[-1]
        rsi = latest['rsi']
        macd = latest['macd']
        macd_signal = latest['macd_signal']
        roc = latest['roc']

        if pd.isna(rsi) or pd.isna(macd):
            return 0.0

        # RSI component (normalized)
        rsi_score = (rsi - 50) / 50  # -1 to +1

        # MACD component
        macd_score = 0.0
        if macd > macd_signal:
            macd_score = 0.5
        elif macd < macd_signal:
            macd_score = -0.5

        # ROC component
        roc_score = np.clip(roc / 10, -1, 1) if not pd.isna(roc) else 0.0

        momentum = (
            rsi_score * 0.4 +
            macd_score * 0.3 +
            roc_score * 0.3
        )

        return np.clip(momentum, -1, 1)

    def _calculate_volatility(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Calculate volatility classification.

        Returns:
            Tuple of (classification, percentile)
        """
        # Use ATR percent for volatility
        atr_pct = df['atr_percent'].dropna()

        if len(atr_pct) < 20:
            return 'normal', 50.0

        current_vol = atr_pct.iloc[-1]
        percentile = (atr_pct < current_vol).mean() * 100

        if percentile < 25:
            classification = 'low'
        elif percentile > 75:
            classification = 'high'
        else:
            classification = 'normal'

        return classification, percentile

    def _classify_regime(
        self,
        trend_strength: float,
        momentum: float,
        volatility: str,
        htf_trend: float
    ) -> Tuple[MarketRegime, float]:
        """
        Classify market regime based on indicators.

        Returns:
            Tuple of (regime, confidence)
        """
        # Combine trend and momentum
        combined = (trend_strength * 0.6 + momentum * 0.4)

        # Add higher timeframe bias
        if htf_trend != 0:
            combined = combined * 0.7 + htf_trend * 0.3

        # Classify
        if combined > 0.6:
            regime = MarketRegime.STRONG_BULL
            confidence = min((combined - 0.6) / 0.4 + 0.7, 1.0)
        elif combined > 0.2:
            regime = MarketRegime.BULL
            confidence = min((combined - 0.2) / 0.4 + 0.5, 0.9)
        elif combined > -0.2:
            regime = MarketRegime.SIDEWAYS
            confidence = 1.0 - abs(combined) / 0.2
        elif combined > -0.6:
            regime = MarketRegime.BEAR
            confidence = min((-combined - 0.2) / 0.4 + 0.5, 0.9)
        else:
            regime = MarketRegime.STRONG_BEAR
            confidence = min((-combined - 0.6) / 0.4 + 0.7, 1.0)

        # Reduce confidence in high volatility
        if volatility == 'high':
            confidence *= 0.8

        return regime, confidence

    def _generate_recommendations(
        self,
        regime: MarketRegime,
        confidence: float,
        volatility: str
    ) -> Tuple[str, float]:
        """
        Generate trading recommendations based on regime.

        Returns:
            Tuple of (direction, size_multiplier)
        """
        recommendations = {
            MarketRegime.STRONG_BULL: ('LONG', 1.2),
            MarketRegime.BULL: ('LONG', 1.0),
            MarketRegime.SIDEWAYS: ('NONE', 0.5),
            MarketRegime.BEAR: ('SHORT', 1.0),
            MarketRegime.STRONG_BEAR: ('SHORT', 1.2),
        }

        direction, size_mult = recommendations[regime]

        # Adjust for confidence
        if confidence < 0.5:
            size_mult *= 0.5
        elif confidence < 0.7:
            size_mult *= 0.75

        # Adjust for volatility
        if volatility == 'high':
            size_mult *= 0.7
        elif volatility == 'low':
            size_mult *= 1.1

        # Cap size multiplier
        size_mult = np.clip(size_mult, 0.3, 1.5)

        return direction, size_mult

    def analyze_regime_performance(
        self,
        df: pd.DataFrame,
        trades: List
    ) -> Dict:
        """
        Analyze how strategy performed in different regimes.

        Args:
            df: OHLCV DataFrame
            trades: List of SimulatedTrade objects

        Returns:
            Dict with performance by regime
        """
        df = self._add_indicators(df)

        results = {regime.value: {'trades': 0, 'wins': 0, 'pnl': 0.0} for regime in MarketRegime}

        for trade in trades:
            # Find regime at entry
            entry_time = trade.entry_time
            if entry_time in df.index:
                idx = df.index.get_loc(entry_time)
            else:
                # Find closest timestamp
                idx = df.index.searchsorted(entry_time)
                if idx >= len(df):
                    idx = len(df) - 1

            # Get regime at entry
            window = df.iloc[max(0, idx-50):idx+1]
            if len(window) > 20:
                analysis = self.detect_regime(window)
                regime = analysis.regime.value

                results[regime]['trades'] += 1
                results[regime]['pnl'] += trade.pnl_usdt
                if trade.is_win:
                    results[regime]['wins'] += 1

        # Calculate win rates
        for regime in results:
            total = results[regime]['trades']
            if total > 0:
                results[regime]['win_rate'] = (results[regime]['wins'] / total) * 100
            else:
                results[regime]['win_rate'] = 0

        return results


if __name__ == '__main__':
    # Test regime detector
    from data_fetcher import DataFetcher

    fetcher = DataFetcher()

    # Fetch hourly data
    df_1h = fetcher.fetch_ohlcv('BTCUSDT', interval='1h', days=90)

    # Fetch daily data for higher timeframe
    df_1d = fetcher.fetch_ohlcv('BTCUSDT', interval='1d', days=90)

    detector = RegimeDetector()

    # Analyze current regime
    analysis = detector.detect_regime(df_1h, df_1d)

    print(f"\n{'='*60}")
    print("MARKET REGIME ANALYSIS - BTCUSDT")
    print(f"{'='*60}")
    print(f"\nRegime: {analysis.regime.value.upper()}")
    print(f"Confidence: {analysis.confidence*100:.1f}%")
    print(f"Trend Strength: {analysis.trend_strength:+.2f}")
    print(f"Volatility: {analysis.volatility} ({analysis.volatility_percentile:.0f}th percentile)")
    print(f"\nRecommendations:")
    print(f"  Direction: {analysis.recommended_direction}")
    print(f"  Size Multiplier: {analysis.recommended_size_mult:.2f}x")
    print(f"\nIndicators:")
    for key, value in analysis.details.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    print(f"{'='*60}")
