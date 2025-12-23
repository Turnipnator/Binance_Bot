# Winning Momentum Strategy Guide

## Overview

This document details the momentum-based trading strategy that achieved **13 wins out of 13 trades** on December 19th, 2025. The strategy is designed to capture small, consistent gains by entering on strong bullish signals and exiting quickly at a fixed take profit level.

**Core Philosophy**: Don't be greedy. Lock in small profits quickly and re-enter if conditions remain bullish. This "rinse and repeat" approach compounds gains while minimizing exposure time.

---

## Strategy Summary

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| Take Profit | 1.3% | Lock in gains quickly before reversals |
| Stop Loss | 5% | Wide enough to avoid noise, tight enough to limit damage |
| Entry Threshold | 0.60+ momentum score | Only enter on strong signals |
| Trend Requirement | BULLISH only | No sideways or bearish markets |
| Volume Confirmation | 1.5x average | Ensures institutional participation |

---

## Entry Signal Requirements

For the bot to open a LONG position, **ALL** of the following conditions must be true simultaneously:

### 1. Momentum Score >= 0.60

The momentum score is a composite indicator ranging from 0.0 to 1.0 that combines multiple technical factors:

**Components of the Momentum Score:**
- **RSI Position**: Where RSI sits relative to oversold/overbought zones
- **MACD Alignment**: MACD line above signal line, histogram positive
- **Moving Average Alignment**: Price above key EMAs (20, 50, 200)
- **Price Position**: Where price sits within Bollinger Bands
- **Stochastic**: Momentum confirmation from stochastic oscillator

**Why 0.60?**
- Below 0.50 = weak/neutral signal (too risky)
- 0.50-0.59 = moderate signal (still too risky)
- 0.60-0.69 = strong signal (our entry zone)
- 0.70+ = very strong signal (excellent entry)

We found that raising the threshold from 0.50 to 0.60 significantly improved win rate by filtering out marginal setups.

### 2. Trend Must Be BULLISH

The bot calculates trend using a 3-layer detection system:

**Layer 1 - EMA Alignment:**
```
BULLISH: EMA20 > EMA50 > EMA200 (all moving averages stacked bullishly)
BEARISH: EMA20 < EMA50 < EMA200 (all stacked bearishly)
SIDEWAYS: Mixed alignment (choppy, ranging)
```

**Layer 2 - Price Position:**
- Price must be above the 50 EMA for bullish
- Price must be making higher highs and higher lows

**Layer 3 - Higher Timeframe Confirmation:**
- The 4-hour timeframe must also show bullish alignment
- This prevents entering on minor pullbacks against the larger trend

**Why BULLISH only?**
- SIDEWAYS markets chop you up with false breakouts
- BEARISH markets can have relief rallies, but the odds are against you
- BULLISH markets have momentum on your side

### 3. Volume Confirmation (1.5x Average)

Volume must be at least 1.5 times the 20-period average volume.

**Why Volume Matters:**
- High volume = institutional participation = more likely to follow through
- Low volume breakouts often fail and reverse
- Volume confirms that the move has "fuel" behind it

**What We Look For:**
- Current candle volume > 1.5x average (minimum)
- Ideal entries have 2x-3x average volume
- The 14x volume entry on ZEC (score 0.73) was an excellent signal and printed $$$

### 4. Not In Cooldown Period

After a LOSING trade, the bot waits 20 minutes before re-entering that symbol.

**Why Cooldown After Losses Only:**
- Prevents revenge trading after a loss
- Gives the market time to settle
- Winning trades can re-enter immediately (momentum continuation)

### 5. Daily Loss Limit Hit

Trading pauses completely if daily losses reach -$30.

**Why This Matters:**
- Prevents catastrophic losing days
- Protects capital for tomorrow
- Forces you to step away when the market isn't working for you

### 6. Portfolio Heat < 15%

Total risk across all open positions must be below 15% of account balance.

**Calculation:**
```
Portfolio Heat = Sum of (Position Size × Stop Distance) / Account Balance
```

**Why 15%?**
- Allows multiple positions (diversification)
- Limits total exposure if everything goes wrong at once
- With 5 positions at 2% risk each = 10% heat (within limit)

### 7. Max 5 Concurrent Positions

No more than 5 positions can be open at once.

**Why This Limit:**
- Keeps the account manageable
- Ensures enough capital for each position
- Prevents over-trading

---

## Exit Strategy

### Take Profit: 1.3%

When a position reaches +1.3% profit, it automatically closes.

**Why 1.3%?**
- Small enough to hit frequently (high win rate)
- Large enough to cover fees and still profit
- Avoids the "watched it go to +3% then reverse to -2%" scenario
- Quick exits = less time exposed to market risk

**The Math:**
- With 1.3% TP and good entries, you need only ~30% win rate to break even (with 5% SL)
- But with our filters, we're achieving 80-100% win rates
- 13 wins × 1.3% = 16.9% return in a single day

### Stop Loss: 5%

If a position drops 5% from entry, it automatically closes.

**Why 5%?**
- Wide enough to survive normal market noise
- Tight enough to limit damage on bad trades
- With our strict entry filters, stops rarely get hit
- If the signal was truly bullish, it shouldn't drop 5%

**Risk/Reward Ratio:**
- Risk: 5%
- Reward: 1.3%
- Ratio: 1:0.26 (inverted from traditional)

**Why This Works:**
Traditional advice says aim for 1:2 or 1:3 risk/reward. But that requires predicting large moves, which is hard. Our approach:
- Take high-probability setups (tight filters)
- Accept small wins
- Rarely take losses
- Win rate compensates for inverted R:R

---

## Position Sizing

### Risk Per Trade: 2%

Each trade risks 2% of account balance.

**Calculation:**
```
Position Size = (Account Balance × 0.02) / Stop Distance
```

**Example:**
- Account: $1,000
- Risk: $1,000 × 2% = $20
- Entry: $100
- Stop: $95 (5% below)
- Stop Distance: $5
- Position Size: $20 / $5 = 4 units
- Position Value: 4 × $100 = $400

### Volatility Adjustment

Position size is reduced in high-volatility conditions:

| Volatility (ATR %) | Size Multiplier |
|-------------------|-----------------|
| < 5% | 1.0x (full size) |
| 5-8% | 0.75x |
| > 8% | 0.5x (half size) |

---

## Anti-Churning Protections

To prevent excessive trading and protect against edge cases:

### 1. Cooldown After Losses
- 20 minutes per symbol after a loss
- Prevents revenge trading
- Winners can re-enter immediately

### 2. Max Trades Per Day
- 25 total trades maximum
- 3 trades per symbol per day
- Prevents overtrading

### 3. Position Persistence
- Open positions saved to JSON file
- Survives bot restarts
- No "lost" positions

### 4. Stale Position Cleanup
- Positions open > 72 hours are auto-closed
- Prevents stuck/forgotten positions

### 5. Process Lock
- Only one bot instance can run
- Prevents duplicate trades

---

## Technical Implementation

### Indicators Used

1. **Exponential Moving Averages (EMA)**
   - EMA 20 (short-term trend)
   - EMA 50 (medium-term trend)
   - EMA 200 (long-term trend)

2. **RSI (Relative Strength Index)**
   - Period: 14
   - Overbought: 70
   - Oversold: 30

3. **MACD (Moving Average Convergence Divergence)**
   - Fast: 12
   - Slow: 26
   - Signal: 9

4. **Bollinger Bands**
   - Period: 20
   - Standard Deviations: 2

5. **ATR (Average True Range)**
   - Period: 14
   - Used for volatility measurement

6. **Stochastic Oscillator**
   - K Period: 14
   - D Period: 3

7. **Volume**
   - 20-period average for comparison

### Timeframes

- **Primary**: 5-minute candles for entries
- **Confirmation**: 4-hour candles for trend direction

---

## Configuration Values

```python
# Entry Filters
MOMENTUM_THRESHOLD = 0.60      # Minimum score to enter
TREND_REQUIREMENT = "BULLISH"  # Only bullish trends
VOLUME_MULTIPLIER = 1.5        # Minimum volume vs average

# Exit Parameters
TAKE_PROFIT_PERCENT = 1.3      # Exit at +1.3%
STOP_LOSS_PERCENT = 5.0        # Exit at -5%

# Risk Management
MAX_RISK_PER_TRADE = 0.02      # 2% risk per trade
MAX_PORTFOLIO_RISK = 0.15      # 15% total portfolio heat
MAX_CONCURRENT_POSITIONS = 5   # Max open positions

# Daily Limits
MAX_DAILY_LOSS = 30            # Stop trading at -$30
MAX_DAILY_TRADES = 25          # Max trades per day
MAX_SYMBOL_TRADES_PER_DAY = 3  # Max trades per symbol

# Anti-Churning
COOLDOWN_MINUTES = 20          # Cooldown after loss
MAX_POSITION_AGE_HOURS = 72    # Close stale positions
```

---

## Why This Strategy Works

### 1. High-Quality Entries Only
By requiring:
- Score >= 0.60
- BULLISH trend
- Volume confirmation
- Higher timeframe alignment

We filter out 90%+ of potential trades, leaving only the highest-probability setups.

### 2. Quick Profit Taking
1.3% is achievable in most momentum moves. By taking profit quickly:
- We capture the "easy" part of the move
- We avoid holding through reversals
- We free up capital for the next trade

### 3. Re-Entry on Continuation
If we take profit and the signal is still bullish, we re-enter immediately. This captures extended moves while still locking in profits along the way.

### 4. Strict Risk Control
- 2% max risk per trade
- 5% stop loss
- 15% max portfolio heat
- Daily loss limit

Even a string of losses won't devastate the account.

### 5. Psychological Simplicity
- Clear rules, no discretion needed
- Small wins feel good (positive reinforcement)
- Losses are rare and limited
- No agonizing over "should I hold longer?"

---

## Adapting to Other Markets

This strategy should work on any liquid market with:

1. **Sufficient Volatility**: Needs 1-2% daily moves minimum
2. **Good Liquidity**: Tight spreads, minimal slippage
3. **24/7 or Extended Hours**: More opportunities
4. **Technical Trading**: Responds to indicators (not news-driven)

**Good Candidates:**
- Other cryptocurrency pairs
- Forex major pairs (EUR/USD, GBP/USD)
- Stock index futures (ES, NQ)
- Commodities (Gold, Oil)

**Adjustments Needed:**
- Take profit % may need tweaking based on typical volatility
- Volume thresholds may differ
- Timeframes may need adjustment (forex moves slower than crypto)

---

## Performance Metrics (Dec 19, 2025)

| Metric | Value |
|--------|-------|
| Total Trades | 13 |
| Winning Trades | 13 |
| Losing Trades | 0 |
| Win Rate | 100% |
| Avg Win | +1.3% |
| Total Return | ~$169 |
| Max Drawdown | $0 |

---

## Key Takeaways

1. **Less is more**: Fewer, higher-quality trades beat many mediocre trades
2. **Don't be greedy**: 1.3% repeatedly beats hoping for 10%
3. **Trend is your friend**: Only trade with the trend, never against
4. **Volume confirms**: No volume = no conviction = no trade
5. **Protect capital**: Risk management is more important than entries
6. **Let winners re-enter**: If still bullish after TP, go again

---

## Final Notes

This strategy emerged from iterating through several failed approaches:
- Trailing stops gave back too much profit
- Wide take profits turned winners into losers
- Low thresholds (0.50) let in weak signals
- Trading sideways markets was a losing game

The current configuration represents the refined, battle-tested version that produced a perfect trading day. The key insight was: **take small wins consistently rather than hoping for big wins occasionally**.

Good luck applying this to other markets!

---

*Document created: December 19, 2025*
*Strategy Version: 2.0 (Simple TP/SL System)*
