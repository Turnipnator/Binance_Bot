"""
Backtest different TP/SL combinations to find optimal risk/reward ratio.
Tests against the current momentum strategy with sustained volume filter.
"""
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timedelta

client = Client()


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


def calculate_indicators(df):
    df['ema8'] = ta.ema(df['close'], length=8)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['vol_min3'] = df['vol_ratio'].rolling(3).min()

    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']

    df['bullish'] = (df['close'] > df['ema8']) & (df['ema8'] > df['ema21']) & (df['ema21'] > df['ema50'])
    return df


def simulate(df, tp_pct, sl_pct, trailing_tp=False, partial_exit=False):
    """
    Simulate strategy with given TP/SL percentages.

    trailing_tp: After hitting initial TP, trail with a tighter stop
    partial_exit: Exit 50% at TP, trail remaining 50%
    """
    df = df.dropna().copy()
    wins, losses = 0, 0
    total_pnl = 0
    in_pos = False
    entry_price = highest = 0
    partial_closed = False
    partial_pnl = 0

    tp = tp_pct / 100
    sl = sl_pct / 100

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']

        if in_pos:
            if price > highest:
                highest = price

            if trailing_tp and not partial_exit:
                # Mode: trailing TP
                # Once price hits TP level, start trailing with 1% stop from high
                if highest >= entry_price * (1 + tp):
                    # Now trailing - use tighter stop (1% from highest)
                    trail_stop = highest * (1 - 0.01)
                    if price <= trail_stop:
                        pnl = ((price - entry_price) / entry_price) * 100
                        total_pnl += pnl
                        if pnl > 0:
                            wins += 1
                        else:
                            losses += 1
                        in_pos = False
                        continue
                # Normal stop loss still applies
                if price <= entry_price * (1 - sl):
                    pnl = ((price - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    losses += 1
                    in_pos = False

            elif partial_exit:
                # Mode: partial exit
                # Close 50% at TP, trail other 50% with 1.5% stop from high
                if not partial_closed and price >= entry_price * (1 + tp):
                    # Close first half
                    partial_pnl = tp * 100 * 0.5  # 50% of position at TP
                    partial_closed = True
                    continue

                if partial_closed:
                    # Trail second half with 1.5% from high
                    trail_stop = highest * (1 - 0.015)
                    if price <= trail_stop:
                        pnl2 = ((price - entry_price) / entry_price) * 100 * 0.5
                        total_pnl += partial_pnl + pnl2
                        wins += 1
                        in_pos = False
                        partial_closed = False
                        continue

                # Normal stop loss for full position (before partial close)
                if not partial_closed and price <= entry_price * (1 - sl):
                    pnl = ((price - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    losses += 1
                    in_pos = False
                    partial_closed = False

                # Stop loss for remaining 50% after partial close
                if partial_closed and price <= entry_price * (1 - sl):
                    pnl2 = ((price - entry_price) / entry_price) * 100 * 0.5
                    total_pnl += partial_pnl + pnl2
                    losses += 1
                    in_pos = False
                    partial_closed = False

            else:
                # Standard mode: fixed TP and trailing SL
                if price >= entry_price * (1 + tp):
                    pnl = ((price - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    wins += 1
                    in_pos = False
                elif price <= highest * (1 - sl):
                    pnl = ((price - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    losses += 1
                    in_pos = False
        else:
            if not row['bullish']:
                continue
            if row['rsi'] > 70 or row['rsi'] < 40:
                continue
            if row['macd'] <= row['macd_signal']:
                continue
            if row['vol_ratio'] < 1.5:
                continue
            if row['vol_min3'] < 1.5:
                continue

            in_pos = True
            entry_price = price
            highest = price
            partial_closed = False
            partial_pnl = 0

    trades = wins + losses
    wr = wins / trades * 100 if trades else 0
    avg_win = total_pnl / wins if wins else 0
    avg_loss = 0
    if losses:
        # Calculate average loss separately
        avg_loss = (total_pnl - (avg_win * wins)) / losses if losses else 0

    return {
        'trades': trades,
        'wins': wins,
        'losses': losses,
        'win_rate': wr,
        'total_pnl': total_pnl,
    }


if __name__ == "__main__":
    configs = [
        {'name': 'Current: 5% SL / 1.3% TP', 'sl': 5.0, 'tp': 1.3, 'trailing': False, 'partial': False},
        {'name': 'Option A: 3% SL / 1.3% TP', 'sl': 3.0, 'tp': 1.3, 'trailing': False, 'partial': False},
        {'name': 'Option B: 5% SL / 2.5% TP', 'sl': 5.0, 'tp': 2.5, 'trailing': False, 'partial': False},
        {'name': 'Option C: 3% SL / 2% TP', 'sl': 3.0, 'tp': 2.0, 'trailing': False, 'partial': False},
        {'name': 'Option D: 3% SL / trailing after 1.3%', 'sl': 3.0, 'tp': 1.3, 'trailing': True, 'partial': False},
        {'name': 'Option E: 3% SL / partial exit at 1.3%', 'sl': 3.0, 'tp': 1.3, 'trailing': False, 'partial': True},
        {'name': 'Option F: 2% SL / 1.3% TP', 'sl': 2.0, 'tp': 1.3, 'trailing': False, 'partial': False},
        {'name': 'Option G: 2% SL / 2% TP', 'sl': 2.0, 'tp': 2.0, 'trailing': False, 'partial': False},
    ]

    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'ARBUSDT', 'AVAXUSDT', 'BNBUSDT']

    results = {c['name']: {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0} for c in configs}

    for sym in symbols:
        print(f"Fetching {sym}...")
        df = fetch_data(sym)
        df = calculate_indicators(df)

        for cfg in configs:
            r = simulate(df, cfg['tp'], cfg['sl'], cfg['trailing'], cfg['partial'])
            results[cfg['name']]['trades'] += r['trades']
            results[cfg['name']]['wins'] += r['wins']
            results[cfg['name']]['losses'] += r['losses']
            results[cfg['name']]['pnl'] += r['total_pnl']

    print()
    print('=' * 90)
    print('TP/SL OPTIMIZATION RESULTS (60 days, 7 symbols)')
    print('=' * 90)
    print()
    print(f"{'Config':<40} {'Trades':>7} {'Wins':>6} {'Losses':>7} {'WinRate':>8} {'P&L':>10} {'P&L/Trade':>10}")
    print('-' * 90)

    for cfg in configs:
        r = results[cfg['name']]
        wr = r['wins'] / r['trades'] * 100 if r['trades'] else 0
        ppt = r['pnl'] / r['trades'] if r['trades'] else 0
        marker = ''
        print(f"{cfg['name']:<40} {r['trades']:>7} {r['wins']:>6} {r['losses']:>7} {wr:>7.1f}% {r['pnl']:>+9.2f}% {ppt:>+9.3f}%")

    # Find best
    best = max(results.items(), key=lambda x: x[1]['pnl'])
    current_pnl = results['Current: 5% SL / 1.3% TP']['pnl']

    print()
    print(f">>> BEST CONFIG: {best[0]}")
    print(f"    P&L: {best[1]['pnl']:+.2f}% (vs current {current_pnl:+.2f}%)")
    print(f"    Improvement: {best[1]['pnl'] - current_pnl:+.2f}%")

    # Risk/reward analysis
    print()
    print('=' * 90)
    print('RISK/REWARD ANALYSIS')
    print('=' * 90)
    print()
    for cfg in configs:
        r = results[cfg['name']]
        if r['wins'] > 0 and r['losses'] > 0:
            # Estimate avg win and avg loss from pnl split
            wr = r['wins'] / r['trades'] * 100
            # Calculate breakeven win rate needed
            loss_size = cfg['sl']
            win_size = cfg['tp']
            breakeven_wr = loss_size / (loss_size + win_size) * 100
            margin = wr - breakeven_wr
            rr_ratio = win_size / loss_size
            print(f"{cfg['name']:<40} R:R={rr_ratio:.2f}  Breakeven WR={breakeven_wr:.0f}%  Actual WR={wr:.0f}%  Safety margin={margin:+.0f}%")
