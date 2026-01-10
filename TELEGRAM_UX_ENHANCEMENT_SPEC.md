# Telegram UX Enhancement Specification

## ⚠️ CRITICAL: BACKUP FIRST

**Before making ANY changes, create a backup of the working system:**

```bash
# On your VPS, backup the entire bot directory
cp -r ~/Binance_Bot ~/Binance_Bot_BACKUP_$(date +%Y%m%d_%H%M%S)

# If using Docker, also save the current image
docker commit binance_bot binance_bot_backup:$(date +%Y%m%d)

# Verify backup exists
ls -la ~/Binance_Bot_BACKUP_*
```

**DO NOT proceed with implementation until backup is confirmed.**

---

## Overview

This specification details enhancements to the Telegram bot interface for the Binance Trading Bot. The primary goal is to add **data persistence** so that trade history, statistics, and performance data survive bot restarts.

### Current State

The bot currently has these working commands:
- `/status` - Bot status and summary
- `/positions` - View open positions
- `/pnl` - P&L reports (daily/weekly/monthly/all-time)
- `/balance` - Account balance
- `/stop` - Stop trading (keep positions)
- `/resume` - Resume trading
- `/emergency` - Emergency stop (close all)
- `/help` - Show help message

**Problem:** All trade history is lost when the bot restarts. This is unacceptable for a commercial product.

### Goals

1. Implement persistent storage for all trade data
2. Enhance existing commands to use persisted data
3. Add new commands for better user experience
4. Improve notification formatting
5. Make the bot suitable for non-technical users

---

## Part 1: Persistence Layer

### Directory Structure

Create a `/data` directory relative to the bot's working directory:

```
Binance_Bot/
├── data/                       # NEW - Persistent storage
│   ├── trades.json            # All historical trades
│   ├── daily_stats.json       # Daily aggregated statistics
│   ├── lifetime_stats.json    # Lifetime statistics (calculated)
│   └── state.json             # Current bot state for recovery
├── telegram_bot.py            # Existing - will be modified
├── trading_bot.py             # Existing - will be modified
└── ... (other existing files)
```

### Data Schemas

#### trades.json

Stores every completed trade. Append-only (never delete entries).

```json
{
  "version": "1.0",
  "trades": [
    {
      "id": "trade_20250106_143845_BTCUSDT",
      "pair": "BTCUSDT",
      "strategy": "momentum",
      "side": "long",
      "entry_price": 67432.00,
      "exit_price": 67891.00,
      "size": 0.1,
      "size_quote": 6743.20,
      "pnl_usdt": 45.90,
      "pnl_percent": 1.36,
      "fees_usdt": 2.70,
      "net_pnl_usdt": 43.20,
      "entry_time": "2025-01-06T10:15:32Z",
      "exit_time": "2025-01-06T14:38:45Z",
      "duration_seconds": 15793,
      "exit_reason": "take_profit",
      "is_win": true
    }
  ],
  "last_updated": "2025-01-06T14:38:45Z"
}
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID: `trade_{date}_{time}_{pair}` |
| `pair` | string | Trading pair (e.g., "BTCUSDT") |
| `strategy` | string | Strategy name: "momentum", "grid", "mean_reversion" |
| `side` | string | "long" or "short" |
| `entry_price` | float | Entry price in quote currency |
| `exit_price` | float | Exit price in quote currency |
| `size` | float | Position size in base currency |
| `size_quote` | float | Position size in quote currency (USDT) |
| `pnl_usdt` | float | Gross P&L before fees |
| `pnl_percent` | float | P&L as percentage of position |
| `fees_usdt` | float | Total fees paid |
| `net_pnl_usdt` | float | Net P&L after fees |
| `entry_time` | string | ISO 8601 timestamp |
| `exit_time` | string | ISO 8601 timestamp |
| `duration_seconds` | int | Trade duration in seconds |
| `exit_reason` | string | "take_profit", "stop_loss", "trailing_stop", "manual", "emergency" |
| `is_win` | bool | True if net_pnl_usdt > 0 |

#### daily_stats.json

Aggregated daily statistics. Updated at end of each trade and at day rollover.

```json
{
  "version": "1.0",
  "days": {
    "2025-01-06": {
      "date": "2025-01-06",
      "starting_balance": 2759.89,
      "ending_balance": 2847.32,
      "realised_pnl": 87.43,
      "unrealised_pnl": 0.00,
      "total_trades": 7,
      "wins": 5,
      "losses": 2,
      "win_rate": 71.43,
      "total_fees": 8.21,
      "best_trade_pnl": 42.10,
      "best_trade_pair": "BTCUSDT",
      "worst_trade_pnl": -18.30,
      "worst_trade_pair": "AVAXUSDT",
      "strategies": {
        "momentum": {"trades": 3, "pnl": 52.30, "wins": 2, "losses": 1},
        "grid": {"trades": 3, "pnl": 28.40, "wins": 2, "losses": 1},
        "mean_reversion": {"trades": 1, "pnl": 6.73, "wins": 1, "losses": 0}
      }
    }
  },
  "last_updated": "2025-01-06T23:59:59Z"
}
```

#### lifetime_stats.json

Calculated from trades.json. Recalculated on startup and after each trade.

```json
{
  "version": "1.0",
  "first_trade_date": "2024-12-14",
  "last_trade_date": "2025-01-06",
  "total_days_trading": 24,
  "total_trades": 187,
  "total_wins": 112,
  "total_losses": 75,
  "win_rate": 59.89,
  "total_pnl": 847.32,
  "total_fees": 156.40,
  "net_pnl": 690.92,
  "average_daily_pnl": 35.30,
  "best_day": {
    "date": "2024-12-28",
    "pnl": 124.50
  },
  "worst_day": {
    "date": "2025-01-02",
    "pnl": -67.20
  },
  "current_streak": {
    "type": "win",
    "count": 3
  },
  "best_win_streak": 8,
  "worst_loss_streak": 4,
  "average_win": 18.42,
  "average_loss": -12.87,
  "largest_win": {
    "pnl": 89.50,
    "pair": "BTCUSDT",
    "date": "2024-12-28"
  },
  "largest_loss": {
    "pnl": -34.20,
    "pair": "SOLUSDT",
    "date": "2025-01-02"
  },
  "profit_factor": 1.43,
  "strategies": {
    "momentum": {
      "trades": 48,
      "wins": 30,
      "losses": 18,
      "win_rate": 62.50,
      "total_pnl": 412.30
    },
    "grid": {
      "trades": 89,
      "wins": 52,
      "losses": 37,
      "win_rate": 58.43,
      "total_pnl": 298.70
    },
    "mean_reversion": {
      "trades": 50,
      "wins": 30,
      "losses": 20,
      "win_rate": 60.00,
      "total_pnl": 136.32
    }
  },
  "last_calculated": "2025-01-06T14:38:45Z"
}
```

#### state.json

Current bot state for recovery after restart.

```json
{
  "version": "1.0",
  "bot_started": "2025-01-03T08:00:00Z",
  "is_running": true,
  "is_paused": false,
  "current_balance": 2847.32,
  "open_positions": [
    {
      "pair": "BTCUSDT",
      "strategy": "momentum",
      "side": "long",
      "entry_price": 67432.00,
      "size": 0.1,
      "entry_time": "2025-01-06T10:15:32Z",
      "stop_loss": 66100.00,
      "take_profit": 69500.00
    }
  ],
  "daily_target_reached": false,
  "daily_loss_limit_reached": false,
  "last_updated": "2025-01-06T14:38:45Z"
}
```

### Persistence Implementation

#### Storage Manager Class

Create a new file `utils/storage_manager.py`:

```python
"""
Storage Manager for persistent trade data.
Handles all read/write operations to JSON files.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil
import logging

logger = logging.getLogger(__name__)

class StorageManager:
    """
    Manages persistent storage for the trading bot.
    All data is stored as JSON files in the /data directory.
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialise the storage manager.
        
        Args:
            data_dir: Directory path for data files (relative to bot root)
        """
        # Create the data directory if it doesn't exist
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Define file paths
        self.trades_file = self.data_dir / "trades.json"
        self.daily_stats_file = self.data_dir / "daily_stats.json"
        self.lifetime_stats_file = self.data_dir / "lifetime_stats.json"
        self.state_file = self.data_dir / "state.json"
        
        # Initialise files if they don't exist
        self._init_files()
        
        logger.info(f"Storage manager initialised. Data directory: {self.data_dir}")
    
    def _init_files(self):
        """Create empty data files if they don't exist."""
        
        # trades.json
        if not self.trades_file.exists():
            self._write_json(self.trades_file, {
                "version": "1.0",
                "trades": [],
                "last_updated": self._now_iso()
            })
            logger.info("Created new trades.json")
        
        # daily_stats.json
        if not self.daily_stats_file.exists():
            self._write_json(self.daily_stats_file, {
                "version": "1.0",
                "days": {},
                "last_updated": self._now_iso()
            })
            logger.info("Created new daily_stats.json")
        
        # lifetime_stats.json
        if not self.lifetime_stats_file.exists():
            self._write_json(self.lifetime_stats_file, {
                "version": "1.0",
                "total_trades": 0,
                "last_calculated": self._now_iso()
            })
            logger.info("Created new lifetime_stats.json")
        
        # state.json
        if not self.state_file.exists():
            self._write_json(self.state_file, {
                "version": "1.0",
                "bot_started": self._now_iso(),
                "is_running": False,
                "is_paused": False,
                "open_positions": [],
                "last_updated": self._now_iso()
            })
            logger.info("Created new state.json")
    
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
            trade: Trade data dictionary (see schema above)
        
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
            
            # Append the new trade
            data['trades'].append(trade)
            data['last_updated'] = self._now_iso()
            
            # Save trades
            self._write_json(self.trades_file, data)
            
            # Update daily stats
            self._update_daily_stats(trade)
            
            # Recalculate lifetime stats
            self._recalculate_lifetime_stats()
            
            logger.info(f"Saved trade: {trade['id']}")
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
    
    # =========================================================================
    # DAILY STATS OPERATIONS
    # =========================================================================
    
    def _update_daily_stats(self, trade: Dict):
        """Update daily statistics after a trade."""
        data = self._read_json(self.daily_stats_file)
        
        # Get the trade's date
        trade_date = trade.get('exit_time', self._now_iso())[:10]
        
        # Initialise day if it doesn't exist
        if trade_date not in data.get('days', {}):
            data.setdefault('days', {})[trade_date] = {
                "date": trade_date,
                "starting_balance": 0,  # Will be set properly elsewhere
                "ending_balance": 0,
                "realised_pnl": 0,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_fees": 0,
                "best_trade_pnl": 0,
                "best_trade_pair": "",
                "worst_trade_pnl": 0,
                "worst_trade_pair": "",
                "strategies": {}
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
        day['realised_pnl'] += net_pnl
        day['total_fees'] += trade.get('fees_usdt', 0)
        
        # Update win rate
        if day['total_trades'] > 0:
            day['win_rate'] = round((day['wins'] / day['total_trades']) * 100, 2)
        
        # Update best/worst trade
        if net_pnl > day['best_trade_pnl']:
            day['best_trade_pnl'] = net_pnl
            day['best_trade_pair'] = trade.get('pair', '')
        if net_pnl < day['worst_trade_pnl']:
            day['worst_trade_pnl'] = net_pnl
            day['worst_trade_pair'] = trade.get('pair', '')
        
        # Update strategy stats
        strategy = trade.get('strategy', 'unknown')
        if strategy not in day['strategies']:
            day['strategies'][strategy] = {"trades": 0, "pnl": 0, "wins": 0, "losses": 0}
        
        day['strategies'][strategy]['trades'] += 1
        day['strategies'][strategy]['pnl'] += net_pnl
        if trade.get('is_win', False):
            day['strategies'][strategy]['wins'] += 1
        else:
            day['strategies'][strategy]['losses'] += 1
        
        data['last_updated'] = self._now_iso()
        self._write_json(self.daily_stats_file, data)
    
    def get_daily_stats(self, date_str: str) -> Optional[Dict]:
        """Get statistics for a specific day."""
        data = self._read_json(self.daily_stats_file)
        return data.get('days', {}).get(date_str)
    
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
                "realised_pnl": 0
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
            "net_pnl": round(total_pnl - total_fees, 2)
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
        best_trade = max(trades, key=lambda x: x.get('net_pnl_usdt', 0))
        worst_trade = min(trades, key=lambda x: x.get('net_pnl_usdt', 0))
        
        # Streak calculation
        current_streak = self._calculate_current_streak(trades)
        best_win_streak, worst_loss_streak = self._calculate_best_streaks(trades)
        
        # Strategy breakdown
        strategies = {}
        for trade in trades:
            strat = trade.get('strategy', 'unknown')
            if strat not in strategies:
                strategies[strat] = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0}
            strategies[strat]['trades'] += 1
            strategies[strat]['total_pnl'] += trade.get('net_pnl_usdt', 0)
            if trade.get('is_win', False):
                strategies[strat]['wins'] += 1
            else:
                strategies[strat]['losses'] += 1
        
        # Add win rates to strategies
        for strat in strategies:
            s = strategies[strat]
            s['win_rate'] = round((s['wins'] / s['trades']) * 100, 2) if s['trades'] > 0 else 0
            s['total_pnl'] = round(s['total_pnl'], 2)
        
        # Daily stats for best/worst day
        daily_data = self._read_json(self.daily_stats_file)
        days = daily_data.get('days', {})
        
        best_day = max(days.items(), key=lambda x: x[1].get('realised_pnl', 0)) if days else (None, {'realised_pnl': 0})
        worst_day = min(days.items(), key=lambda x: x[1].get('realised_pnl', 0)) if days else (None, {'realised_pnl': 0})
        
        # Build lifetime stats
        stats = {
            "version": "1.0",
            "first_trade_date": trades[0].get('exit_time', '')[:10],
            "last_trade_date": trades[-1].get('exit_time', '')[:10],
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
            },
            "largest_loss": {
                "pnl": round(worst_trade.get('net_pnl_usdt', 0), 2),
                "pair": worst_trade.get('pair', ''),
                "date": worst_trade.get('exit_time', '')[:10]
            },
            "profit_factor": round(abs(sum(t.get('net_pnl_usdt', 0) for t in wins)) / 
                                  abs(sum(t.get('net_pnl_usdt', 0) for t in losses)), 2) 
                           if losses and sum(t.get('net_pnl_usdt', 0) for t in losses) != 0 else 0,
            "strategies": strategies,
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
    
    # =========================================================================
    # STATE OPERATIONS
    # =========================================================================
    
    def save_state(self, state: Dict):
        """Save current bot state."""
        state['last_updated'] = self._now_iso()
        state['version'] = "1.0"
        self._write_json(self.state_file, state)
    
    def get_state(self) -> Dict:
        """Get saved bot state."""
        return self._read_json(self.state_file)
    
    def update_state(self, **kwargs):
        """Update specific state fields."""
        state = self.get_state()
        state.update(kwargs)
        self.save_state(state)
```

### Integration Points

The `StorageManager` needs to be integrated into the existing code at these points:

1. **On trade close** (in `trading_bot.py` or wherever trades are finalised):
   ```python
   # After a trade closes successfully
   storage.save_trade({
       "pair": trade.pair,
       "strategy": trade.strategy,
       "side": trade.side,
       # ... all other fields
   })
   ```

2. **On bot startup** (in `trading_bot.py`):
   ```python
   # Initialise storage manager
   from utils.storage_manager import StorageManager
   storage = StorageManager()
   
   # Log loaded data
   stats = storage.get_lifetime_stats()
   logger.info(f"Loaded {stats.get('total_trades', 0)} historical trades")
   ```

3. **In Telegram commands** (in `telegram_bot.py`):
   ```python
   # Pass storage manager to telegram bot
   # Use it in command handlers
   ```

---

## Part 2: Enhanced Telegram Commands

### Updated Help Menu

```
🤖 TRADING BOT COMMANDS

📊 MONITORING
/status      - Bot status and health check
/balance     - Account balance (total, allocated, available)
/positions   - Open positions with live P&L
/heat        - Portfolio risk exposure

💰 PERFORMANCE  
/pnl         - Today's P&L summary
/pnl weekly  - This week's P&L
/pnl monthly - This month's P&L
/pnl all     - All-time performance
/trades      - Last 10 closed trades
/trades [n]  - Last n trades (e.g., /trades 25)
/winners     - Last 10 winning trades
/losers      - Last 10 losing trades
/stats       - Comprehensive statistics

🎮 CONTROL
/pause       - Pause new trades (keeps monitoring)
/resume      - Resume trading
/stop        - Stop bot completely
/emergency   - ⚠️ Close ALL positions NOW

ℹ️ HELP & INFO
/help        - This menu
/explain     - What is the bot doing? (plain English)
/health      - Simple health check with recommendations

📤 EXPORT
/export      - Download trade history as CSV

🔔 Notifications are automatic for:
• Trade opened/closed
• Daily target reached  
• Stop loss triggered
• Bot errors
```

### Command Implementations

#### /pnl (Enhanced)

```python
async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /pnl command with optional period argument.
    
    Usage:
        /pnl          - Today's P&L
        /pnl daily    - Same as /pnl
        /pnl weekly   - This week (Mon-Sun)
        /pnl monthly  - This calendar month
        /pnl all      - All-time statistics
        /pnl 2025-01-05  - Specific date
    """
    args = context.args
    period = args[0].lower() if args else "daily"
    
    today = datetime.now(timezone.utc)
    
    if period == "daily" or period == today.strftime("%Y-%m-%d"):
        # Today's stats
        stats = storage.get_daily_stats(today.strftime("%Y-%m-%d"))
        
        if not stats:
            await update.message.reply_text(
                "📊 TODAY'S PERFORMANCE\n\n"
                "No trades completed today yet.\n"
                "Check /positions for open trades."
            )
            return
        
        # Get open positions for unrealised P&L
        # (This would come from your existing position tracking)
        unrealised_pnl = calculate_unrealised_pnl()  # Implement this
        
        message = (
            f"📊 TODAY'S PERFORMANCE ({today.strftime('%d %b %Y')})\n\n"
            f"Realised P&L: {format_pnl(stats['realised_pnl'])}\n"
            f"Unrealised P&L: {format_pnl(unrealised_pnl)} (open positions)\n"
            f"{'─' * 25}\n"
            f"Net P&L: {format_pnl(stats['realised_pnl'] + unrealised_pnl)}\n\n"
            f"Trades: {stats['total_trades']} "
            f"({stats['wins']}W / {stats['losses']}L)\n"
            f"Win Rate: {stats['win_rate']}%\n"
        )
        
        if stats['best_trade_pair']:
            message += f"Best: {stats['best_trade_pair']} {format_pnl(stats['best_trade_pnl'])}\n"
        if stats['worst_trade_pair']:
            message += f"Worst: {stats['worst_trade_pair']} {format_pnl(stats['worst_trade_pnl'])}\n"
        
        # Add streak info
        lifetime = storage.get_lifetime_stats()
        streak = lifetime.get('current_streak', {})
        if streak.get('count', 0) >= 3:
            emoji = "🔥" if streak['type'] == "win" else "❄️"
            message += f"\nStreak: {emoji} {streak['count']} {streak['type']}s in a row"
        
        await update.message.reply_text(message)
    
    elif period == "weekly":
        # This week (Monday to today)
        start_of_week = today - timedelta(days=today.weekday())
        stats = storage.get_stats_for_period(
            start_of_week.strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d")
        )
        
        message = (
            f"📊 THIS WEEK'S PERFORMANCE\n"
            f"({start_of_week.strftime('%d %b')} - {today.strftime('%d %b %Y')})\n\n"
            f"Total P&L: {format_pnl(stats['realised_pnl'])}\n"
            f"Trades: {stats['total_trades']} "
            f"({stats['wins']}W / {stats['losses']}L)\n"
            f"Win Rate: {stats['win_rate']}%\n"
            f"Trading Days: {stats['days_count']}"
        )
        
        await update.message.reply_text(message)
    
    elif period == "monthly":
        # This calendar month
        start_of_month = today.replace(day=1)
        stats = storage.get_stats_for_period(
            start_of_month.strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d")
        )
        
        message = (
            f"📊 THIS MONTH'S PERFORMANCE\n"
            f"({today.strftime('%B %Y')})\n\n"
            f"Total P&L: {format_pnl(stats['realised_pnl'])}\n"
            f"Trades: {stats['total_trades']} "
            f"({stats['wins']}W / {stats['losses']}L)\n"
            f"Win Rate: {stats['win_rate']}%\n"
            f"Trading Days: {stats['days_count']}"
        )
        
        await update.message.reply_text(message)
    
    elif period == "all":
        # All-time statistics
        stats = storage.get_lifetime_stats()
        
        if stats.get('total_trades', 0) == 0:
            await update.message.reply_text(
                "📊 ALL-TIME PERFORMANCE\n\n"
                "No trade history yet.\n"
                "Statistics will appear after your first completed trade."
            )
            return
        
        message = (
            f"📊 ALL-TIME PERFORMANCE\n\n"
            f"Period: {stats['first_trade_date']} → {stats['last_trade_date']}\n"
            f"Trading Days: {stats['total_days_trading']}\n"
            f"{'─' * 25}\n"
            f"Total P&L: {format_pnl(stats['total_pnl'])}\n"
            f"Daily Average: {format_pnl(stats['average_daily_pnl'])}\n\n"
            f"Total Trades: {stats['total_trades']}\n"
            f"Winners: {stats['total_wins']} ({stats['win_rate']}%)\n"
            f"Losers: {stats['total_losses']}\n\n"
            f"Avg Win: {format_pnl(stats['average_win'])}\n"
            f"Avg Loss: {format_pnl(stats['average_loss'])}\n"
            f"Profit Factor: {stats['profit_factor']}\n"
        )
        
        if stats.get('best_day'):
            message += f"\nBest Day: {format_pnl(stats['best_day']['pnl'])} ({stats['best_day']['date']})"
        if stats.get('worst_day'):
            message += f"\nWorst Day: {format_pnl(stats['worst_day']['pnl'])} ({stats['worst_day']['date']})"
        
        await update.message.reply_text(message)
    
    else:
        # Assume it's a specific date
        try:
            # Validate date format
            datetime.strptime(period, "%Y-%m-%d")
            stats = storage.get_daily_stats(period)
            
            if not stats:
                await update.message.reply_text(f"No trades found for {period}")
                return
            
            message = (
                f"📊 PERFORMANCE FOR {period}\n\n"
                f"P&L: {format_pnl(stats['realised_pnl'])}\n"
                f"Trades: {stats['total_trades']} "
                f"({stats['wins']}W / {stats['losses']}L)\n"
                f"Win Rate: {stats['win_rate']}%"
            )
            
            await update.message.reply_text(message)
            
        except ValueError:
            await update.message.reply_text(
                "❓ Unknown period. Use:\n"
                "/pnl daily\n"
                "/pnl weekly\n"
                "/pnl monthly\n"
                "/pnl all\n"
                "/pnl 2025-01-05"
            )


def format_pnl(value: float) -> str:
    """Format P&L value with sign and colour indicator."""
    if value >= 0:
        return f"+${value:.2f} ✅"
    else:
        return f"-${abs(value):.2f} 🔻"
```

#### /trades (New)

```python
async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show recent trade history.
    
    Usage:
        /trades      - Last 10 trades
        /trades 25   - Last 25 trades
        /trades today - Today's trades only
    """
    args = context.args
    
    if args and args[0].lower() == "today":
        trades = storage.get_trades_for_day(
            datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        title = "TODAY'S TRADES"
    else:
        limit = int(args[0]) if args and args[0].isdigit() else 10
        limit = min(limit, 50)  # Cap at 50
        trades = storage.get_trades(limit=limit)
        title = f"LAST {len(trades)} TRADES"
    
    if not trades:
        await update.message.reply_text("No trade history found.")
        return
    
    message = f"📜 {title}\n\n"
    
    for trade in trades:
        # Determine emoji based on win/loss
        emoji = "✅" if trade.get('is_win', False) else "❌"
        
        # Format P&L
        pnl = trade.get('net_pnl_usdt', trade.get('pnl_usdt', 0))
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        
        # Format duration
        duration_secs = trade.get('duration_seconds', 0)
        if duration_secs < 3600:
            duration = f"{duration_secs // 60}m"
        else:
            duration = f"{duration_secs // 3600}h {(duration_secs % 3600) // 60}m"
        
        # Build line
        message += (
            f"{emoji} {trade['pair']} | {pnl_str} ({trade.get('pnl_percent', 0):.1f}%) | "
            f"{duration} | {trade.get('strategy', '?')[:3].upper()}\n"
        )
    
    # Summary
    wins = sum(1 for t in trades if t.get('is_win', False))
    total_pnl = sum(t.get('net_pnl_usdt', 0) for t in trades)
    
    message += (
        f"\n{'─' * 30}\n"
        f"Summary: {wins}W/{len(trades)-wins}L | "
        f"Total: {format_pnl(total_pnl)}"
    )
    
    await update.message.reply_text(message)
```

#### /winners and /losers (New)

```python
async def cmd_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last 10 winning trades."""
    trades = storage.get_winning_trades(limit=10)
    
    if not trades:
        await update.message.reply_text("No winning trades yet! 🤞")
        return
    
    message = "🏆 LAST 10 WINNERS\n\n"
    
    for trade in trades:
        pnl = trade.get('net_pnl_usdt', 0)
        date = trade.get('exit_time', '')[:10]
        message += (
            f"✅ {trade['pair']} | +${pnl:.2f} "
            f"(+{trade.get('pnl_percent', 0):.1f}%) | {date}\n"
        )
    
    avg_win = sum(t.get('net_pnl_usdt', 0) for t in trades) / len(trades)
    message += f"\nAverage Win: +${avg_win:.2f}"
    
    await update.message.reply_text(message)


async def cmd_losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last 10 losing trades."""
    trades = storage.get_losing_trades(limit=10)
    
    if not trades:
        await update.message.reply_text("No losing trades! 🎉")
        return
    
    message = "📉 LAST 10 LOSSES\n\n"
    
    for trade in trades:
        pnl = trade.get('net_pnl_usdt', 0)
        date = trade.get('exit_time', '')[:10]
        reason = trade.get('exit_reason', 'unknown')
        message += (
            f"❌ {trade['pair']} | -${abs(pnl):.2f} "
            f"({trade.get('pnl_percent', 0):.1f}%) | {reason} | {date}\n"
        )
    
    avg_loss = sum(t.get('net_pnl_usdt', 0) for t in trades) / len(trades)
    message += f"\nAverage Loss: -${abs(avg_loss):.2f}"
    
    await update.message.reply_text(message)
```

#### /stats (New)

```python
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show comprehensive lifetime statistics."""
    stats = storage.get_lifetime_stats()
    
    if stats.get('total_trades', 0) == 0:
        await update.message.reply_text(
            "📈 LIFETIME STATISTICS\n\n"
            "No trade history yet.\n"
            "Complete your first trade to see statistics."
        )
        return
    
    message = (
        f"📈 LIFETIME STATISTICS\n\n"
        f"📅 Period\n"
        f"{stats['first_trade_date']} → {stats['last_trade_date']}\n"
        f"Trading days: {stats['total_days_trading']}\n\n"
        f"💰 Performance\n"
        f"Total P&L: {format_pnl(stats['total_pnl'])}\n"
        f"Daily Avg: {format_pnl(stats['average_daily_pnl'])}\n"
        f"Profit Factor: {stats['profit_factor']}\n\n"
        f"📊 Trade Stats\n"
        f"Total: {stats['total_trades']} "
        f"({stats['total_wins']}W / {stats['total_losses']}L)\n"
        f"Win Rate: {stats['win_rate']}%\n"
        f"Avg Win: +${stats['average_win']:.2f}\n"
        f"Avg Loss: -${abs(stats['average_loss']):.2f}\n\n"
        f"🏆 Records\n"
    )
    
    if stats.get('largest_win'):
        message += (
            f"Best Trade: +${stats['largest_win']['pnl']:.2f} "
            f"({stats['largest_win']['pair']})\n"
        )
    if stats.get('largest_loss'):
        message += (
            f"Worst Trade: -${abs(stats['largest_loss']['pnl']):.2f} "
            f"({stats['largest_loss']['pair']})\n"
        )
    if stats.get('best_day'):
        message += f"Best Day: +${stats['best_day']['pnl']:.2f} ({stats['best_day']['date']})\n"
    if stats.get('worst_day'):
        message += f"Worst Day: -${abs(stats['worst_day']['pnl']):.2f} ({stats['worst_day']['date']})\n"
    
    message += f"Best Win Streak: {stats['best_win_streak']}\n"
    
    # Current streak
    streak = stats.get('current_streak', {})
    if streak.get('count', 0) >= 2:
        emoji = "🔥" if streak['type'] == "win" else "❄️"
        message += f"\nCurrent: {emoji} {streak['count']} {streak['type']}s"
    
    # Strategy breakdown
    if stats.get('strategies'):
        message += "\n\n📋 By Strategy\n"
        for strat, data in stats['strategies'].items():
            message += (
                f"• {strat.title()}: {format_pnl(data['total_pnl'])} "
                f"({data['trades']} trades, {data['win_rate']}% win)\n"
            )
    
    await update.message.reply_text(message)
```

#### /explain (New - User Friendly)

```python
async def cmd_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Explain what the bot is doing in plain English.
    Designed for non-technical users.
    """
    # Get current state
    state = storage.get_state()
    positions = get_open_positions()  # Your existing function
    today_stats = storage.get_daily_stats(
        datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    
    # Build explanation
    message = "🤖 WHAT I'M DOING RIGHT NOW\n\n"
    
    # Status
    if not state.get('is_running', False):
        message += "I'm currently STOPPED and not trading.\n"
        message += "Use /resume to start me again.\n"
        await update.message.reply_text(message)
        return
    
    if state.get('is_paused', False):
        message += "I'm PAUSED - monitoring positions but not opening new trades.\n"
        message += "Use /resume to start trading again.\n\n"
    else:
        message += "I'm actively monitoring 10 trading pairs for opportunities.\n\n"
    
    # Positions
    if positions:
        total_value = sum(p.get('value_usdt', 0) for p in positions)
        unrealised = sum(p.get('unrealised_pnl', 0) for p in positions)
        
        message += f"Currently:\n"
        message += f"• I have {len(positions)} open trade(s) worth ${total_value:,.0f}\n"
        message += f"• I'm {'+' if unrealised >= 0 else ''}{unrealised:.2f} on these positions\n"
        
        # Calculate risk
        heat = calculate_portfolio_heat()  # Your existing function
        message += f"• I'm using {heat:.1f}% of your risk budget "
        if heat < 10:
            message += "(safe zone ✅)\n"
        elif heat < 15:
            message += "(moderate ⚠️)\n"
        else:
            message += "(high exposure 🔴)\n"
    else:
        message += "Currently:\n"
        message += "• I have no open positions\n"
        message += "• I'm watching for entry signals\n"
    
    # What strategies are looking for
    message += "\nMy strategies are looking for:\n"
    message += "• Momentum: Strong trend signals with volume confirmation\n"
    message += "• Grid: Price ranges to trade within\n"
    message += "• Mean Reversion: Oversold/overbought bounces\n"
    
    # Recent activity
    if today_stats:
        message += (
            f"\nToday so far: {today_stats['total_trades']} trades, "
            f"{format_pnl(today_stats['realised_pnl'])}\n"
        )
    
    # Health
    message += "\n"
    if state.get('is_running') and not state.get('daily_loss_limit_reached'):
        message += "Everything looks healthy ✅"
    elif state.get('daily_loss_limit_reached'):
        message += "⚠️ Daily loss limit reached - I've stopped trading for today"
    elif state.get('daily_target_reached'):
        message += "🎯 Daily target reached! I've paused new entries"
    
    await update.message.reply_text(message)
```

#### /health (New - User Friendly)

```python
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Simple health check with green ticks and recommendations.
    Designed for non-technical users.
    """
    state = storage.get_state()
    
    message = "🏥 BOT HEALTH CHECK\n\n"
    
    recommendations = []
    
    # Bot status
    if state.get('is_running', False):
        uptime = calculate_uptime(state.get('bot_started'))  # Implement this
        message += f"✅ Bot Status: Running ({uptime})\n"
    else:
        message += "❌ Bot Status: Stopped\n"
        recommendations.append("Use /resume to start the bot")
    
    # Binance connection
    try:
        latency = test_binance_connection()  # Implement this
        if latency < 100:
            message += f"✅ Binance Connection: Excellent ({latency}ms)\n"
        elif latency < 500:
            message += f"⚠️ Binance Connection: Slow ({latency}ms)\n"
        else:
            message += f"🔴 Binance Connection: Very Slow ({latency}ms)\n"
            recommendations.append("Check your internet connection")
    except Exception:
        message += "❌ Binance Connection: Failed\n"
        recommendations.append("Check API keys and internet")
    
    # Balance
    balance = get_account_balance()  # Your existing function
    message += f"✅ Balance: ${balance:,.2f} available\n"
    
    # Risk level
    heat = calculate_portfolio_heat()
    if heat < 10:
        message += f"✅ Risk Level: {heat:.1f}% (conservative)\n"
    elif heat < 15:
        message += f"⚠️ Risk Level: {heat:.1f}% (moderate)\n"
    else:
        message += f"🔴 Risk Level: {heat:.1f}% (high)\n"
        recommendations.append("Consider closing some positions")
    
    # Daily P&L
    today_stats = storage.get_daily_stats(
        datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    if today_stats:
        pnl = today_stats['realised_pnl']
        if pnl >= 50:  # Target
            message += f"✅ Daily P&L: +${pnl:.2f} (target reached! 🎯)\n"
        elif pnl >= 0:
            message += f"✅ Daily P&L: +${pnl:.2f}\n"
        elif pnl > -30:  # Loss limit
            message += f"⚠️ Daily P&L: -${abs(pnl):.2f}\n"
        else:
            message += f"🔴 Daily P&L: -${abs(pnl):.2f} (loss limit!)\n"
    else:
        message += "✅ Daily P&L: $0.00 (no trades yet)\n"
    
    # Recent errors
    recent_errors = get_recent_errors()  # Implement this
    if not recent_errors:
        message += "✅ No errors in last 24h\n"
    else:
        message += f"⚠️ {len(recent_errors)} error(s) in last 24h\n"
        recommendations.append("Check logs for details")
    
    # Recommendations
    if recommendations:
        message += "\n📋 Recommendations:\n"
        for rec in recommendations:
            message += f"• {rec}\n"
    else:
        message += "\n👍 Everything looks good! No action needed."
    
    await update.message.reply_text(message)
```

#### /export (New)

```python
async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export trade history as CSV file."""
    trades = storage.get_trades()
    
    if not trades:
        await update.message.reply_text("No trade history to export.")
        return
    
    # Create CSV content
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'ID', 'Pair', 'Strategy', 'Side', 'Entry Price', 'Exit Price',
        'Size', 'P&L ($)', 'P&L (%)', 'Fees', 'Net P&L',
        'Entry Time', 'Exit Time', 'Duration', 'Exit Reason', 'Win'
    ])
    
    # Data
    for trade in trades:
        duration_mins = trade.get('duration_seconds', 0) // 60
        writer.writerow([
            trade.get('id', ''),
            trade.get('pair', ''),
            trade.get('strategy', ''),
            trade.get('side', ''),
            trade.get('entry_price', 0),
            trade.get('exit_price', 0),
            trade.get('size', 0),
            trade.get('pnl_usdt', 0),
            trade.get('pnl_percent', 0),
            trade.get('fees_usdt', 0),
            trade.get('net_pnl_usdt', 0),
            trade.get('entry_time', ''),
            trade.get('exit_time', ''),
            f"{duration_mins}m",
            trade.get('exit_reason', ''),
            'Yes' if trade.get('is_win') else 'No'
        ])
    
    # Send file
    output.seek(0)
    filename = f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    await update.message.reply_document(
        document=io.BytesIO(output.getvalue().encode()),
        filename=filename,
        caption=f"📊 Exported {len(trades)} trades"
    )
```

#### /pause (Enhanced)

```python
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Pause new trade entries but keep monitoring existing positions.
    Different from /stop which completely stops the bot.
    """
    storage.update_state(is_paused=True)
    
    positions = get_open_positions()
    
    message = (
        "⏸️ BOT PAUSED\n\n"
        "• No new trades will be opened\n"
        "• Existing positions are still being monitored\n"
        "• Stop losses and take profits are still active\n"
    )
    
    if positions:
        message += f"\nCurrently monitoring {len(positions)} open position(s).\n"
    
    message += "\nUse /resume to start trading again."
    
    await update.message.reply_text(message)
```

---

## Part 3: Enhanced Notifications

### Trade Opened Notification

```python
async def notify_trade_opened(trade: Dict):
    """Send notification when a trade is opened."""
    
    message = (
        f"📈 TRADE OPENED\n\n"
        f"Pair: {trade['pair']} ({trade['side'].upper()})\n"
        f"Strategy: {trade['strategy'].title()}\n"
        f"Entry: ${trade['entry_price']:,.2f}\n"
        f"Size: {trade['size']} ({trade['size_quote']:,.2f} USDT)\n"
        f"Stop Loss: ${trade['stop_loss']:,.2f} "
        f"({((trade['stop_loss'] - trade['entry_price']) / trade['entry_price'] * 100):+.2f}%)\n"
        f"Take Profit: ${trade['take_profit']:,.2f} "
        f"({((trade['take_profit'] - trade['entry_price']) / trade['entry_price'] * 100):+.2f}%)\n"
        f"Risk: ${trade.get('risk_usdt', 0):,.2f}\n"
    )
    
    # Add portfolio heat
    heat_before = trade.get('heat_before', 0)
    heat_after = trade.get('heat_after', 0)
    message += f"\nPortfolio Heat: {heat_before:.1f}% → {heat_after:.1f}%"
    
    await send_telegram_message(message)
```

### Trade Closed Notification

```python
async def notify_trade_closed(trade: Dict):
    """Send notification when a trade is closed."""
    
    # Determine if win or loss
    is_win = trade.get('is_win', trade['net_pnl_usdt'] > 0)
    emoji = "✅" if is_win else "❌"
    status = "WIN" if is_win else "LOSS"
    
    # Format duration
    duration_secs = trade.get('duration_seconds', 0)
    if duration_secs < 3600:
        duration = f"{duration_secs // 60}m"
    else:
        hours = duration_secs // 3600
        mins = (duration_secs % 3600) // 60
        duration = f"{hours}h {mins}m"
    
    # Get today's running total
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_stats = storage.get_daily_stats(today)
    
    message = (
        f"{emoji} TRADE CLOSED - {status}\n\n"
        f"Pair: {trade['pair']} ({trade['side'].upper()})\n"
        f"Entry: ${trade['entry_price']:,.2f} → "
        f"Exit: ${trade['exit_price']:,.2f}\n"
        f"P&L: {'+' if trade['net_pnl_usdt'] >= 0 else ''}"
        f"${trade['net_pnl_usdt']:.2f} "
        f"({trade['pnl_percent']:+.2f}%)\n"
        f"Duration: {duration}\n"
        f"Reason: {trade['exit_reason'].replace('_', ' ').title()}\n"
    )
    
    # Add today's summary
    if today_stats:
        message += (
            f"\nToday: {'+' if today_stats['realised_pnl'] >= 0 else ''}"
            f"${today_stats['realised_pnl']:.2f} "
            f"({today_stats['wins']}W/{today_stats['losses']}L)"
        )
    
    await send_telegram_message(message)
```

### Daily Summary Notification

```python
async def send_daily_summary():
    """
    Send daily summary notification.
    Call this at end of trading day (e.g., 23:59 UTC).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = storage.get_daily_stats(today)
    
    if not stats or stats['total_trades'] == 0:
        message = (
            f"📊 DAILY SUMMARY - {today}\n\n"
            f"No trades today.\n"
            f"Rest up for tomorrow! 😴"
        )
    else:
        # Determine emoji based on performance
        if stats['realised_pnl'] >= 50:
            emoji = "🎯"
            mood = "Target reached!"
        elif stats['realised_pnl'] > 0:
            emoji = "📈"
            mood = "Profitable day"
        elif stats['realised_pnl'] > -30:
            emoji = "📉"
            mood = "Minor setback"
        else:
            emoji = "⚠️"
            mood = "Tough day"
        
        message = (
            f"📊 DAILY SUMMARY - {today}\n"
            f"{emoji} {mood}\n\n"
            f"P&L: {'+' if stats['realised_pnl'] >= 0 else ''}"
            f"${stats['realised_pnl']:.2f}\n"
            f"Trades: {stats['total_trades']} "
            f"({stats['wins']}W / {stats['losses']}L)\n"
            f"Win Rate: {stats['win_rate']}%\n"
        )
        
        if stats['best_trade_pair']:
            message += (
                f"\nBest: {stats['best_trade_pair']} "
                f"+${stats['best_trade_pnl']:.2f}\n"
            )
        if stats['worst_trade_pair'] and stats['worst_trade_pnl'] < 0:
            message += (
                f"Worst: {stats['worst_trade_pair']} "
                f"${stats['worst_trade_pnl']:.2f}\n"
            )
        
        # Add lifetime context
        lifetime = storage.get_lifetime_stats()
        message += (
            f"\nAll-Time: ${lifetime['total_pnl']:.2f} "
            f"({lifetime['total_trades']} trades)"
        )
    
    await send_telegram_message(message)
```

---

## Part 4: Command Registration

Update your telegram bot handler registration:

```python
def setup_telegram_handlers(application):
    """Register all command handlers."""
    
    # Monitoring commands
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("balance", cmd_balance))
    application.add_handler(CommandHandler("positions", cmd_positions))
    application.add_handler(CommandHandler("heat", cmd_heat))
    
    # Performance commands (NEW/ENHANCED)
    application.add_handler(CommandHandler("pnl", cmd_pnl))
    application.add_handler(CommandHandler("trades", cmd_trades))
    application.add_handler(CommandHandler("winners", cmd_winners))
    application.add_handler(CommandHandler("losers", cmd_losers))
    application.add_handler(CommandHandler("stats", cmd_stats))
    
    # Control commands
    application.add_handler(CommandHandler("pause", cmd_pause))
    application.add_handler(CommandHandler("resume", cmd_resume))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("emergency", cmd_emergency))
    
    # User-friendly commands (NEW)
    application.add_handler(CommandHandler("explain", cmd_explain))
    application.add_handler(CommandHandler("health", cmd_health))
    
    # Export (NEW)
    application.add_handler(CommandHandler("export", cmd_export))
    
    # Help
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("start", cmd_help))  # Same as help
```

---

## Part 5: Implementation Checklist

### Phase 1: Persistence (Do First)

- [ ] Create `/data` directory structure
- [ ] Implement `StorageManager` class in `utils/storage_manager.py`
- [ ] Add `save_trade()` call wherever trades are closed
- [ ] Add storage initialisation to bot startup
- [ ] Test: Close a trade, restart bot, verify data persists

### Phase 2: Enhanced Commands

- [ ] Update `/pnl` to use persisted data
- [ ] Add `/trades` command
- [ ] Add `/winners` command  
- [ ] Add `/losers` command
- [ ] Add `/stats` command
- [ ] Update `/help` menu

### Phase 3: User-Friendly Commands

- [ ] Add `/explain` command
- [ ] Add `/health` command
- [ ] Add `/export` command
- [ ] Add `/pause` command (if not already present)

### Phase 4: Enhanced Notifications

- [ ] Update trade opened notification format
- [ ] Update trade closed notification format
- [ ] Add daily summary notification
- [ ] Test all notifications

### Phase 5: Testing

- [ ] Run bot for 24 hours
- [ ] Verify all data persists across restarts
- [ ] Test all commands manually
- [ ] Verify notifications are formatted correctly
- [ ] Check CSV export works

---

## Appendix: Helper Functions

```python
def calculate_uptime(start_time_iso: str) -> str:
    """Calculate human-readable uptime from ISO timestamp."""
    start = datetime.fromisoformat(start_time_iso.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    delta = now - start
    
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def format_pnl(value: float) -> str:
    """Format P&L with sign and emoji."""
    if value >= 0:
        return f"+${value:.2f} ✅"
    else:
        return f"-${abs(value):.2f} 🔻"


def format_pnl_simple(value: float) -> str:
    """Format P&L with sign only."""
    if value >= 0:
        return f"+${value:.2f}"
    else:
        return f"-${abs(value):.2f}"
```

---

## Notes for Claude Code

1. **Always backup first** - Don't skip this step
2. **Test incrementally** - Implement persistence first, then commands one by one
3. **Don't break existing functionality** - The current commands should keep working
4. **Handle edge cases** - Empty data, first trade, missing files
5. **Log everything** - Add logging to help debug issues
6. **Use UTC timestamps** - Consistent timezone handling

Good luck! 🚀
