"""
Test different filter combinations to find optimal settings
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
    df['vol_avg3'] = df['vol_ratio'].rolling(3).mean()

    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']

    df['bullish'] = (df['close'] > df['ema8']) & (df['ema8'] > df['ema21']) & (df['ema21'] > df['ema50'])

    # MACD histogram momentum (is it increasing?)
    df['macd_hist_rising'] = df['macd_hist'] > df['macd_hist'].shift(1)

    return df

def simulate(df, rsi_max=70, vol_min3_thresh=1.0, require_macd_rising=False):
    df = df.dropna().copy()
    wins, losses = 0, 0
    total_pnl = 0
    in_pos = False
    entry_price = highest = 0

    TP_PCT = 1.3/100
    SL_PCT = 5.0/100

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']

        if in_pos:
            if price > highest: highest = price
            if price >= entry_price * (1 + TP_PCT):
                pnl = ((price - entry_price) / entry_price) * 100
                total_pnl += pnl
                wins += 1
                in_pos = False
            elif price <= highest * (1 - SL_PCT):
                pnl = ((price - entry_price) / entry_price) * 100
                total_pnl += pnl
                losses += 1
                in_pos = False
        else:
            if not row['bullish']: continue
            if row['rsi'] > rsi_max or row['rsi'] < 40: continue
            if row['macd'] <= row['macd_signal']: continue
            if row['vol_ratio'] < 1.5: continue
            if row['vol_min3'] < vol_min3_thresh: continue
            if require_macd_rising and not row['macd_hist_rising']: continue

            in_pos = True
            entry_price = price
            highest = price

    trades = wins + losses
    wr = wins/trades*100 if trades else 0
    return trades, wins, losses, wr, total_pnl


if __name__ == "__main__":
    print('=== FILTER OPTIMIZATION ANALYSIS (60 days, 7 symbols) ===')
    print()

    configs = [
        {'name': 'Current (vol_min3>=1.0)', 'rsi_max': 70, 'vol_min3': 1.0, 'macd_rising': False},
        {'name': 'Tighter RSI (<=65)', 'rsi_max': 65, 'vol_min3': 1.0, 'macd_rising': False},
        {'name': 'Tighter RSI (<=60)', 'rsi_max': 60, 'vol_min3': 1.0, 'macd_rising': False},
        {'name': 'Higher vol_min3 (>=1.2)', 'rsi_max': 70, 'vol_min3': 1.2, 'macd_rising': False},
        {'name': 'Higher vol_min3 (>=1.5)', 'rsi_max': 70, 'vol_min3': 1.5, 'macd_rising': False},
        {'name': 'MACD rising required', 'rsi_max': 70, 'vol_min3': 1.0, 'macd_rising': True},
        {'name': 'RSI<=65 + MACD rising', 'rsi_max': 65, 'vol_min3': 1.0, 'macd_rising': True},
        {'name': 'RSI<=60 + vol_min3>=1.2', 'rsi_max': 60, 'vol_min3': 1.2, 'macd_rising': False},
    ]

    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'ARBUSDT', 'AVAXUSDT', 'BNBUSDT']
    results = {c['name']: {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0} for c in configs}

    for sym in symbols:
        print(f"Fetching {sym}...")
        df = fetch_data(sym)
        df = calculate_indicators(df)

        for cfg in configs:
            t, w, l, wr, pnl = simulate(df, cfg['rsi_max'], cfg['vol_min3'], cfg['macd_rising'])
            results[cfg['name']]['trades'] += t
            results[cfg['name']]['wins'] += w
            results[cfg['name']]['losses'] += l
            results[cfg['name']]['pnl'] += pnl

    print()
    print(f"{'Config':<30} {'Trades':>7} {'Wins':>6} {'Losses':>7} {'WinRate':>8} {'P&L':>10}")
    print('-' * 75)

    for cfg in configs:
        r = results[cfg['name']]
        wr = r['wins']/r['trades']*100 if r['trades'] else 0
        print(f"{cfg['name']:<30} {r['trades']:>7} {r['wins']:>6} {r['losses']:>7} {wr:>7.1f}% {r['pnl']:>+9.2f}%")

    # Find best config
    best = max(results.items(), key=lambda x: x[1]['pnl'])
    current = results['Current (vol_min3>=1.0)']

    print()
    print(f">>> BEST CONFIG: {best[0]}")
    print(f"    P&L: {best[1]['pnl']:+.2f}% (vs current {current['pnl']:+.2f}%)")
    print(f"    Improvement: {best[1]['pnl'] - current['pnl']:+.2f}%")
