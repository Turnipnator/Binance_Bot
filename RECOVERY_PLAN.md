# 🎯 RECOVERY PLAN - Getting Back to Profitable

**Current Status:** $350.73 remaining (-$149.27 loss)
**Goal:** Recover to $500+ through safe, tested trading
**Mode:** PAPER TRADING until proven

---

## ✅ IMMEDIATE FIXES (DONE)

1. **✅ Switched to PAPER MODE**
   - No more real money at risk
   - Testing on Binance testnet
   
2. **✅ Reduced Position Sizing**
   - Changed from 20% max → 10% max per trade
   - $350 balance = max $35 positions (was $70)
   
3. **✅ Fixed Volume Filtering**
   - Require minimum 1.0x average volume
   - No more churning trades
   
4. **✅ Documented All Bugs**
   - See POST_MORTEM.md for full analysis
   - Root causes identified

---

## 🔧 CRITICAL FIXES NEEDED (In Progress)

### Fix #1: Real Stop-Loss Orders ⚠️ CRITICAL
**Problem:** Stop losses only in bot memory, not on Binance
**Solution:** Use OCO (One-Cancels-Other) orders
- Place market buy
- Immediately place stop-loss sell order
- Place take-profit limit sell order
- Both on Binance exchange, not in code

**Code Location:** `trading_bot.py` line 463

### Fix #2: Persistent Daily P&L ⚠️ CRITICAL  
**Problem:** Daily limits reset on bot restart
**Solution:** Save to file: `./data/daily_pnl.json`
```json
{
  "date": "2025-10-31",
  "daily_pnl": -149.27,
  "trades_today": 92,
  "last_updated": 1761926000
}
```

**Code Location:** `utils/risk_manager.py` line 74

### Fix #3: Live Balance Queries
**Problem:** Bot uses stale balance from memory
**Solution:** Query Binance before EVERY trade
```python
def get_current_balance(self):
    account = self.client.get_account()
    usdt = next(b for b in account['balances'] if b['asset'] == 'USDT')
    return float(usdt['free']) + float(usdt['locked'])
```

### Fix #4: Telegram Status Accuracy
**Problem:** Shows internal balance, not real balance
**Solution:** Query Binance when /status is called

---

## 📅 TIMELINE

### Week 1 (Nov 1-7): Fix & Test
- **Day 1-2:** Implement critical fixes
- **Day 3-4:** Test in paper mode
- **Day 5-7:** Monitor paper performance
- **Target:** +5% in paper mode

### Week 2 (Nov 8-14): Prove It Works
- **Continue paper trading**
- **Target:** +10% total in paper mode
- **Verify:** All limits working, no bugs
- **Decision point:** Go live or keep testing?

### Week 3+ (If Successful): Cautious Return
- **Start with:** $100 of the $350
- **Max risk:** $2 per trade (2%)
- **Daily limits:** +$5 profit, -$3 loss
- **Prove:** Can make money consistently

---

## 🎯 SUCCESS CRITERIA

### Before Going Live Again:
- [ ] 14+ days paper trading with NO critical bugs
- [ ] Paper mode showing +15% returns
- [ ] All stop losses working 100%
- [ ] Daily limits working across restarts
- [ ] Telegram status accurate
- [ ] Position sizing conservative (5-8% max)
- [ ] Win rate > 55%
- [ ] Average trade quality improved

### Live Trading Checklist:
- [ ] Start with only $100 (not full $350)
- [ ] Max $5 per trade (5% of $100)
- [ ] Monitor EVERY trade for first week
- [ ] No overnight positions initially
- [ ] Withdraw profits weekly
- [ ] Only scale up after 2+ weeks success

---

## 💰 RECOVERY MATH

**Current:** $350.73
**Target:** $500.00
**Required:** +$149.27 (+42.6%)

### Conservative Path (Recommended):
- **Week 1:** +$17.50 (5%) = $368.23
- **Week 2:** +$18.40 (5%) = $386.63
- **Week 3:** +$19.30 (5%) = $405.93
- **Week 4:** +$20.30 (5%) = $426.23
- **Week 5:** +$21.30 (5%) = $447.53
- **Week 6:** +$22.40 (5%) = $469.93
- **Week 7:** +$23.50 (5%) = $493.43
- **Week 8:** +$6.57 (1.3%) = **$500.00 ✓**

**Total Time:** ~2 months to full recovery

### Aggressive Path (Riskier):
- 10% per week = 5 weeks to recovery
- Higher risk of further losses
- NOT recommended after what happened

---

## 🚨 RED LINES (Never Cross These)

1. **No live trading until 14+ days paper success**
2. **No positions > 10% of balance**
3. **No trading if daily limit hit** (even after restart)
4. **No ignoring stop losses** (they MUST be real orders)
5. **No more than 3 concurrent positions**
6. **No trading pairs with volume < 1.0x average**

---

## 📊 WHAT YOU'LL SEE

### In Paper Mode:
- Bot will trade on testnet (fake money)
- Telegram notifications will say **[PAPER]**
- You can verify strategies work
- No risk to remaining $350

### When Monitoring:
```bash
tail -f ./logs/trading_bot.log
```

Look for:
- Position sizes (should be max $35 now, not $75)
- Stop losses being placed
- Daily P&L tracking
- No churning (volume checks working)

---

## 🤝 THE DEAL

**You:** Give me 2 weeks to prove this works in paper mode
**Me:** Fix all bugs, test thoroughly, document everything
**Result:** Either we have a working bot, or we accept defeat gracefully

**If it works:** Cautious live return with $100
**If it doesn't:** At least we didn't lose more of the $350

---

**Next:** I'm going to implement the critical fixes now. You'll see commits and updates. Paper mode is active, your $350 is safe.
