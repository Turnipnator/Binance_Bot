"""
Check for valid entry signals since the sustained volume filter was implemented
"""
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from datetime import datetime

client = Client()

def fetch_and_analyze(symbol, start_date='2026-01-16'):
    klines = client.get_historical_klines(symbol=symbol, interval='5m',
        start_str=start_date, end_str=datetime.now().strftime('%Y-%m-%d %H:%M'))

    if not klines:
        return [], []

    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

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

    df['bullish'] = (df['ema8'] > df['ema21']) & (df['ema21'] > df['ema50'])
    df = df.dropna()

    valid_entries = []
    near_misses = []

    for idx in range(len(df)):
        row = df.iloc[idx]
        checks = {
            'bullish_trend': bool(row['bullish']),
            'rsi_ok': 40 <= row['rsi'] <= 70,
            'macd_ok': row['macd'] > row['macd_signal'],
            'vol_ratio_ok': row['vol_ratio'] >= 1.5,
            'vol_min3_ok': row['vol_min3'] >= 1.5
        }

        passed = sum(checks.values())

        if all(checks.values()):
            valid_entries.append({
                'ts': str(row['timestamp']),
                'price': row['close'],
                'rsi': row['rsi'],
                'vol_ratio': row['vol_ratio'],
                'vol_min3': row['vol_min3']
            })
        elif passed >= 4:
            failed = [k for k, v in checks.items() if not v]
            near_misses.append({
                'ts': str(row['timestamp']),
                'failed': failed,
                'vol_ratio': row['vol_ratio'],
                'vol_min3': row['vol_min3']
            })

    return valid_entries, near_misses


if __name__ == "__main__":
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'ARBUSDT', 'AVAXUSDT', 'BNBUSDT',
               'SUIUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'TONUSDT', 'SHIBUSDT', 'BONKUSDT']

    print('=== SIGNAL ANALYSIS SINCE JAN 16 ===')
    print('(Checking if bot should have entered any trades)')
    print()

    total_valid = 0
    all_entries = []

    for sym in symbols:
        valid, near = fetch_and_analyze(sym)
        total_valid += len(valid)

        for v in valid:
            v['symbol'] = sym
            all_entries.append(v)

        if valid:
            print(f"{sym}: {len(valid)} valid entries")
            for v in valid[:2]:
                print(f"  {v['ts']}: vol={v['vol_ratio']:.2f}x, vol_min3={v['vol_min3']:.2f}x")
            if len(valid) > 2:
                print(f"  ... and {len(valid)-2} more")
        else:
            if near:
                failed_counts = {}
                for n in near:
                    for f in n['failed']:
                        failed_counts[f] = failed_counts.get(f, 0) + 1
                if failed_counts:
                    top_fail = max(failed_counts.items(), key=lambda x: x[1])
                    print(f"{sym}: 0 valid, {len(near)} near misses (blocked by: {top_fail[0]})")
            else:
                print(f"{sym}: 0 valid entries")

    print()
    print('=' * 60)
    print(f"TOTAL VALID ENTRIES SINCE JAN 16: {total_valid}")

    if total_valid > 0:
        print()
        print("NOTE: These are candles where ALL conditions were met.")
        print("The bot should have entered on these signals.")
        print()
        print("First 5 missed signals:")
        for e in all_entries[:5]:
            print(f"  {e['symbol']} @ {e['ts']}: price={e['price']:.4f}")
