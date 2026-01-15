"""
Backtest comparing current volume filter vs sustained volume filter
"""
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime, timedelta

client = Client()

def fetch_data(symbol, interval='5m', days=60):
    """Fetch historical data"""
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    klines = client.get_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=start_time.strftime('%Y-%m-%d'),
        end_str=end_time.strftime('%Y-%m-%d')
    )

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df

def calculate_indicators(df):
    """Calculate all indicators"""
    df['ema8'] = ta.ema(df['close'], length=8)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['vol_avg3'] = df['vol_ratio'].rolling(3).mean()
    df['vol_min3'] = df['vol_ratio'].rolling(3).min()

    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']

    # Trend
    df['bullish'] = (df['close'] > df['ema8']) & (df['ema8'] > df['ema21']) & (df['ema21'] > df['ema50'])

    return df

def simulate_strategy(df, symbol, volume_filter='current'):
    """
    Simulate trades with different volume filters
    volume_filter: 'current' (>= 1.5x) or 'sustained' (min3 >= 1.0x AND current >= 1.5x)
    """
    df = df.copy()
    df = df.dropna()

    trades = []
    in_position = False
    entry_price = 0
    entry_time = None
    highest_price = 0

    TP_PCT = 1.3 / 100  # 1.3%
    SL_PCT = 5.0 / 100  # 5%

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']

        if in_position:
            # Update trailing stop
            if price > highest_price:
                highest_price = price

            # Check TP
            if price >= entry_price * (1 + TP_PCT):
                pnl_pct = ((price - entry_price) / entry_price) * 100
                trades.append({
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'take_profit',
                    'is_win': True
                })
                in_position = False
                continue

            # Check SL (trailing from highest)
            if price <= highest_price * (1 - SL_PCT):
                pnl_pct = ((price - entry_price) / entry_price) * 100
                trades.append({
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price,
                    'exit_price': price,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'stop_loss',
                    'is_win': False
                })
                in_position = False
                continue

        else:
            # Check entry conditions
            if not row['bullish']:
                continue
            if row['rsi'] > 70 or row['rsi'] < 40:
                continue
            if row['macd'] <= row['macd_signal']:
                continue

            # Volume filter
            if volume_filter == 'current':
                # Current logic: just check current candle
                if row['vol_ratio'] < 1.5:
                    continue
            elif volume_filter == 'sustained':
                # Proposed logic: current >= 1.5x AND min of last 3 >= 1.0x
                if row['vol_ratio'] < 1.5 or row['vol_min3'] < 1.0:
                    continue

            # Enter trade
            in_position = True
            entry_price = price
            entry_time = row['timestamp']
            highest_price = price

    return trades

def run_backtest(symbol, days=60):
    """Run backtest comparing both volume filters"""
    print(f"\n{'='*60}")
    print(f"BACKTESTING {symbol} - {days} days")
    print(f"{'='*60}")

    # Fetch data
    df = fetch_data(symbol, '5m', days)
    print(f"Fetched {len(df)} candles")

    # Calculate indicators
    df = calculate_indicators(df)

    # Run with current filter
    trades_current = simulate_strategy(df, symbol, 'current')

    # Run with sustained filter
    trades_sustained = simulate_strategy(df, symbol, 'sustained')

    # Calculate stats
    def calc_stats(trades):
        if not trades:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0, 'avg_win': 0, 'avg_loss': 0}

        wins = [t for t in trades if t['is_win']]
        losses = [t for t in trades if not t['is_win']]

        return {
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'total_pnl': sum(t['pnl_pct'] for t in trades),
            'avg_win': sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
        }

    stats_current = calc_stats(trades_current)
    stats_sustained = calc_stats(trades_sustained)

    print(f"\n{'CURRENT FILTER (vol >= 1.5x)':<35} {'SUSTAINED FILTER (+ min3 >= 1.0x)':<35}")
    print("-" * 70)
    print(f"{'Total Trades:':<20} {stats_current['trades']:<15} {stats_sustained['trades']:<15}")
    print(f"{'Winners:':<20} {stats_current['wins']:<15} {stats_sustained['wins']:<15}")
    print(f"{'Losers:':<20} {stats_current['losses']:<15} {stats_sustained['losses']:<15}")
    print(f"{'Win Rate:':<20} {stats_current['win_rate']:.1f}%{'':<10} {stats_sustained['win_rate']:.1f}%")
    print(f"{'Total P&L:':<20} {stats_current['total_pnl']:+.2f}%{'':<9} {stats_sustained['total_pnl']:+.2f}%")
    print(f"{'Avg Win:':<20} {stats_current['avg_win']:+.2f}%{'':<9} {stats_sustained['avg_win']:+.2f}%")
    print(f"{'Avg Loss:':<20} {stats_current['avg_loss']:+.2f}%{'':<9} {stats_sustained['avg_loss']:+.2f}%")

    return stats_current, stats_sustained


if __name__ == "__main__":
    # Run on multiple symbols
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'ARBUSDT', 'AVAXUSDT', 'BNBUSDT']
    all_current = {'trades': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0}
    all_sustained = {'trades': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0}

    for symbol in symbols:
        try:
            current, sustained = run_backtest(symbol, days=60)
            all_current['trades'] += current['trades']
            all_current['wins'] += current['wins']
            all_current['losses'] += current['losses']
            all_current['total_pnl'] += current['total_pnl']
            all_sustained['trades'] += sustained['trades']
            all_sustained['wins'] += sustained['wins']
            all_sustained['losses'] += sustained['losses']
            all_sustained['total_pnl'] += sustained['total_pnl']
        except Exception as e:
            print(f"Error with {symbol}: {e}")

    print(f"\n{'='*60}")
    print("COMBINED RESULTS (ALL SYMBOLS)")
    print(f"{'='*60}")
    print(f"\n{'CURRENT FILTER':<35} {'SUSTAINED FILTER':<35}")
    print("-" * 70)
    print(f"{'Total Trades:':<20} {all_current['trades']:<15} {all_sustained['trades']:<15}")
    print(f"{'Winners:':<20} {all_current['wins']:<15} {all_sustained['wins']:<15}")
    print(f"{'Losers:':<20} {all_current['losses']:<15} {all_sustained['losses']:<15}")

    wr_current = all_current['wins'] / all_current['trades'] * 100 if all_current['trades'] else 0
    wr_sustained = all_sustained['wins'] / all_sustained['trades'] * 100 if all_sustained['trades'] else 0
    print(f"{'Win Rate:':<20} {wr_current:.1f}%{'':<10} {wr_sustained:.1f}%")
    print(f"{'Total P&L:':<20} {all_current['total_pnl']:+.2f}%{'':<9} {all_sustained['total_pnl']:+.2f}%")

    diff_trades = all_sustained['trades'] - all_current['trades']
    diff_pnl = all_sustained['total_pnl'] - all_current['total_pnl']
    print(f"\n{'DIFFERENCE:':<20} {diff_trades:+d} trades{'':<5} {diff_pnl:+.2f}% P&L")

    if diff_pnl > 0:
        print(f"\n>>> SUSTAINED FILTER IS BETTER by {diff_pnl:+.2f}%")
    else:
        print(f"\n>>> CURRENT FILTER IS BETTER by {-diff_pnl:+.2f}%")
