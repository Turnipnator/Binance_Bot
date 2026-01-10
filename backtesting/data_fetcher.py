"""
Historical Data Fetcher for Backtesting
Fetches OHLCV data from Binance for backtesting.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from binance.client import Client
from loguru import logger
import time
import os


class DataFetcher:
    """
    Fetches historical OHLCV data from Binance.
    Handles rate limiting and data caching.
    """

    # Binance kline intervals
    INTERVALS = {
        '1m': Client.KLINE_INTERVAL_1MINUTE,
        '5m': Client.KLINE_INTERVAL_5MINUTE,
        '15m': Client.KLINE_INTERVAL_15MINUTE,
        '1h': Client.KLINE_INTERVAL_1HOUR,
        '4h': Client.KLINE_INTERVAL_4HOUR,
        '1d': Client.KLINE_INTERVAL_1DAY,
    }

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize data fetcher.

        Args:
            api_key: Binance API key (optional for public data)
            api_secret: Binance API secret (optional for public data)
        """
        self.api_key = api_key or os.getenv('BINANCE_API_KEY')
        self.api_secret = api_secret or os.getenv('BINANCE_API_SECRET')

        if self.api_key and self.api_secret:
            self.client = Client(self.api_key, self.api_secret)
        else:
            # Public client (no auth needed for historical data)
            self.client = Client()

        self.cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = '1h',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Binance.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Candle interval ('1m', '5m', '15m', '1h', '4h', '1d')
            start_date: Start date string 'YYYY-MM-DD' (optional)
            end_date: End date string 'YYYY-MM-DD' (optional)
            days: Number of days to fetch if no dates specified

        Returns:
            DataFrame with OHLCV data
        """
        if interval not in self.INTERVALS:
            raise ValueError(f"Invalid interval: {interval}. Use: {list(self.INTERVALS.keys())}")

        # Calculate date range
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_dt = datetime.now()

        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = end_dt - timedelta(days=days)

        # Convert to milliseconds
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

        logger.info(f"Fetching {symbol} {interval} data from {start_dt.date()} to {end_dt.date()}")

        # Fetch data in chunks (Binance limit is 1000 candles per request)
        all_klines = []
        current_start = start_ms

        while current_start < end_ms:
            try:
                klines = self.client.get_klines(
                    symbol=symbol,
                    interval=self.INTERVALS[interval],
                    startTime=current_start,
                    endTime=end_ms,
                    limit=1000
                )

                if not klines:
                    break

                all_klines.extend(klines)

                # Move to next chunk
                current_start = klines[-1][0] + 1

                # Rate limiting
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error fetching data: {e}")
                break

        if not all_klines:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convert types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = df[col].astype(float)

        df.set_index('timestamp', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']]

        logger.info(f"Fetched {len(df)} candles for {symbol}")

        return df

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        interval: str = '1h',
        days: int = 30
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols.

        Args:
            symbols: List of trading pairs
            interval: Candle interval
            days: Number of days to fetch

        Returns:
            Dict mapping symbol to DataFrame
        """
        data = {}
        for symbol in symbols:
            df = self.fetch_ohlcv(symbol, interval=interval, days=days)
            if not df.empty:
                data[symbol] = df
            time.sleep(0.2)  # Rate limiting between symbols

        return data

    def save_to_cache(self, symbol: str, interval: str, df: pd.DataFrame):
        """Save data to local cache."""
        filename = f"{symbol}_{interval}.parquet"
        filepath = os.path.join(self.cache_dir, filename)
        df.to_parquet(filepath)
        logger.info(f"Cached {symbol} data to {filepath}")

    def load_from_cache(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Load data from local cache if available."""
        filename = f"{symbol}_{interval}.parquet"
        filepath = os.path.join(self.cache_dir, filename)

        if os.path.exists(filepath):
            df = pd.read_parquet(filepath)
            logger.info(f"Loaded {symbol} data from cache ({len(df)} candles)")
            return df

        return None

    def fetch_with_cache(
        self,
        symbol: str,
        interval: str = '1h',
        days: int = 30,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Fetch data with caching support.

        Args:
            symbol: Trading pair
            interval: Candle interval
            days: Number of days
            force_refresh: Force fetch fresh data

        Returns:
            DataFrame with OHLCV data
        """
        if not force_refresh:
            cached = self.load_from_cache(symbol, interval)
            if cached is not None:
                return cached

        df = self.fetch_ohlcv(symbol, interval=interval, days=days)

        if not df.empty:
            self.save_to_cache(symbol, interval, df)

        return df


if __name__ == '__main__':
    # Test the data fetcher
    fetcher = DataFetcher()

    # Fetch 30 days of BTC 1H data
    df = fetcher.fetch_ohlcv('BTCUSDT', interval='1h', days=30)

    print(f"\nFetched {len(df)} candles")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"\nSample data:")
    print(df.head())
    print(f"\nStatistics:")
    print(df.describe())
