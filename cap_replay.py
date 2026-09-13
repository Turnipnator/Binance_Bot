#!/usr/bin/env python3
"""
Concurrent-trade-cap replay: is MAX_CONCURRENT_TRADES worth raising?

Reads data/trades.json, finds every window in which the live bot held the
maximum number of positions (the cap was binding), then checks which other
mean-reversion-liquid pairs met the MR entry rule on a CLOSED 15m bar during
those windows and simulates them under the live MR exit rules (touch of the
15m EMA20 / 3% stop / 24h time-stop). The output is the number of signals the
cap actually blocked and what they would have earned. Stdlib only, public
klines, so it runs on the VPS host directly (no container, no rebuild):

    python3 /opt/Binance_Bot/cap_replay.py            # default: data/trades.json, cap 5
    python3 /opt/Binance_Bot/cap_replay.py --cap 6    # what a cap of 6 would have blocked
    python3 /opt/Binance_Bot/cap_replay.py --trades /path/to/trades.json

Approximations (all conservative): closed bars only (live reads the partial
bar), stop checked before target within a bar, BTC daily-EMA50 gate evaluated
once per window, momentum signals are NOT replayed (only MR is frequent enough
to matter). Trade timestamps in trades.json are BST (UTC+1).

Result 2026-09-13 (cap 5): bound for 24.8h in 8 months over 5 windows, only
5.9h since MR went live; 2 blocked MR signals worth +$0.35 combined. Verdict:
leave the cap at 5. See CLAUDE.local.md session 2026-09-13.
"""
import argparse, os
import json, urllib.request, urllib.parse, time
from datetime import datetime, timedelta, timezone

_ap=argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
_ap.add_argument('--trades', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'trades.json'))
_ap.add_argument('--cap', type=int, default=5, help='MAX_CONCURRENT_TRADES to test (default 5)')
_ap.add_argument('--notional', type=float, default=150.0, help='USD per hypothetical trade (default 150)')
_args=_ap.parse_args()
TRADES=_args.trades
MAXC=_args.cap
PAIRS=['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','LINKUSDT','LTCUSDT','ADAUSDT','AVAXUSDT','TRXUSDT','SUIUSDT','ZECUSDT']
UTC=timezone.utc; BST=timezone(timedelta(hours=1))
ZEC_FROM=datetime(2026,9,1,13,29,tzinfo=UTC)
FEE=0.0015; NOTIONAL=_args.notional; STOP=0.03; TIME_STOP=timedelta(hours=24); WIN=250

t=json.load(open(TRADES))['trades']
print('source: %s  cap: %d'%(TRADES,MAXC))
for r in t:
    r['et']=datetime.fromisoformat(r['entry_time']).replace(tzinfo=BST).astimezone(UTC)
    r['xt']=datetime.fromisoformat(r['exit_time']).replace(tzinfo=BST).astimezone(UTC)
ev=sorted([(r['et'],1,r) for r in t]+[(r['xt'],-1,r) for r in t], key=lambda e:(e[0],e[1]))
n=0; intervals=[]; cur=None
for ts,d,r in ev:
    n+=d
    if n>=MAXC and cur is None: cur=ts
    elif n<MAXC and cur is not None: intervals.append((cur,ts)); cur=None
if cur: intervals.append((cur,datetime.now(UTC)))
print('cap-bound windows (open positions == %d):'%MAXC)
tot=timedelta(0)
for a,b in intervals:
    held=[(r['pair'][:-4], r.get('strategy','mom')[:3]) for r in t if r['et']<=a<r['xt'] or (a<=r['et']<b)]
    print('  %s -> %s UTC (%.1fh) held: %s'%(a.strftime('%m-%d %H:%M'),b.strftime('%m-%d %H:%M'),(b-a).total_seconds()/3600,sorted(set(held))))
    tot+=b-a
print('  total cap-bound time: %.1fh over %d windows'%(tot.total_seconds()/3600,len(intervals)))
if not intervals: raise SystemExit

def klines(sym, interval, start, end):
    out=[]; s=int(start.timestamp()*1000); e=int(end.timestamp()*1000)
    while s<e:
        q=urllib.parse.urlencode(dict(symbol=sym,interval=interval,startTime=s,endTime=e,limit=1000))
        with urllib.request.urlopen('https://api.binance.com/api/v3/klines?'+q, timeout=20) as f: k=json.load(f)
        if not k: break
        out+=k; s=k[-1][6]+1
        if len(k)<1000: break
        time.sleep(0.15)
    return out
def ema_window(vals, length):
    seed=sum(vals[:length])/length; a=2/(length+1); e=seed
    for v in vals[length:]: e=a*v+(1-a)*e
    return e
def rsi_window(vals, length=14):
    d=[vals[i]-vals[i-1] for i in range(1,len(vals))]
    g=[max(x,0) for x in d]; l=[max(-x,0) for x in d]
    ag=sum(g[:length])/length; al=sum(l[:length])/length
    for i in range(length,len(d)):
        ag=(ag*(length-1)+g[i])/length; al=(al*(length-1)+l[i])/length
    return 100.0 if al==0 else 100-100/(1+ag/al)

start=min(a for a,b in intervals)-timedelta(minutes=15*(WIN+5)); end=max(b for a,b in intervals)+TIME_STOP+timedelta(hours=2)
K={s:klines(s,'15m',start,end) for s in PAIRS}
# BTC daily gate at each window start (bot: 100 daily bars, EMA50, last close > ema50)
btc_d=klines('BTCUSDT','1d',start-timedelta(days=105),end)
def gate_open(when):
    bars=[b for b in btc_d if b[0]<=int(when.timestamp()*1000)][-100:]
    c=[float(b[4]) for b in bars]; return c[-1]>ema_window(c,50), c[-1]/ema_window(c,50)-1

print('\nblocked MR signals (closed-bar rule) during cap-bound windows:')
grand=[]
for a,b in intervals:
    g,gap=gate_open(a)
    print('\n== window %s -> %s  BTC gate %s (%+.1f%% vs daily EMA50)'%(a.strftime('%m-%d %H:%M'),b.strftime('%m-%d %H:%M'),'OPEN' if g else 'CLOSED',gap*100))
    if not g: continue
    extras=[]
    for sym in PAIRS:
        if sym=='ZECUSDT' and a<ZEC_FROM: continue
        bars=K[sym]; i=WIN
        while i<len(bars):
            ct=datetime.fromtimestamp(bars[i][6]/1000,UTC)
            if ct>=b: break
            if ct<a or any(r['pair']==sym and r['et']<=ct<r['xt'] for r in t): i+=1; continue
            w=[float(x[4]) for x in bars[i-WIN+1:i+1]]
            rsi=rsi_window(w); e200=ema_window(w,200); c=w[-1]
            if rsi<30 and c>e200:
                entry=c; stop=entry*(1-STOP); res=None
                for j in range(i+1,len(bars)):
                    o,h,lo,cj=[float(bars[j][k]) for k in (1,2,3,4)]
                    tj=datetime.fromtimestamp(bars[j][6]/1000,UTC)
                    e20=ema_window([float(x[4]) for x in bars[j-WIN+1:j+1]],20)
                    if lo<=stop: res=(stop,'stop',tj,j); break
                    if h>=e20: res=(max(e20,o),'target',tj,j); break
                    if tj-ct>=TIME_STOP: res=(cj,'time',tj,j); break
                if res is None: i+=1; continue
                px,why,tj,j=res; pct=px/entry-1; net=NOTIONAL*pct-NOTIONAL*FEE
                extras.append((ct,sym,rsi,entry,px,why,tj,pct,net))
                i=j+1
            else: i+=1
    extras.sort()
    # how many extra slots would have been needed simultaneously
    peak=0
    for ct,sym,rsi,entry,px,why,tj,pct,net in extras:
        peak=max(peak,sum(1 for e in extras if e[0]<=ct<e[6]))
    for ct,sym,rsi,entry,px,why,tj,pct,net in extras:
        print('  %s %-8s rsi=%4.1f entry=%.4g -> %s %.4g at %s  %+.2f%%  net %+.2f'%(ct.strftime('%m-%d %H:%M'),sym[:-4],rsi,entry,why,px,tj.strftime('%m-%d %H:%M'),pct*100,net))
    print('  -> %d blocked signals, peak %d extra slots needed, net $%+.2f at $%.0f each'%(len(extras),peak,sum(e[8] for e in extras),NOTIONAL))
    grand+=extras
print('\nTOTAL blocked signals: %d, net $%+.2f, wins %d, exits %s'%(len(grand),sum(e[8] for e in grand),sum(1 for e in grand if e[8]>0),{k:sum(1 for e in grand if e[5]==k) for k in ('target','stop','time')}))
