#!/usr/bin/env python3
"""
Backtesting CLI for Binance Trading Bot
Run backtests against historical data to validate strategies.

Usage:
    python -m backtesting.backtest --symbol BTCUSDT --days 90
    python -m backtesting.backtest --symbol BTCUSDT --days 90 --compare-shorting
    python -m backtesting.backtest --symbol BTCUSDT --start 2024-01-01 --end 2024-06-01
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from loguru import logger

from backtesting.data_fetcher import DataFetcher
from backtesting.simulator import TradeSimulator
from backtesting.regime_detector import RegimeDetector
from backtesting.reporter import BacktestReporter


def run_backtest(
    symbol: str,
    days: int = 90,
    start_date: str = None,
    end_date: str = None,
    interval: str = '1h',
    initial_balance: float = 1000.0,
    enable_shorting: bool = False,
    compare_shorting: bool = False,
    show_trades: bool = False,
    analyze_regimes: bool = False,
    save_results: bool = False
):
    """
    Run a backtest with the specified parameters.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        days: Number of days of historical data
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Candle interval
        initial_balance: Starting balance
        enable_shorting: Allow short trades
        compare_shorting: Run both LONG-only and LONG+SHORT for comparison
        show_trades: Show recent trades
        analyze_regimes: Analyze performance by market regime
        save_results: Save results to files
    """
    print(f"\n{'='*70}")
    print("BINANCE BOT BACKTESTER")
    print(f"{'='*70}")

    # Fetch data
    print(f"\nFetching {symbol} {interval} data...")
    fetcher = DataFetcher()

    df = fetcher.fetch_ohlcv(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        days=days
    )

    if df.empty:
        print("ERROR: No data fetched. Check symbol and date range.")
        return

    print(f"Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    # Initialize reporter
    reporter = BacktestReporter()

    # Run comparison if requested
    if compare_shorting:
        print("\n--- Running LONG ONLY backtest ---")
        sim_long = TradeSimulator(
            initial_balance=initial_balance,
            enable_shorting=False
        )
        result_long = sim_long.simulate(df, symbol)

        print("\n--- Running LONG + SHORT backtest ---")
        sim_both = TradeSimulator(
            initial_balance=initial_balance,
            enable_shorting=True
        )
        result_both = sim_both.simulate(df, symbol)

        # Print comparison
        reporter.print_comparison(result_long, result_both)

        # Show regime analysis for both
        if analyze_regimes:
            print("\n--- LONG ONLY - Regime Analysis ---")
            reporter.print_regime_analysis(df, result_long.trades)

            print("\n--- LONG + SHORT - Regime Analysis ---")
            reporter.print_regime_analysis(df, result_both.trades)

        # Save results
        if save_results:
            reporter.save_results(result_long, f"backtest_{symbol}_long_only.json")
            reporter.save_results(result_both, f"backtest_{symbol}_long_short.json")

    else:
        # Single backtest
        direction = "LONG + SHORT" if enable_shorting else "LONG ONLY"
        print(f"\n--- Running {direction} backtest ---")

        simulator = TradeSimulator(
            initial_balance=initial_balance,
            enable_shorting=enable_shorting
        )

        result = simulator.simulate(df, symbol)

        # Print results
        reporter.print_summary(result)

        # Show recent trades
        if show_trades and result.trades:
            reporter.print_recent_trades(result)

        # Regime analysis
        if analyze_regimes and result.trades:
            reporter.print_regime_analysis(df, result.trades)

        # Save results
        if save_results:
            reporter.save_results(result)
            reporter.save_trade_log_csv(result)

    # Current regime analysis
    print("\n--- CURRENT MARKET REGIME ---")
    detector = RegimeDetector()

    # Get higher timeframe data
    df_daily = fetcher.fetch_ohlcv(symbol, interval='1d', days=90)

    analysis = detector.detect_regime(df, df_daily)

    print(f"\nRegime: {analysis.regime.value.upper()}")
    print(f"Confidence: {analysis.confidence*100:.1f}%")
    print(f"Trend Strength: {analysis.trend_strength:+.2f} (-1=bear, +1=bull)")
    print(f"Volatility: {analysis.volatility} ({analysis.volatility_percentile:.0f}th percentile)")
    print(f"\nRecommendation:")
    print(f"  Direction: {analysis.recommended_direction}")
    print(f"  Position Size: {analysis.recommended_size_mult:.1f}x normal")

    if analysis.recommended_direction == 'NONE':
        print(f"\n  (Sideways market - consider reducing exposure)")
    elif analysis.recommended_direction == 'SHORT' and not enable_shorting:
        print(f"\n  (Shorting not enabled - sit tight or reduce longs)")


def main():
    parser = argparse.ArgumentParser(
        description='Backtest Binance trading strategy against historical data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic backtest (LONG only, last 90 days)
  python -m backtesting.backtest --symbol BTCUSDT

  # Compare LONG-only vs LONG+SHORT
  python -m backtesting.backtest --symbol BTCUSDT --compare-shorting

  # Backtest with specific date range
  python -m backtesting.backtest --symbol ETHUSDT --start 2024-01-01 --end 2024-06-01

  # Full analysis with regime breakdown
  python -m backtesting.backtest --symbol BTCUSDT --days 180 --analyze-regimes --show-trades
        """
    )

    parser.add_argument(
        '--symbol', '-s',
        type=str,
        default='BTCUSDT',
        help='Trading pair symbol (default: BTCUSDT)'
    )

    parser.add_argument(
        '--days', '-d',
        type=int,
        default=90,
        help='Number of days of historical data (default: 90)'
    )

    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--interval', '-i',
        type=str,
        default='1h',
        choices=['1m', '5m', '15m', '1h', '4h', '1d'],
        help='Candle interval (default: 1h)'
    )

    parser.add_argument(
        '--balance', '-b',
        type=float,
        default=1000.0,
        help='Initial balance in USDT (default: 1000)'
    )

    parser.add_argument(
        '--enable-shorting',
        action='store_true',
        help='Enable short trades'
    )

    parser.add_argument(
        '--compare-shorting', '-c',
        action='store_true',
        help='Compare LONG-only vs LONG+SHORT performance'
    )

    parser.add_argument(
        '--show-trades', '-t',
        action='store_true',
        help='Show recent trades'
    )

    parser.add_argument(
        '--analyze-regimes', '-r',
        action='store_true',
        help='Analyze performance by market regime'
    )

    parser.add_argument(
        '--save', '-o',
        action='store_true',
        help='Save results to files'
    )

    args = parser.parse_args()

    run_backtest(
        symbol=args.symbol,
        days=args.days,
        start_date=args.start,
        end_date=args.end,
        interval=args.interval,
        initial_balance=args.balance,
        enable_shorting=args.enable_shorting,
        compare_shorting=args.compare_shorting,
        show_trades=args.show_trades,
        analyze_regimes=args.analyze_regimes,
        save_results=args.save
    )


if __name__ == '__main__':
    main()
