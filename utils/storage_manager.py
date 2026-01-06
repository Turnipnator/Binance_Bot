"""
Storage Manager for persistent trade data.
Handles all read/write operations to JSON files.
Ensures trade history survives bot restarts.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class StorageManager:
    """
    Manages persistent storage for the trading bot.
    All data is stored as JSON files in the /data directory.
    """

    def __init__(self, data_dir: str = "data"):
        """
        Initialize the storage manager.

        Args:
            data_dir: Directory path for data files (relative to bot root)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Define file paths
        self.trades_file = self.data_dir / "trades.json"
        self.daily_stats_file = self.data_dir / "daily_stats.json"
        self.lifetime_stats_file = self.data_dir / "lifetime_stats.json"

        # Initialize files if they don't exist
        self._init_files()

        logger.info(f"Storage manager initialized. Data directory: {self.data_dir}")

    def _init_files(self):
        """Create empty data files if they don't exist."""

        # trades.json - Historical trade records
        if not self.trades_file.exists():
            self._write_json(self.trades_file, {
                "version": "1.0",
                "trades": [],
                "last_updated": self._now_iso()
            })
            logger.info("Created new trades.json")

        # daily_stats.json - Aggregated daily statistics
        if not self.daily_stats_file.exists():
            self._write_json(self.daily_stats_file, {
                "version": "1.0",
                "days": {},
                "last_updated": self._now_iso()
            })
            logger.info("Created new daily_stats.json")

        # lifetime_stats.json - All-time statistics
        if not self.lifetime_stats_file.exists():
            self._write_json(self.lifetime_stats_file, {
                "version": "1.0",
                "total_trades": 0,
                "last_calculated": self._now_iso()
            })
            logger.info("Created new lifetime_stats.json")

    def _now_iso(self) -> str:
        """Return current UTC time in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _today_str(self) -> str:
        """Return today's date as YYYY-MM-DD string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _read_json(self, filepath: Path) -> Dict:
        """Read and parse a JSON file."""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error reading {filepath}: {e}")
            return {}

    def _write_json(self, filepath: Path, data: Dict):
        """
        Write data to a JSON file with backup.
        Creates a .bak file before overwriting.
        """
        # Create backup of existing file
        if filepath.exists():
            backup_path = filepath.with_suffix('.json.bak')
            shutil.copy2(filepath, backup_path)

        # Write new data
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # TRADE OPERATIONS
    # =========================================================================

    def save_trade(self, trade: Dict) -> bool:
        """
        Save a completed trade to trades.json.
        Also updates daily_stats and lifetime_stats.

        Args:
            trade: Trade data dictionary with fields:
                - pair: Trading pair (e.g., "BTCUSDT")
                - side: "long" or "short"
                - entry_price: Entry price
                - exit_price: Exit price
                - size: Position size in base currency
                - size_quote: Position size in USDT
                - pnl_usdt: Gross P&L
                - pnl_percent: P&L as percentage
                - fees_usdt: Total fees (optional)
                - entry_time: ISO timestamp
                - exit_time: ISO timestamp
                - exit_reason: "take_profit", "stop_loss", "trailing_stop", "manual"
                - is_win: True if profitable

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load current trades
            data = self._read_json(self.trades_file)

            # Generate trade ID if not present
            if 'id' not in trade:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                trade['id'] = f"trade_{timestamp}_{trade.get('pair', 'UNKNOWN')}"

            # Ensure strategy is set (default to momentum)
            if 'strategy' not in trade:
                trade['strategy'] = 'momentum'

            # Calculate duration if times provided
            if 'entry_time' in trade and 'exit_time' in trade and 'duration_seconds' not in trade:
                try:
                    entry = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
                    exit_time = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
                    trade['duration_seconds'] = int((exit_time - entry).total_seconds())
                except Exception:
                    trade['duration_seconds'] = 0

            # Calculate net P&L if fees provided
            if 'net_pnl_usdt' not in trade:
                fees = trade.get('fees_usdt', 0)
                trade['net_pnl_usdt'] = trade.get('pnl_usdt', 0) - fees

            # Ensure is_win is set
            if 'is_win' not in trade:
                trade['is_win'] = trade.get('net_pnl_usdt', 0) > 0

            # Append the new trade
            data['trades'].append(trade)
            data['last_updated'] = self._now_iso()

            # Save trades
            self._write_json(self.trades_file, data)

            # Update daily stats
            self._update_daily_stats(trade)

            # Recalculate lifetime stats
            self._recalculate_lifetime_stats()

            logger.info(f"Saved trade: {trade['id']} - P&L: ${trade.get('net_pnl_usdt', 0):.2f}")
            return True

        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            return False

    def get_trades(self, limit: Optional[int] = None,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> List[Dict]:
        """
        Get trades with optional filtering.

        Args:
            limit: Maximum number of trades to return (most recent first)
            start_date: Filter trades on or after this date (YYYY-MM-DD)
            end_date: Filter trades on or before this date (YYYY-MM-DD)

        Returns:
            List of trade dictionaries
        """
        data = self._read_json(self.trades_file)
        trades = data.get('trades', [])

        # Filter by date if specified
        if start_date:
            trades = [t for t in trades if t.get('exit_time', '')[:10] >= start_date]
        if end_date:
            trades = [t for t in trades if t.get('exit_time', '')[:10] <= end_date]

        # Sort by exit time (most recent first)
        trades.sort(key=lambda x: x.get('exit_time', ''), reverse=True)

        # Apply limit
        if limit:
            trades = trades[:limit]

        return trades

    def get_trades_for_day(self, date_str: str) -> List[Dict]:
        """Get all trades for a specific day."""
        return self.get_trades(start_date=date_str, end_date=date_str)

    def get_winning_trades(self, limit: int = 10) -> List[Dict]:
        """Get the most recent winning trades."""
        data = self._read_json(self.trades_file)
        trades = [t for t in data.get('trades', []) if t.get('is_win', False)]
        trades.sort(key=lambda x: x.get('exit_time', ''), reverse=True)
        return trades[:limit]

    def get_losing_trades(self, limit: int = 10) -> List[Dict]:
        """Get the most recent losing trades."""
        data = self._read_json(self.trades_file)
        trades = [t for t in data.get('trades', []) if not t.get('is_win', True)]
        trades.sort(key=lambda x: x.get('exit_time', ''), reverse=True)
        return trades[:limit]

    def get_trade_count(self) -> int:
        """Get total number of trades."""
        data = self._read_json(self.trades_file)
        return len(data.get('trades', []))

    # =========================================================================
    # DAILY STATS OPERATIONS
    # =========================================================================

    def _update_daily_stats(self, trade: Dict):
        """Update daily statistics after a trade."""
        data = self._read_json(self.daily_stats_file)

        # Get the trade's date
        trade_date = trade.get('exit_time', self._now_iso())[:10]

        # Initialize day if it doesn't exist
        if trade_date not in data.get('days', {}):
            data.setdefault('days', {})[trade_date] = {
                "date": trade_date,
                "realised_pnl": 0,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_fees": 0,
                "best_trade_pnl": 0,
                "best_trade_pair": "",
                "worst_trade_pnl": 0,
                "worst_trade_pair": ""
            }

        day = data['days'][trade_date]

        # Update counters
        day['total_trades'] += 1
        if trade.get('is_win', False):
            day['wins'] += 1
        else:
            day['losses'] += 1

        # Update P&L
        net_pnl = trade.get('net_pnl_usdt', trade.get('pnl_usdt', 0))
        day['realised_pnl'] = round(day['realised_pnl'] + net_pnl, 2)
        day['total_fees'] = round(day['total_fees'] + trade.get('fees_usdt', 0), 2)

        # Update win rate
        if day['total_trades'] > 0:
            day['win_rate'] = round((day['wins'] / day['total_trades']) * 100, 2)

        # Update best/worst trade
        if net_pnl > day['best_trade_pnl']:
            day['best_trade_pnl'] = round(net_pnl, 2)
            day['best_trade_pair'] = trade.get('pair', '')
        if net_pnl < day['worst_trade_pnl']:
            day['worst_trade_pnl'] = round(net_pnl, 2)
            day['worst_trade_pair'] = trade.get('pair', '')

        data['last_updated'] = self._now_iso()
        self._write_json(self.daily_stats_file, data)

    def get_daily_stats(self, date_str: str) -> Optional[Dict]:
        """Get statistics for a specific day."""
        data = self._read_json(self.daily_stats_file)
        return data.get('days', {}).get(date_str)

    def get_today_stats(self) -> Optional[Dict]:
        """Get today's statistics."""
        return self.get_daily_stats(self._today_str())

    def get_stats_for_period(self, start_date: str, end_date: str) -> Dict:
        """
        Get aggregated statistics for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Aggregated statistics dictionary
        """
        data = self._read_json(self.daily_stats_file)
        days = data.get('days', {})

        # Filter days in range
        relevant_days = {k: v for k, v in days.items()
                        if start_date <= k <= end_date}

        if not relevant_days:
            return {
                "period_start": start_date,
                "period_end": end_date,
                "total_trades": 0,
                "realised_pnl": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0
            }

        # Aggregate
        total_trades = sum(d.get('total_trades', 0) for d in relevant_days.values())
        total_wins = sum(d.get('wins', 0) for d in relevant_days.values())
        total_losses = sum(d.get('losses', 0) for d in relevant_days.values())
        total_pnl = sum(d.get('realised_pnl', 0) for d in relevant_days.values())
        total_fees = sum(d.get('total_fees', 0) for d in relevant_days.values())

        return {
            "period_start": start_date,
            "period_end": end_date,
            "days_count": len(relevant_days),
            "total_trades": total_trades,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": round((total_wins / total_trades) * 100, 2) if total_trades > 0 else 0,
            "realised_pnl": round(total_pnl, 2),
            "total_fees": round(total_fees, 2),
            "net_pnl": round(total_pnl, 2)
        }

    # =========================================================================
    # LIFETIME STATS OPERATIONS
    # =========================================================================

    def _recalculate_lifetime_stats(self):
        """Recalculate all lifetime statistics from trades."""
        trades_data = self._read_json(self.trades_file)
        trades = trades_data.get('trades', [])

        if not trades:
            return

        # Sort trades by exit time
        trades.sort(key=lambda x: x.get('exit_time', ''))

        # Basic counts
        total_trades = len(trades)
        wins = [t for t in trades if t.get('is_win', False)]
        losses = [t for t in trades if not t.get('is_win', True)]

        # P&L calculations
        total_pnl = sum(t.get('net_pnl_usdt', t.get('pnl_usdt', 0)) for t in trades)
        total_fees = sum(t.get('fees_usdt', 0) for t in trades)

        # Averages
        avg_win = sum(t.get('net_pnl_usdt', 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get('net_pnl_usdt', 0) for t in losses) / len(losses) if losses else 0

        # Best/worst trades
        best_trade = max(trades, key=lambda x: x.get('net_pnl_usdt', 0)) if trades else {}
        worst_trade = min(trades, key=lambda x: x.get('net_pnl_usdt', 0)) if trades else {}

        # Streak calculation
        current_streak = self._calculate_current_streak(trades)
        best_win_streak, worst_loss_streak = self._calculate_best_streaks(trades)

        # Daily stats for best/worst day
        daily_data = self._read_json(self.daily_stats_file)
        days = daily_data.get('days', {})

        best_day = max(days.items(), key=lambda x: x[1].get('realised_pnl', 0)) if days else (None, {'realised_pnl': 0})
        worst_day = min(days.items(), key=lambda x: x[1].get('realised_pnl', 0)) if days else (None, {'realised_pnl': 0})

        # Calculate profit factor
        total_wins_pnl = abs(sum(t.get('net_pnl_usdt', 0) for t in wins))
        total_losses_pnl = abs(sum(t.get('net_pnl_usdt', 0) for t in losses))
        profit_factor = round(total_wins_pnl / total_losses_pnl, 2) if total_losses_pnl > 0 else 0

        # Build lifetime stats
        stats = {
            "version": "1.0",
            "first_trade_date": trades[0].get('exit_time', '')[:10] if trades else None,
            "last_trade_date": trades[-1].get('exit_time', '')[:10] if trades else None,
            "total_days_trading": len(days),
            "total_trades": total_trades,
            "total_wins": len(wins),
            "total_losses": len(losses),
            "win_rate": round((len(wins) / total_trades) * 100, 2) if total_trades > 0 else 0,
            "total_pnl": round(total_pnl, 2),
            "total_fees": round(total_fees, 2),
            "net_pnl": round(total_pnl, 2),
            "average_daily_pnl": round(total_pnl / len(days), 2) if days else 0,
            "best_day": {
                "date": best_day[0],
                "pnl": round(best_day[1].get('realised_pnl', 0), 2)
            } if best_day[0] else None,
            "worst_day": {
                "date": worst_day[0],
                "pnl": round(worst_day[1].get('realised_pnl', 0), 2)
            } if worst_day[0] else None,
            "current_streak": current_streak,
            "best_win_streak": best_win_streak,
            "worst_loss_streak": worst_loss_streak,
            "average_win": round(avg_win, 2),
            "average_loss": round(avg_loss, 2),
            "largest_win": {
                "pnl": round(best_trade.get('net_pnl_usdt', 0), 2),
                "pair": best_trade.get('pair', ''),
                "date": best_trade.get('exit_time', '')[:10]
            } if best_trade else None,
            "largest_loss": {
                "pnl": round(worst_trade.get('net_pnl_usdt', 0), 2),
                "pair": worst_trade.get('pair', ''),
                "date": worst_trade.get('exit_time', '')[:10]
            } if worst_trade else None,
            "profit_factor": profit_factor,
            "last_calculated": self._now_iso()
        }

        self._write_json(self.lifetime_stats_file, stats)

    def _calculate_current_streak(self, trades: List[Dict]) -> Dict:
        """Calculate the current win/loss streak."""
        if not trades:
            return {"type": "none", "count": 0}

        # Start from most recent trade
        streak_type = "win" if trades[-1].get('is_win', False) else "loss"
        count = 0

        for trade in reversed(trades):
            is_win = trade.get('is_win', False)
            if (streak_type == "win" and is_win) or (streak_type == "loss" and not is_win):
                count += 1
            else:
                break

        return {"type": streak_type, "count": count}

    def _calculate_best_streaks(self, trades: List[Dict]) -> tuple:
        """Calculate best win streak and worst loss streak."""
        if not trades:
            return 0, 0

        best_win = 0
        worst_loss = 0
        current_win = 0
        current_loss = 0

        for trade in trades:
            if trade.get('is_win', False):
                current_win += 1
                current_loss = 0
                best_win = max(best_win, current_win)
            else:
                current_loss += 1
                current_win = 0
                worst_loss = max(worst_loss, current_loss)

        return best_win, worst_loss

    def get_lifetime_stats(self) -> Dict:
        """Get lifetime statistics."""
        return self._read_json(self.lifetime_stats_file)

    def recalculate_all_stats(self):
        """Force recalculation of all statistics from trades."""
        logger.info("Recalculating all statistics from trade history...")

        # Clear and rebuild daily stats from trades
        trades_data = self._read_json(self.trades_file)
        trades = trades_data.get('trades', [])

        # Reset daily stats
        daily_data = {
            "version": "1.0",
            "days": {},
            "last_updated": self._now_iso()
        }
        self._write_json(self.daily_stats_file, daily_data)

        # Rebuild from each trade
        for trade in trades:
            self._update_daily_stats(trade)

        # Recalculate lifetime stats
        self._recalculate_lifetime_stats()

        logger.info(f"Recalculated stats for {len(trades)} trades")


# Singleton instance for easy access
_storage_instance: Optional[StorageManager] = None


def get_storage() -> StorageManager:
    """Get or create the storage manager singleton."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance
