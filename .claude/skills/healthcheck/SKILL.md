---
name: healthcheck
description: Run a comprehensive health check on the Binance trading bot
---

# Binance Trading Bot Health Check

Run a comprehensive health check on the binance-trading-bot. Work through each section systematically and provide a summary dashboard at the end.

## VPS Details
Read VPS connection details from CLAUDE.local.md (contains server IP, SSH key path, bot path).
- Container name: binance-trading-bot

## 1. PROCESS STATUS
- Is the bot process running? Check with `docker ps`
- How long has it been running (uptime)?
- Any recent restarts or crashes?

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "docker ps --format '{{.Names}}\t{{.Status}}\t{{.RunningFor}}' | grep binance"
```

## 2. LOG ANALYSIS
- Check the last 100 lines of logs for errors, warnings, or anomalies
- Identify any recurring error patterns
- Look for WebSocket connection issues

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "docker logs binance-trading-bot --tail 100 2>&1"
ssh -i <SSH_KEY> <USER>@<VPS_IP> "docker logs binance-trading-bot 2>&1 | grep -iE 'error|warn|fail|disconnect|reconnect|rate.limit' | tail -20"
```

## 3. SIGNAL GENERATION
- Is the bot actively producing trading signals?
- What was the last signal generated and when?
- Check data files for recent activity

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "ls -la <BOT_PATH>/data/"
ssh -i <SSH_KEY> <USER>@<VPS_IP> "docker exec binance-trading-bot cat /app/data/state.json 2>/dev/null || echo 'No state file'"
```

## 4. PERFORMANCE METRICS
- Check current trades/positions
- Review recent P&L if logged
- Check open positions

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "docker exec binance-trading-bot cat /app/data/trading_stats.json 2>/dev/null || echo 'No stats file'"
ssh -i <SSH_KEY> <USER>@<VPS_IP> "docker exec binance-trading-bot cat /app/data/positions.json 2>/dev/null || echo 'No positions file'"
```

## 5. SYSTEM RESOURCES
- RAM usage, disk space, CPU usage

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "free -h && echo '---' && df -h / && echo '---' && top -bn1 | head -12"
```

## 6. CONFIGURATION REVIEW
- Check key environment variables are set correctly
- Verify trading pairs configured

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "grep -E 'ENABLE_|TRADING_PAIRS|MODE|STRATEGY' <BOT_PATH>/.env 2>/dev/null | head -15"
```

## 7. BINANCE-SPECIFIC CHECKS
- WebSocket connection status to exchange
- Current open positions and unrealised P&L
- Funding rate considerations if holding futures
- API rate limit usage (are we near limits?)
- Check for IP bans or restrictions

## 8. STRATEGY EDGE ASSESSMENT
- Calculate win rate from stats
- Is the strategy performing as expected?
- Any parameter tweaks recommended?

## 8.5 MEAN-REVERSION MONITOR (live vs backtest)
The mean-reversion strategy went live 2026-07-02 with an **unproven** live edge (deployed on a 53-trade backtest, PF 1.82 @0.2% fee). This section tracks whether the real fills hold up. Run the monitor (stdlib-only, runs on the VPS host — no container/rebuild needed):

```bash
ssh -i <SSH_KEY> <USER>@<VPS_IP> "python3 /opt/Binance_Bot/mr_monitor.py"
```

Interpret the output:
- **0 MR trades**: strategy is armed but dormant (needs BTC > daily EMA50 **and** a liquid pair at 15m RSI<30). Nothing to judge yet — expected while BTC is below its daily EMA50.
- **<30 trades**: directional only, not conclusive.
- **Key comparisons vs backtest** (WR ~70%, PF 1.82, avgW +0.59% / avgL −0.80%):
  - PF < 1.0 over 30+ trades → **losing**; recommend the kill switch the monitor prints (`ENABLE_MEAN_REVERSION=false`).
  - avgW materially below backtest → **slippage/execution drag** eroding the thin edge (the #1 risk flagged at deploy).
  - Excess `stop_loss` exits (backtest exits mostly at the EMA20 target) → dips reverting less than modeled.
- Per-strategy split: momentum vs mean_reversion trade counts and P&L are separable because trades are tagged `strategy` in `trades.json`.

The monitor also prints a **STRATEGY HEAD-TO-HEAD**: momentum vs mean_reversion, both under current rules (trades since 2026-07-02 only — earlier momentum trades are old-rule and NOT comparable). It reports each strategy's n / WR / net$ / PF / **expectancy $ per trade**. Read BOTH: net$ = what grows the account, expectancy = edge quality normalised for the fact MR trades far more often than momentum. Needs ~15 trades each before it's meaningful.

Report MR's live line, the backtest line, the head-to-head table, and a one-line verdict (on track / slipping / disable; which strategy leads).

## 9. RECOMMENDATIONS
Provide prioritised recommendations:
- P1 (Critical): Issues that need immediate attention
- P2 (Important): Should be addressed soon
- P3 (Nice to have): Optimisations for later

## 10. SUMMARY DASHBOARD
Present a quick status summary table:

| Check | Status | Notes |
|-------|--------|-------|
| Process Running | ?/? | |
| Logs Healthy | ?/?/? | |
| Signals Active | ?/? | |
| Resources OK | ?/?/? | |
| WebSocket Connected | ?/? | |
| Strategy Edge (momentum) | ?/?/? | |
| Mean-Reversion vs Backtest | ?/?/? | n trades; on track / slipping / dormant |

Traffic light summary: ? All good / ? Minor issues / ? Needs attention
