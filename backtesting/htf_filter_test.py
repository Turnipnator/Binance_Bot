"""
Backtest higher timeframe (HTF) filters to prevent entries during bearish markets.
Tests 1H and 4H filters to see which would have saved the most losses.

Uses the actual 37 trade entry timestamps and checks what the HTF conditions were.
"""
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timedelta

client = Client()

# All 37 actual trades from the bot
TRADES = [
    {"pair": "SOLUSDT", "entry": "2026-01-09T00:46", "pnl": 2.02, "result": "W"},
    {"pair": "ZECUSDT", "entry": "2026-01-09T04:00", "pnl": 2.24, "result": "W"},
    {"pair": "TRXUSDT", "entry": "2026-01-09T23:55", "pnl": 1.68, "result": "W"},
    {"pair": "ARBUSDT", "entry": "2026-01-13T16:27", "pnl": 1.68, "result": "W"},
    {"pair": "ADAUSDT", "entry": "2026-01-13T20:02", "pnl": 1.76, "result": "W"},
    {"pair": "SUIUSDT", "entry": "2026-01-08T21:38", "pnl": 2.19, "result": "W"},
    {"pair": "SHIBUSDT", "entry": "2026-01-13T22:07", "pnl": 2.49, "result": "W"},
    {"pair": "AVAXUSDT", "entry": "2026-01-13T20:00", "pnl": 1.95, "result": "W"},
    {"pair": "SOLUSDT", "entry": "2026-01-14T01:33", "pnl": 1.45, "result": "W"},
    {"pair": "LINKUSDT", "entry": "2026-01-14T01:07", "pnl": 1.85, "result": "W"},
    {"pair": "SUIUSDT", "entry": "2026-01-13T22:29", "pnl": 1.95, "result": "W"},
    {"pair": "ADAUSDT", "entry": "2026-01-14T01:09", "pnl": -6.26, "result": "L"},
    {"pair": "ARBUSDT", "entry": "2026-01-14T01:07", "pnl": -6.30, "result": "L"},
    {"pair": "SOLUSDT", "entry": "2026-02-06T13:14", "pnl": 2.20, "result": "W"},
    {"pair": "SUIUSDT", "entry": "2026-02-06T13:24", "pnl": 2.12, "result": "W"},
    {"pair": "ETHUSDT", "entry": "2026-02-06T22:38", "pnl": 2.15, "result": "W"},
    {"pair": "BNBUSDT", "entry": "2026-02-06T17:38", "pnl": -8.23, "result": "L"},
    {"pair": "SUIUSDT", "entry": "2026-02-12T11:03", "pnl": -4.95, "result": "L"},
    {"pair": "AVAXUSDT", "entry": "2026-02-13T21:09", "pnl": 0.35, "result": "W"},
    {"pair": "XRPUSDT", "entry": "2026-02-15T08:33", "pnl": -4.30, "result": "L"},
    {"pair": "SUIUSDT", "entry": "2026-02-20T05:40", "pnl": 1.25, "result": "W"},
    {"pair": "AVAXUSDT", "entry": "2026-02-25T07:13", "pnl": 15.07, "result": "W"},
    {"pair": "XRPUSDT", "entry": "2026-02-25T21:03", "pnl": 0.66, "result": "W"},
    {"pair": "SHIBUSDT", "entry": "2026-02-25T20:37", "pnl": -6.00, "result": "L"},
    {"pair": "ARBUSDT", "entry": "2026-03-02T15:19", "pnl": -5.15, "result": "L"},
    {"pair": "XRPUSDT", "entry": "2026-03-02T22:11", "pnl": -4.85, "result": "L"},
    {"pair": "ETHUSDT", "entry": "2026-03-04T14:17", "pnl": 0.76, "result": "W"},
    {"pair": "ETHUSDT", "entry": "2026-03-04T14:36", "pnl": 4.44, "result": "W"},
    {"pair": "SUIUSDT", "entry": "2026-03-04T19:12", "pnl": -4.17, "result": "L"},
    {"pair": "SOLUSDT", "entry": "2026-03-04T19:13", "pnl": -3.86, "result": "L"},
    {"pair": "SHIBUSDT", "entry": "2026-03-04T17:18", "pnl": -5.26, "result": "L"},
    {"pair": "AVAXUSDT", "entry": "2026-03-04T19:13", "pnl": -3.94, "result": "L"},
    {"pair": "BTCUSDT", "entry": "2026-03-04T19:17", "pnl": -3.66, "result": "L"},
    {"pair": "BTCUSDT", "entry": "2026-03-09T19:33", "pnl": 1.13, "result": "W"},
    {"pair": "AVAXUSDT", "entry": "2026-03-09T19:33", "pnl": 1.17, "result": "W"},
    {"pair": "SHIBUSDT", "entry": "2026-03-10T15:34", "pnl": -5.84, "result": "L"},
    {"pair": "SUIUSDT", "entry": "2026-03-10T15:10", "pnl": -5.10, "result": "L"},
]


def fetch_htf_data(symbol, timeframe, entry_time_str):
    """Fetch higher timeframe data around the entry time."""
    entry_time = datetime.fromisoformat(entry_time_str)
    # Fetch enough history before the entry
    start = entry_time - timedelta(days=30)
    end = entry_time + timedelta(hours=1)

    klines = client.get_historical_klines(
        symbol=symbol, interval=timeframe,
        start_str=start.strftime('%Y-%m-%d'),
        end_str=end.strftime('%Y-%m-%d %H:%M')
    )

    if not klines:
        return None

    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df


def check_htf_condition(df, entry_time_str, condition_type):
    """Check a higher timeframe condition at entry time."""
    if df is None or len(df) < 50:
        return None  # Insufficient data

    entry_time = datetime.fromisoformat(entry_time_str)

    # Calculate indicators
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['ema8'] = ta.ema(df['close'], length=8)
    df['rsi'] = ta.rsi(df['close'], length=14)

    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']

    # Find the candle at or just before entry time
    mask = df['timestamp'] <= entry_time
    if not mask.any():
        return None
    latest = df[mask].iloc[-1]

    price = latest['close']
    ema8 = latest['ema8']
    ema21 = latest['ema21']
    ema50 = latest['ema50']
    rsi = latest['rsi']
    macd_val = latest['macd']
    macd_sig = latest['macd_signal']

    if pd.isna(ema21) or pd.isna(ema50):
        return None

    if condition_type == 'price_above_ema50':
        return price > ema50
    elif condition_type == 'price_above_ema21':
        return price > ema21
    elif condition_type == 'ema8_above_ema21':
        return pd.notna(ema8) and ema8 > ema21
    elif condition_type == 'ema_stack':
        return pd.notna(ema8) and price > ema8 > ema21 > ema50
    elif condition_type == 'price_above_ema21_and_macd':
        return (price > ema21) and pd.notna(macd_val) and pd.notna(macd_sig) and (macd_val > macd_sig)
    elif condition_type == 'not_oversold_and_above_ema21':
        return (price > ema21) and pd.notna(rsi) and (rsi > 40)

    return None


def test_filter(timeframe, condition_type, label):
    """Test a specific HTF filter against all trades."""
    allowed = []
    blocked = []
    skipped = 0

    for trade in TRADES:
        symbol = trade['pair']
        entry = trade['entry']

        try:
            df = fetch_htf_data(symbol, timeframe, entry)
        except Exception as e:
            print(f"  Error fetching {symbol} {timeframe}: {e}")
            df = None

        result = check_htf_condition(df, entry, condition_type)

        if result is None:
            skipped += 1
            allowed.append(trade)  # Fail open
        elif result:
            allowed.append(trade)
        else:
            blocked.append(trade)

    # Calculate stats
    wins_allowed = [t for t in allowed if t['result'] == 'W']
    losses_allowed = [t for t in allowed if t['result'] == 'L']
    wins_blocked = [t for t in blocked if t['result'] == 'W']
    losses_blocked = [t for t in blocked if t['result'] == 'L']

    pnl_allowed = sum(t['pnl'] for t in allowed)
    pnl_blocked = sum(t['pnl'] for t in blocked)
    saved = sum(abs(t['pnl']) for t in losses_blocked)

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  Trades allowed: {len(allowed)} ({len(wins_allowed)}W / {len(losses_allowed)}L)")
    print(f"  Trades blocked: {len(blocked)} ({len(wins_blocked)}W / {len(losses_blocked)}L)")
    if skipped:
        print(f"  Skipped (no data): {skipped}")
    print(f"  P&L of allowed: ${pnl_allowed:+.2f}")
    print(f"  P&L of blocked: ${pnl_blocked:+.2f}")
    print(f"  Losses saved: ${saved:.2f}")
    if allowed:
        wr = len(wins_allowed) / len(allowed) * 100
        print(f"  Win rate (filtered): {wr:.1f}%")
    print(f"  Wins accidentally blocked: {len(wins_blocked)} (${sum(t['pnl'] for t in wins_blocked):.2f})")
    if wins_blocked:
        for t in wins_blocked:
            print(f"    - {t['pair']} {t['entry'][:16]}: +${t['pnl']:.2f}")

    return {
        'label': label,
        'allowed': len(allowed),
        'blocked': len(blocked),
        'pnl': pnl_allowed,
        'saved': saved,
        'win_rate': len(wins_allowed) / len(allowed) * 100 if allowed else 0,
        'wins_blocked': len(wins_blocked),
        'losses_blocked': len(losses_blocked),
    }


if __name__ == '__main__':
    print("=" * 70)
    print("  HIGHER TIMEFRAME FILTER BACKTEST")
    print("  Testing against all 37 actual bot trades")
    print("  Which filter would have blocked the most losses")
    print("  while keeping the most wins?")
    print("=" * 70)

    no_filter_pnl = sum(t['pnl'] for t in TRADES)
    no_filter_wins = len([t for t in TRADES if t['result'] == 'W'])
    no_filter_losses = len([t for t in TRADES if t['result'] == 'L'])
    print(f"\n  BASELINE (no filter): {len(TRADES)} trades ({no_filter_wins}W/{no_filter_losses}L)")
    print(f"  Baseline P&L: ${no_filter_pnl:+.2f}")
    print(f"  Baseline Win Rate: {no_filter_wins/len(TRADES)*100:.1f}%")

    configs = [
        ('1h', 'price_above_ema50',          '1H: Price > EMA50'),
        ('1h', 'price_above_ema21',          '1H: Price > EMA21'),
        ('1h', 'ema8_above_ema21',           '1H: EMA8 > EMA21'),
        ('1h', 'price_above_ema21_and_macd', '1H: Price > EMA21 + MACD bullish'),
        ('4h', 'price_above_ema50',          '4H: Price > EMA50'),
        ('4h', 'price_above_ema21',          '4H: Price > EMA21'),
        ('4h', 'ema8_above_ema21',           '4H: EMA8 > EMA21'),
    ]

    results = []
    for tf, cond, label in configs:
        print(f"\nTesting: {label}...")
        r = test_filter(tf, cond, label)
        results.append(r)

    # Comparison
    print("\n\n" + "=" * 90)
    print("  COMPARISON TABLE")
    print("=" * 90)
    print(f"  {'Filter':<40} {'Allowed':>7} {'Blocked':>8} {'P&L':>8} {'Saved':>7} {'WR%':>6} {'WinsLost':>9}")
    print("-" * 90)
    print(f"  {'NO FILTER (baseline)':<40} {len(TRADES):>7} {0:>8} ${no_filter_pnl:>+6.2f} {'$0':>7} {no_filter_wins/len(TRADES)*100:>5.1f}% {0:>9}")
    for r in sorted(results, key=lambda x: x['pnl'], reverse=True):
        print(f"  {r['label']:<40} {r['allowed']:>7} {r['blocked']:>8} ${r['pnl']:>+6.2f} ${r['saved']:>5.2f} {r['win_rate']:>5.1f}% {r['wins_blocked']:>9}")
    print("-" * 90)

    best = max(results, key=lambda x: x['pnl'])
    print(f"\n  BEST: {best['label']}")
    print(f"  P&L: ${best['pnl']:+.2f} (vs ${no_filter_pnl:+.2f} baseline)")
    print(f"  Improvement: ${best['pnl'] - no_filter_pnl:+.2f}")
    print(f"  Win Rate: {best['win_rate']:.1f}% (vs {no_filter_wins/len(TRADES)*100:.1f}% baseline)")
