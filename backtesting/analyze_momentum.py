"""
Analyze momentum score components to understand why signals aren't triggering
"""
import pandas as pd
import pandas_ta as ta
from binance.client import Client

client = Client()

def analyze_momentum_score(symbol):
    klines = client.get_historical_klines(symbol=symbol, interval='5m', limit=200)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    df['ema8'] = ta.ema(df['close'], length=8)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']

    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']

    try:
        df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    except:
        df['vwap'] = df['close']

    row = df.iloc[-1]
    price = row['close']
    ema_fast, ema_slow, ema_trend = row['ema8'], row['ema21'], row['ema50']

    # Trend
    trend_bullish = price > ema_fast > ema_slow > ema_trend
    if trend_bullish:
        ema_sep = ((ema_fast - ema_trend) / ema_trend) * 100
        trend_strength = min(ema_sep / 5.0, 1.0)
    else:
        trend_strength = 0.0
        ema_sep = ((ema_fast - ema_trend) / ema_trend) * 100 if ema_trend else 0

    # RSI
    rsi = row['rsi'] if pd.notna(row['rsi']) else 50
    if 50 < rsi < 70: rsi_mom = 1.0
    elif 40 < rsi < 50: rsi_mom = 0.5
    elif 70 < rsi < 80: rsi_mom = 0.7
    else: rsi_mom = 0.0

    # MACD
    macd_val = row['macd'] if pd.notna(row['macd']) else 0
    macd_sig = row['macd_signal'] if pd.notna(row['macd_signal']) else 0
    macd_h = row['macd_hist'] if pd.notna(row['macd_hist']) else 0
    macd_bull = macd_val > macd_sig and macd_h > 0
    macd_str = abs(macd_h) / abs(macd_val) if macd_val != 0 else 0
    macd_mom = min(macd_str, 1.0) if macd_bull else 0.0

    # Volume
    vol_ratio = row['vol_ratio'] if pd.notna(row['vol_ratio']) else 0
    vol_mom = min(vol_ratio / 2.0, 1.0)

    # VWAP
    vwap_val = row['vwap'] if pd.notna(row['vwap']) else price
    vwap_str = 1.0 if price > vwap_val else 0.3

    # Total
    score = trend_strength*0.35 + rsi_mom*0.25 + macd_mom*0.20 + vol_mom*0.10 + vwap_str*0.10

    return {
        'trend_bullish': trend_bullish,
        'ema_sep': ema_sep,
        'trend_strength': trend_strength,
        'rsi': rsi,
        'rsi_mom': rsi_mom,
        'macd_mom': macd_mom,
        'vol_mom': vol_mom,
        'vwap_str': vwap_str,
        'score': score
    }


if __name__ == "__main__":
    print('=== MOMENTUM SCORE BREAKDOWN (Current) ===')
    print()

    for sym in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ARBUSDT', 'LINKUSDT', 'XRPUSDT']:
        r = analyze_momentum_score(sym)
        trend_status = "BULLISH" if r['trend_bullish'] else "not bullish"
        print(f"{sym}:")
        print(f"  Trend: {trend_status} (EMA separation: {r['ema_sep']:.2f}%)")
        print(f"  Components:")
        print(f"    trend_strength: {r['trend_strength']:.2f} * 35% = {r['trend_strength']*0.35:.2f}")
        print(f"    rsi_momentum:   {r['rsi_mom']:.2f} * 25% = {r['rsi_mom']*0.25:.2f}")
        print(f"    macd_momentum:  {r['macd_mom']:.2f} * 20% = {r['macd_mom']*0.20:.2f}")
        print(f"    volume_mom:     {r['vol_mom']:.2f} * 10% = {r['vol_mom']*0.10:.2f}")
        print(f"    vwap_strength:  {r['vwap_str']:.2f} * 10% = {r['vwap_str']*0.10:.2f}")
        print(f"  TOTAL SCORE: {r['score']:.2f} (need >= 0.70)")
        print()

    print('=' * 60)
    print('KEY INSIGHT:')
    print('The trend_strength component requires ~5% EMA separation to max out.')
    print('In ranging/consolidating markets, EMAs are close together.')
    print()
    print('To reach 0.70 with trend_strength=0:')
    print('  Max = 0 + 0.25 + 0.20 + 0.10 + 0.10 = 0.65 (impossible!)')
    print()
    print('To reach 0.70 with perfect other components:')
    print('  Need trend_strength >= 0.15 (0.15*0.35 = 0.05)')
    print('  Which requires EMA separation >= 0.75%')
