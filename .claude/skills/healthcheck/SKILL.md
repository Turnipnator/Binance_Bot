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
| Strategy Edge | ?/?/? | |

Traffic light summary: ? All good / ? Minor issues / ? Needs attention
