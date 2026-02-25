"""
Backtest entry timing: Compare current EMA 8/21/50 full stack vs faster EMAs,
crossover triggers, and lower thresholds. All combinations tested.

Exit: 3% SL, trailing TP after 1.3% with 1% trail (current strategy)
Volume: vol_min3 >= 1.5x (current filter)
RSI: 40-70 (current filter)
"""
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timedelta

client = Client()

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'BNBUSDT', 'SUIUSDT',
           'LINKUSDT', 'XRPUSDT', 'ARBUSDT', 'TRXUSDT', 'TONUSDT', 'ADAUSDT']

# Exit params (fixed across all tests)
SL_PCT = 3.0
TP_PCT = 1.3
TRAIL_PCT = 1.0


def fetch_data(symbol, days=60):
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    klines = client.get_historical_klines(symbol=symbol, interval='5m',
        start_str=start_time.strftime('%Y-%m-%d'), end_str=end_time.strftime('%Y-%m-%d'))
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df


def calculate_indicators(df, ema_fast=8, ema_mid=21, ema_slow=50):
    """Calculate indicators with configurable EMA periods."""
    df[f'ema_fast'] = ta.ema(df['close'], length=ema_fast)
    df[f'ema_mid'] = ta.ema(df['close'], length=ema_mid)
    df[f'ema_slow'] = ta.ema(df['close'], length=ema_slow)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['vol_min3'] = df['vol_ratio'].rolling(3).min()

    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']

    # VWAP
    df.set_index('timestamp', inplace=True)
    df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    df.reset_index(inplace=True)

    return df


def calculate_momentum_score(row, trend_mode='full_stack'):
    """
    Calculate momentum score matching the live bot's logic.
    trend_mode: 'full_stack' (EMA fast > mid > slow) or 'crossover' (EMA fast > mid only)
    """
    price = row['close']
    ema_fast = row['ema_fast']
    ema_mid = row['ema_mid']
    ema_slow = row['ema_slow']
    rsi = row['rsi']
    macd = row['macd']
    macd_signal = row['macd_signal']
    macd_hist = row['macd_hist']
    vol_ratio = row['vol_ratio']
    vwap = row.get('vwap', price)

    # Trend strength
    if trend_mode == 'full_stack':
        trend_bullish = price > ema_fast > ema_mid > ema_slow
    elif trend_mode == 'crossover':
        # Only require fast > mid, price above fast
        trend_bullish = price > ema_fast > ema_mid
    else:
        trend_bullish = False

    trend_strength = 0.0
    if trend_bullish:
        if trend_mode == 'full_stack':
            ema_separation = ((ema_fast - ema_slow) / ema_slow) * 100
        else:
            ema_separation = ((ema_fast - ema_mid) / ema_mid) * 100
        trend_strength = min(ema_separation / 5.0, 1.0)

    # RSI momentum
    rsi_momentum = 0.0
    if pd.notna(rsi):
        if 50 < rsi < 70:
            rsi_momentum = 1.0
        elif 40 < rsi < 50:
            rsi_momentum = 0.5
        elif 70 < rsi < 80:
            rsi_momentum = 0.7

    # MACD momentum
    macd_momentum = 0.0
    if pd.notna(macd) and pd.notna(macd_signal) and pd.notna(macd_hist):
        if macd > macd_signal and macd_hist > 0 and macd != 0:
            macd_strength = abs(macd_hist) / abs(macd)
            macd_momentum = min(macd_strength, 1.0)

    # Volume momentum
    volume_momentum = min(vol_ratio / 2.0, 1.0) if pd.notna(vol_ratio) else 0.0

    # VWAP strength
    vwap_strength = 1.0 if (pd.notna(vwap) and price > vwap) else 0.3

    # Overall score
    score = (
        trend_strength * 0.35 +
        rsi_momentum * 0.25 +
        macd_momentum * 0.20 +
        volume_momentum * 0.10 +
        vwap_strength * 0.10
    )

    return score


def simulate(df, threshold=0.70, trend_mode='full_stack'):
    """
    Simulate strategy with given entry parameters.
    Exit: 3% SL, trailing after 1.3% TP with 1% trail (fixed).
    """
    df = df.dropna(subset=['ema_fast', 'ema_mid', 'ema_slow', 'rsi', 'vol_min3']).copy()

    trades = []
    in_pos = False
    entry_price = highest = 0
    entry_time = None
    sl = SL_PCT / 100
    tp = TP_PCT / 100
    trail = TRAIL_PCT / 100

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']
        high = row['high']
        low = row['low']

        if in_pos:
            # Track highest with candle high
            if high > highest:
                highest = high

            # Check stop loss first (using candle low)
            sl_price = entry_price * (1 - sl)
            if low <= sl_price:
                pnl_pct = -sl * 100  # Assume stopped at exact SL level
                trades.append({
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'stop_loss',
                    'duration': (row['timestamp'] - entry_time).total_seconds() / 60,
                    'entry_price': entry_price,
                    'exit_price': sl_price
                })
                in_pos = False
                continue

            # Check trailing TP
            tp_level = entry_price * (1 + tp)
            if highest >= tp_level:
                trail_stop = highest * (1 - trail)
                if low <= trail_stop:
                    exit_price = trail_stop
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    trades.append({
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'trailing_tp',
                        'duration': (row['timestamp'] - entry_time).total_seconds() / 60,
                        'entry_price': entry_price,
                        'exit_price': exit_price
                    })
                    in_pos = False
                    continue

        else:
            # Check entry conditions
            rsi = row['rsi']
            vol_min3 = row['vol_min3']
            vol_ratio = row['vol_ratio']

            if pd.isna(rsi) or pd.isna(vol_min3) or pd.isna(vol_ratio):
                continue

            # RSI filter: 40-70
            if not (40 <= rsi <= 70):
                continue

            # Volume filter: current >= 1.5x AND sustained >= 1.5x
            if vol_ratio < 1.5 or vol_min3 < 1.5:
                continue

            # Calculate momentum score
            score = calculate_momentum_score(row, trend_mode=trend_mode)

            if score >= threshold:
                in_pos = True
                entry_price = price
                highest = high
                entry_time = row['timestamp']

    return trades


def run_config(name, ema_periods, trend_mode, threshold):
    """Run a single configuration across all symbols."""
    all_trades = []
    for symbol in SYMBOLS:
        try:
            df = fetch_data(symbol, days=60)
            df = calculate_indicators(df, *ema_periods)
            trades = simulate(df, threshold=threshold, trend_mode=trend_mode)
            for t in trades:
                t['symbol'] = symbol
            all_trades.extend(trades)
        except Exception as e:
            print(f"  Error {symbol}: {e}")
    return all_trades


def summarize(name, trades):
    """Print summary for a configuration."""
    if not trades:
        print(f"\n{name}: NO TRADES")
        return {'name': name, 'total_pnl': 0, 'trades': 0, 'win_rate': 0, 'avg_win': 0, 'avg_loss': 0}

    wins = [t for t in trades if t['pnl_pct'] > 0]
    losses = [t for t in trades if t['pnl_pct'] <= 0]
    total_pnl = sum(t['pnl_pct'] for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
    avg_duration = sum(t['duration'] for t in trades) / len(trades) if trades else 0

    # Trailing TP stats
    tp_exits = [t for t in trades if t['exit_reason'] == 'trailing_tp']
    avg_tp_pnl = sum(t['pnl_pct'] for t in tp_exits) / len(tp_exits) if tp_exits else 0

    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")
    print(f"  Trades: {len(trades)} ({len(wins)}W / {len(losses)}L)")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: {total_pnl:+.2f}%")
    print(f"  Avg Win: {avg_win:+.2f}%  |  Avg Loss: {avg_loss:+.2f}%")
    print(f"  Avg TP exit: {avg_tp_pnl:+.2f}%  ({len(tp_exits)} trailing TP exits)")
    print(f"  Avg Duration: {avg_duration:.0f} min")
    print(f"  Risk/Reward: {abs(avg_win/avg_loss):.2f}x" if avg_loss != 0 else "  Risk/Reward: N/A")

    # Per-symbol breakdown
    symbols_traded = set(t['symbol'] for t in trades)
    print(f"  Symbols active: {len(symbols_traded)}/{len(SYMBOLS)}")

    return {
        'name': name,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'avg_tp_pnl': avg_tp_pnl,
        'avg_duration': avg_duration,
        'risk_reward': abs(avg_win / avg_loss) if avg_loss != 0 else 0
    }


if __name__ == '__main__':
    print("=" * 70)
    print("  ENTRY TIMING OPTIMIZATION BACKTEST")
    print("  60-day backtest | 12 symbols | 5m candles")
    print("  Exit: 3% SL / Trailing after 1.3% with 1% trail (fixed)")
    print("  Filters: RSI 40-70, vol >= 1.5x, vol_min3 >= 1.5x")
    print("=" * 70)

    configs = [
        # (Name, EMA periods, trend_mode, threshold)
        ("CURRENT: EMA 8/21/50 | Full Stack | 0.70",    (8, 21, 50), 'full_stack', 0.70),
        ("A: Fast EMA 5/13/34 | Full Stack | 0.70",     (5, 13, 34), 'full_stack', 0.70),
        ("B: EMA 8/21/50 | Crossover Only | 0.70",      (8, 21, 50), 'crossover', 0.70),
        ("C: EMA 8/21/50 | Full Stack | 0.60",          (8, 21, 50), 'full_stack', 0.60),
        ("D: Fast EMA 5/13/34 | Crossover | 0.70",      (5, 13, 34), 'crossover', 0.70),
        ("E: Fast EMA 5/13/34 | Full Stack | 0.60",     (5, 13, 34), 'full_stack', 0.60),
        ("F: EMA 8/21/50 | Crossover | 0.60",           (8, 21, 50), 'crossover', 0.60),
        ("G: Fast EMA 5/13/34 | Crossover | 0.60",      (5, 13, 34), 'crossover', 0.60),
    ]

    results = []
    for name, ema, trend, thresh in configs:
        print(f"\nRunning: {name}...")
        trades = run_config(name, ema, trend, thresh)
        result = summarize(name, trades)
        results.append(result)

    # Final comparison table
    print("\n\n" + "=" * 90)
    print("  COMPARISON TABLE")
    print("=" * 90)
    print(f"  {'Config':<45} {'Trades':>6} {'Win%':>6} {'P&L%':>8} {'AvgWin':>7} {'AvgLoss':>8} {'R:R':>5}")
    print("-" * 90)

    for r in sorted(results, key=lambda x: x['total_pnl'], reverse=True):
        print(f"  {r['name']:<45} {r['trades']:>6} {r['win_rate']:>5.1f}% {r['total_pnl']:>+7.2f}% {r['avg_win']:>+6.2f}% {r['avg_loss']:>+7.2f}% {r['risk_reward']:>5.2f}")

    print("-" * 90)

    best = max(results, key=lambda x: x['total_pnl'])
    print(f"\n  BEST: {best['name']}")
    print(f"  P&L: {best['total_pnl']:+.2f}% | Win Rate: {best['win_rate']:.1f}% | R:R: {best['risk_reward']:.2f}x")
