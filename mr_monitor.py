#!/usr/bin/env python3
"""
Mean-reversion live-vs-backtest monitor.

Reads data/trades.json and reports how the LIVE mean_reversion strategy is
performing against the backtest that justified deploying it. Stdlib only, so
it runs on the VPS host directly (no container, no rebuild):

    python3 /opt/Binance_Bot/mr_monitor.py

Used by the /healthcheck skill (section 8.5). See memory
mean-reversion-signal-promising for the backtest this compares against.
"""
import json, os

# Backtest reference: conservative rsi<30 / sl3 variant at ~0.2% round-trip fee
# (2026-07-02). This is the bar the live edge must roughly clear to be real.
BT = {"wr": 69.8, "pf": 1.82, "avg_w_pct": 0.59, "avg_l_pct": -0.80}
MIN_TRADES = 30   # below this the live sample is not statistically meaningful


def _find_trades():
    for p in ("/opt/Binance_Bot/data/trades.json", "data/trades.json", "/app/data/trades.json"):
        if os.path.exists(p):
            return p
    return None


def main():
    path = _find_trades()
    if not path:
        print("MR MONITOR: trades.json not found"); return
    d = json.load(open(path))
    trades = d.get("trades", []) if isinstance(d, dict) else d
    mr = [t for t in trades if t.get("strategy") == "mean_reversion"]
    mom = [t for t in trades if t.get("strategy") != "mean_reversion"]

    print("=== MEAN-REVERSION LIVE MONITOR (vs backtest) ===")
    print("source: %s" % path)
    print("momentum trades: %d | mean_reversion trades: %d" % (len(mom), len(mr)))

    if not mr:
        print("\nNo mean_reversion trades yet. Strategy is armed but dormant until BTC > daily")
        print("EMA50 AND a liquid pair hits 15m RSI<30. Nothing to evaluate - re-run after it trades.")
        return

    wins = [t for t in mr if t.get("is_win")]
    losses = [t for t in mr if not t.get("is_win")]
    net = sum(t.get("pnl_usdt", 0) or 0 for t in mr)
    gw = sum(t.get("pnl_usdt", 0) or 0 for t in wins)
    gl = sum(t.get("pnl_usdt", 0) or 0 for t in losses)
    pf = gw / abs(gl) if gl else float("inf")
    wr = 100.0 * len(wins) / len(mr)
    avg_w = sum(t.get("pnl_percent", 0) or 0 for t in wins) / len(wins) if wins else 0.0
    avg_l = sum(t.get("pnl_percent", 0) or 0 for t in losses) / len(losses) if losses else 0.0

    reasons = {}
    for t in mr:
        r = t.get("exit_reason", "?")
        reasons[r] = reasons.get(r, 0) + 1

    print("\nLIVE:      n=%d  WR=%.1f%%  PF=%.2f  net=$%.2f  avgW=%.2f%%  avgL=%.2f%%" % (
        len(mr), wr, pf, net, avg_w, avg_l))
    print("BACKTEST:  WR=%.1f%%  PF=%.2f  ---     ---       avgW=%.2f%%  avgL=%.2f%%" % (
        BT["wr"], BT["pf"], BT["avg_w_pct"], BT["avg_l_pct"]))
    print("exit reasons: %s" % reasons)

    print("\nVERDICT:")
    if len(mr) < MIN_TRADES:
        print("  ⏳ Only %d/%d trades - NOT yet statistically meaningful; treat below as directional." % (
            len(mr), MIN_TRADES))

    if pf < 1.0:
        print("  \U0001f534 PF %.2f < 1.0 - LOSING. If it holds over %d+ trades, DISABLE (see kill switch below)." % (pf, MIN_TRADES))
    elif pf < 1.3:
        print("  \U0001f7e1 PF %.2f below backtest 1.82 - marginal; watch closely." % pf)
    else:
        print("  \U0001f7e2 PF %.2f in line with backtest." % pf)

    if wr < 60:
        print("  \U0001f7e1 WR %.1f%% well below backtest ~70%% - dips may be reverting less than modeled (falling knives)." % wr)
    if wins and avg_w < BT["avg_w_pct"] * 0.7:
        print("  \U0001f7e1 avgW %.2f%% << backtest %.2f%% - likely SLIPPAGE / execution drag eroding the thin edge." % (avg_w, BT["avg_w_pct"]))
    if reasons.get("stop_loss", 0) > len(mr) * 0.4:
        print("  \U0001f7e1 >40%% exiting on stop (backtest exits mostly at the EMA20 target) - entries reverting less than modeled.")

    print("\n  Kill switch if the edge isn't real:")
    print("  cd /opt/Binance_Bot && sed -i 's/ENABLE_MEAN_REVERSION=true/ENABLE_MEAN_REVERSION=false/' .env && \\")
    print("    rm -f data/bot.lock && docker compose up -d --force-recreate")


if __name__ == "__main__":
    main()
