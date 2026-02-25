"""
Fetch and analyze all BNB/USDT trades from Binance account
"""
from binance.client import Client
from datetime import datetime
import os

client = Client(os.environ['BINANCE_API_KEY'], os.environ['BINANCE_API_SECRET'])

# Get all BNB trades
trades = client.get_my_trades(symbol='BNBUSDT', limit=100)

print('=== ALL BNBUSDT TRADES ON ACCOUNT ===')
print()

total_buy_qty = 0
total_buy_quote = 0
total_sell_qty = 0
total_sell_quote = 0

# Group by order ID to see distinct orders
order_ids = set()

for t in trades:
    ts = datetime.fromtimestamp(t['time']/1000).strftime('%Y-%m-%d %H:%M:%S')
    side = 'BUY' if t['isBuyer'] else 'SELL'
    price = float(t['price'])
    qty = float(t['qty'])
    quote = float(t['quoteQty'])
    role = 'Maker' if t['isMaker'] else 'Taker'
    oid = t['orderId']
    commission = float(t['commission'])
    comm_asset = t['commissionAsset']

    order_ids.add(oid)

    if t['isBuyer']:
        total_buy_qty += qty
        total_buy_quote += quote
    else:
        total_sell_qty += qty
        total_sell_quote += quote

    print(f"{ts}  {side:<5} {price:>10.2f}  qty={qty:.5f}  total=${quote:.2f}  {role}  order={oid}  fee={commission:.6f} {comm_asset}")

print()
print('=' * 70)
print('SUMMARY')
print('=' * 70)
print(f"Total trades: {len(trades)}")
print(f"Unique orders: {len(order_ids)}")
print()
print(f"Total BUYs:  {total_buy_qty:.5f} BNB  (cost: ${total_buy_quote:.2f})")
print(f"Total SELLs: {total_sell_qty:.5f} BNB  (received: ${total_sell_quote:.2f})")
print(f"Net BNB position: {total_buy_qty - total_sell_qty:.5f}")
print(f"Net USDT P&L: ${total_sell_quote - total_buy_quote:.2f}")

if total_sell_qty > 0 and total_buy_qty > 0:
    avg_buy = total_buy_quote / total_buy_qty
    avg_sell = total_sell_quote / total_sell_qty
    print(f"Avg buy price: ${avg_buy:.2f}")
    print(f"Avg sell price: ${avg_sell:.2f}")

# Also check all recent trades across all symbols for context
print()
print('=' * 70)
print('ALL RECENT TRADES (ALL SYMBOLS) - Last 24h')
print('=' * 70)

symbols_to_check = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT',
                     'AVAXUSDT', 'SUIUSDT', 'LINKUSDT', 'XRPUSDT', 'ARBUSDT',
                     'TRXUSDT', 'TONUSDT', 'SHIBUSDT', 'BONKUSDT']

for sym in symbols_to_check:
    try:
        sym_trades = client.get_my_trades(symbol=sym, limit=10)
        recent = [t for t in sym_trades if (datetime.now().timestamp() * 1000 - t['time']) < 7 * 86400000]  # Last 7 days
        if recent:
            print(f"\n{sym}: {len(recent)} trades in last 7 days")
            for t in recent:
                ts = datetime.fromtimestamp(t['time']/1000).strftime('%m-%d %H:%M')
                side = 'BUY' if t['isBuyer'] else 'SELL'
                quote = float(t['quoteQty'])
                print(f"  {ts} {side} ${quote:.2f}")
    except:
        pass

# Check account balance
print()
print('=' * 70)
print('CURRENT ACCOUNT BALANCES')
print('=' * 70)
account = client.get_account()
for b in account['balances']:
    free = float(b['free'])
    locked = float(b['locked'])
    if free > 0 or locked > 0:
        print(f"  {b['asset']}: free={free:.6f}, locked={locked:.6f}")
