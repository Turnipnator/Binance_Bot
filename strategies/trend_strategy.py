"""
Daily Trend Strategy
Hold BTC / ETH while the last CLOSED daily candle is above its SMA50, else cash.

Backtested 2026-10-09 (Binance daily 2017->2026, 0.15%/side switch cost): on BTC
every lookback 50-200 beat buy-and-hold on Sharpe in both 2018-21 and 2022-26,
robust to a 1-day execution lag. BTC+ETH 50/50 with SMA50: 2022-26 CAGR +25% /
max DD -41% (hold-both +4% / -68%). Fails on most alts, so BTC/ETH only. Long
only: long/short was worse in 5 of 6 long-run comparisons. It is NOT steady
income - it still lost ~50% in 2022. See memory daily-trend-rule-tested.

Unlike momentum/MR this holds one large position per pair for weeks:
- entry: whenever flat and the trend is ON (state, not crossover - matches the
  backtest, which is long every day the close is above the SMA)
- exit:  the first daily close below the SMA (checked once that candle closes)
- 15% emergency stop from entry (backtest-neutral crash insurance). After a stop
  the pair stays blocked until a daily close below the SMA re-arms it, so the
  bot does not buy straight back into the same falling trend.
"""
import json
import os
import time
from typing import Optional, Tuple

from loguru import logger

TREND_PAIRS = {'BTCUSDT', 'ETHUSDT'}
TREND_SMA_LEN = 50
TREND_STOP_PCT = 15.0
TREND_SIGNAL_REFRESH_S = 600   # refetch daily klines at most every 10 min
TREND_STATE_FILE = './data/trend_state.json'  # persisted post-stop re-arm blocks


class TrendStrategy:
    """Daily close vs SMA50 trend filter for a single pair."""

    def __init__(self, symbol: str, client=None):
        self.symbol = symbol
        self.client = client
        self.in_position = False
        self._cache: Optional[Tuple[float, Optional[bool], Optional[float], Optional[float]]] = None
        logger.info(f"Trend strategy initialized for {symbol} (daily close > SMA{TREND_SMA_LEN})")

    # ── signal ───────────────────────────────────────────────
    def daily_signal(self) -> Tuple[Optional[bool], Optional[float], Optional[float]]:
        """(trend_on, last_closed_close, sma) from CLOSED daily candles only.
        Returns (None, None, None) on data errors - callers must neither enter
        nor exit on an unknown signal (the 15% stop still protects)."""
        now = time.time()
        if self._cache and now - self._cache[0] < TREND_SIGNAL_REFRESH_S:
            return self._cache[1:]
        result = (None, None, None)
        try:
            kl = self.client.get_historical_klines(self.symbol, '1d', limit=TREND_SMA_LEN + 5)
            # drop the in-progress candle (close time still in the future)
            closed = [k for k in (kl or []) if int(k[6]) < now * 1000]
            if len(closed) >= TREND_SMA_LEN:
                closes = [float(k[4]) for k in closed[-TREND_SMA_LEN:]]
                sma = sum(closes) / TREND_SMA_LEN
                result = (closes[-1] > sma, closes[-1], sma)
            else:
                logger.warning(f"Trend: only {len(closed)} closed daily candles for {self.symbol}")
        except Exception as e:
            logger.error(f"Trend: daily signal error for {self.symbol}: {e}")
        if result[0] is not None:
            self._cache = (now, *result)
        return result

    # ── post-stop re-arm block (persisted so a restart can't re-buy) ──
    def _load_state(self) -> dict:
        try:
            if os.path.exists(TREND_STATE_FILE):
                with open(TREND_STATE_FILE) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Trend: could not read {TREND_STATE_FILE}: {e}")
        return {}

    def _save_state(self, state: dict):
        try:
            tmp = TREND_STATE_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(state, f)
            os.replace(tmp, TREND_STATE_FILE)
        except Exception as e:
            logger.error(f"Trend: could not persist {TREND_STATE_FILE}: {e}")

    def is_blocked(self) -> bool:
        return bool(self._load_state().get(self.symbol, {}).get('blocked'))

    def mark_stopped(self):
        state = self._load_state()
        state[self.symbol] = {'blocked': True, 'since': time.strftime('%Y-%m-%dT%H:%M:%S')}
        self._save_state(state)
        logger.warning(f"Trend: {self.symbol} blocked after emergency stop until a daily close below SMA{TREND_SMA_LEN}")

    def _unblock(self):
        state = self._load_state()
        state.pop(self.symbol, None)
        self._save_state(state)
        logger.info(f"Trend: {self.symbol} re-armed (daily close below SMA{TREND_SMA_LEN})")

    # ── decisions ────────────────────────────────────────────
    def should_enter(self) -> Tuple[bool, str]:
        on, close, sma = self.daily_signal()
        if on is None:
            return False, "trend signal unavailable"
        if self.is_blocked():
            if not on:
                self._unblock()
            return False, "blocked after emergency stop"
        if not on:
            return False, f"daily close {close:.2f} <= SMA{TREND_SMA_LEN} {sma:.2f}"
        return True, f"daily close {close:.2f} > SMA{TREND_SMA_LEN} {sma:.2f}"

    def should_exit(self) -> Tuple[bool, str]:
        on, close, sma = self.daily_signal()
        if on is False:
            return True, "Trend exit"
        return False, ""

    def stop_price(self, entry_price: float) -> float:
        return entry_price * (1 - TREND_STOP_PCT / 100)

    def enter_position(self, entry_price: float):
        self.in_position = True

    def exit_position(self, exit_price: float):
        self.in_position = False
