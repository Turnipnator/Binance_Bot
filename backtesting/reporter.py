"""
Backtest Reporter
Generates comprehensive performance reports from backtest results.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import json
import os

from .simulator import BacktestResult, SimulatedTrade
from .regime_detector import RegimeDetector, MarketRegime


class BacktestReporter:
    """
    Generates reports and analysis from backtest results.
    """

    def __init__(self, output_dir: str = None):
        """
        Initialize reporter.

        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(__file__), '..', 'data', 'backtest_reports'
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def print_summary(self, result: BacktestResult):
        """Print a summary of backtest results to console."""
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS - {result.symbol}")
        print(f"{'='*70}")
        print(f"Period: {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')}")
        print(f"Initial Balance: ${result.initial_balance:,.2f}")
        print(f"Final Balance: ${result.final_balance:,.2f}")

        print(f"\n--- PERFORMANCE ---")
        pnl_emoji = "+" if result.total_pnl >= 0 else ""
        print(f"Total P&L: {pnl_emoji}${result.total_pnl:,.2f} ({pnl_emoji}{result.total_pnl_percent:.2f}%)")
        print(f"Win Rate: {result.win_rate:.1f}%")
        print(f"Total Trades: {result.total_trades}")
        print(f"  Winners: {result.winning_trades}")
        print(f"  Losers: {result.losing_trades}")

        print(f"\n--- RISK METRICS ---")
        print(f"Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_percent:.1f}%)")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"Profit Factor: {result.profit_factor:.2f}")

        print(f"\n--- TRADE STATISTICS ---")
        print(f"Average Win: ${result.avg_win:.2f}")
        print(f"Average Loss: ${result.avg_loss:.2f}")
        print(f"Largest Win: ${result.largest_win:.2f}")
        print(f"Largest Loss: ${result.largest_loss:.2f}")
        print(f"Avg Trade Duration: {result.avg_trade_duration_hours:.1f} hours")

        # Risk/Reward
        if result.avg_loss != 0:
            rr_ratio = abs(result.avg_win / result.avg_loss)
            print(f"Risk/Reward Ratio: 1:{rr_ratio:.2f}")

        print(f"{'='*70}\n")

    def print_comparison(
        self,
        long_only: BacktestResult,
        long_short: BacktestResult
    ):
        """Print side-by-side comparison of LONG-only vs LONG+SHORT."""
        print(f"\n{'='*80}")
        print(f"STRATEGY COMPARISON - {long_only.symbol}")
        print(f"{'='*80}")
        print(f"Period: {long_only.start_date.strftime('%Y-%m-%d')} to {long_only.end_date.strftime('%Y-%m-%d')}")

        print(f"\n{'Metric':<25} {'LONG Only':>20} {'LONG + SHORT':>20}")
        print(f"{'-'*65}")

        metrics = [
            ('Total P&L ($)', f"${long_only.total_pnl:,.2f}", f"${long_short.total_pnl:,.2f}"),
            ('Total P&L (%)', f"{long_only.total_pnl_percent:+.2f}%", f"{long_short.total_pnl_percent:+.2f}%"),
            ('Win Rate', f"{long_only.win_rate:.1f}%", f"{long_short.win_rate:.1f}%"),
            ('Total Trades', f"{long_only.total_trades}", f"{long_short.total_trades}"),
            ('Winners', f"{long_only.winning_trades}", f"{long_short.winning_trades}"),
            ('Losers', f"{long_only.losing_trades}", f"{long_short.losing_trades}"),
            ('Max Drawdown ($)', f"${long_only.max_drawdown:,.2f}", f"${long_short.max_drawdown:,.2f}"),
            ('Max Drawdown (%)', f"{long_only.max_drawdown_percent:.1f}%", f"{long_short.max_drawdown_percent:.1f}%"),
            ('Sharpe Ratio', f"{long_only.sharpe_ratio:.2f}", f"{long_short.sharpe_ratio:.2f}"),
            ('Profit Factor', f"{long_only.profit_factor:.2f}", f"{long_short.profit_factor:.2f}"),
            ('Avg Win', f"${long_only.avg_win:.2f}", f"${long_short.avg_win:.2f}"),
            ('Avg Loss', f"${long_only.avg_loss:.2f}", f"${long_short.avg_loss:.2f}"),
        ]

        for metric, val1, val2 in metrics:
            print(f"{metric:<25} {val1:>20} {val2:>20}")

        # Winner determination
        print(f"\n{'-'*65}")
        if long_only.total_pnl > long_short.total_pnl:
            diff = long_only.total_pnl - long_short.total_pnl
            print(f"WINNER: LONG ONLY (+${diff:.2f} better)")
        elif long_short.total_pnl > long_only.total_pnl:
            diff = long_short.total_pnl - long_only.total_pnl
            print(f"WINNER: LONG + SHORT (+${diff:.2f} better)")
        else:
            print(f"RESULT: TIE")

        print(f"{'='*80}\n")

    def print_regime_analysis(
        self,
        df: pd.DataFrame,
        trades: List[SimulatedTrade]
    ):
        """Print performance breakdown by market regime."""
        detector = RegimeDetector()
        regime_stats = detector.analyze_regime_performance(df, trades)

        print(f"\n{'='*70}")
        print("PERFORMANCE BY MARKET REGIME")
        print(f"{'='*70}")

        print(f"\n{'Regime':<15} {'Trades':>10} {'Win Rate':>12} {'Total P&L':>15}")
        print(f"{'-'*55}")

        for regime, stats in regime_stats.items():
            if stats['trades'] > 0:
                pnl_str = f"${stats['pnl']:+,.2f}"
                print(f"{regime:<15} {stats['trades']:>10} {stats['win_rate']:>11.1f}% {pnl_str:>15}")

        print(f"{'='*70}\n")

    def print_recent_trades(self, result: BacktestResult, n: int = 10):
        """Print the most recent trades."""
        print(f"\n{'='*70}")
        print(f"LAST {min(n, len(result.trades))} TRADES")
        print(f"{'='*70}")

        print(f"\n{'Date':<12} {'Side':<6} {'Entry':>10} {'Exit':>10} {'P&L':>12} {'Result':<8}")
        print(f"{'-'*60}")

        for trade in result.trades[-n:]:
            date_str = trade.entry_time.strftime('%Y-%m-%d')
            pnl_str = f"${trade.pnl_usdt:+.2f}"
            result_emoji = "WIN" if trade.is_win else "LOSS"

            print(f"{date_str:<12} {trade.side:<6} ${trade.entry_price:>9.2f} ${trade.exit_price:>9.2f} {pnl_str:>12} {result_emoji:<8}")

        print(f"{'='*70}\n")

    def generate_trade_log(self, result: BacktestResult) -> pd.DataFrame:
        """Generate a DataFrame of all trades."""
        trades_data = []

        for trade in result.trades:
            trades_data.append({
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'symbol': trade.symbol,
                'side': trade.side,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'stop_loss': trade.stop_loss,
                'take_profit': trade.take_profit,
                'size_usdt': trade.size_usdt,
                'pnl_usdt': trade.pnl_usdt,
                'pnl_percent': trade.pnl_percent,
                'is_win': trade.is_win,
                'exit_reason': trade.exit_reason,
                'duration_hours': (trade.exit_time - trade.entry_time).total_seconds() / 3600 if trade.exit_time else 0
            })

        return pd.DataFrame(trades_data)

    def save_results(self, result: BacktestResult, filename: str = None):
        """
        Save backtest results to JSON file.

        Args:
            result: BacktestResult to save
            filename: Output filename (auto-generated if not provided)
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_{result.symbol}_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        # Convert to serializable format
        data = {
            'symbol': result.symbol,
            'start_date': result.start_date.isoformat(),
            'end_date': result.end_date.isoformat(),
            'initial_balance': result.initial_balance,
            'final_balance': result.final_balance,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'win_rate': result.win_rate,
            'total_pnl': result.total_pnl,
            'total_pnl_percent': result.total_pnl_percent,
            'max_drawdown': result.max_drawdown,
            'max_drawdown_percent': result.max_drawdown_percent,
            'sharpe_ratio': result.sharpe_ratio,
            'profit_factor': result.profit_factor,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'largest_win': result.largest_win,
            'largest_loss': result.largest_loss,
            'avg_trade_duration_hours': result.avg_trade_duration_hours,
            'trades': [
                {
                    'entry_time': t.entry_time.isoformat(),
                    'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                    'side': t.side,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'pnl_usdt': t.pnl_usdt,
                    'pnl_percent': t.pnl_percent,
                    'is_win': t.is_win,
                    'exit_reason': t.exit_reason
                }
                for t in result.trades
            ]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Results saved to: {filepath}")
        return filepath

    def save_trade_log_csv(self, result: BacktestResult, filename: str = None):
        """Save trade log as CSV."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"trades_{result.symbol}_{timestamp}.csv"

        filepath = os.path.join(self.output_dir, filename)

        df = self.generate_trade_log(result)
        df.to_csv(filepath, index=False)

        print(f"Trade log saved to: {filepath}")
        return filepath
