"""
Backtesting Framework for Binance Trading Bot
Test strategies against historical data before risking real money.
"""

from .data_fetcher import DataFetcher
from .simulator import TradeSimulator
from .regime_detector import RegimeDetector
from .reporter import BacktestReporter

__all__ = ['DataFetcher', 'TradeSimulator', 'RegimeDetector', 'BacktestReporter']
