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

# Fees are charged in BNB, so trades.json always records fees_usdt=0 and every
# pnl figure in it is GROSS. Measured from real Binance commissions 2026-07-22:
# ~0.00019 BNB per side on a ~$148 fill = 0.15% round trip (0.075%/side, the BNB
# discount rate). MR's gross edge is only ~0.3-0.6%, so fees are a third of it -
# reporting gross here would badly flatter the strategy. NOTE: if the BNB balance
# runs dry, Binance charges 0.10%/side in USDT instead -> raise this to 0.20.
FEE_PCT_ROUND_TRIP = 0.15


def _net(t):
    """Fee-adjusted P&L for one trade (trades.json pnl is gross - see above)."""
    gross = t.get("pnl_usdt", 0) or 0
    notional = t.get("size_quote") or 0
    return gross - notional * FEE_PCT_ROUND_TRIP / 100.0


def _pf(gw, gl):
    """Profit factor, or None when there is no loss to divide by (PF would be
    'inf', which reads as a great result off a tiny sample - it is not)."""
    return (gw / abs(gl)) if gl else None


def _fmt_pf(pf):
    return "n/a" if pf is None else "%.2f" % pf

# Date both strategies went live under CURRENT rules (2% stop + BTC daily gate +
# MR enabled). Trades before this are old-rule momentum and are NOT comparable.
HEAD_TO_HEAD_CUTOFF = "2026-07-02"
H2H_MIN = 15      # per-strategy trades before the head-to-head is worth reading


def _strat_stats(trades):
    n = len(trades)
    if n == 0:
        return None
    # Win/loss classified on NET (after-fee) P&L: a trade that made +$0.10 gross
    # but cost $0.22 in fees is a loss to the account, whatever is_win says.
    nets = [(t, _net(t)) for t in trades]
    wins = [v for _, v in nets if v > 0]
    losses = [v for _, v in nets if v <= 0]
    net = sum(v for _, v in nets)
    return {
        "n": n, "wr": 100.0 * len(wins) / n, "net": net,
        "pf": _pf(sum(wins), sum(losses)),
        "exp": net / n,   # expectancy $/trade - normalises for trade frequency
    }


def head_to_head(trades):
    """Momentum vs mean_reversion, both under current rules (since the cutoff)."""
    recent = [t for t in trades if (t.get("exit_time") or "") >= HEAD_TO_HEAD_CUTOFF]
    mom = _strat_stats([t for t in recent if t.get("strategy") != "mean_reversion"])
    mr = _strat_stats([t for t in recent if t.get("strategy") == "mean_reversion"])

    print("\n=== STRATEGY HEAD-TO-HEAD (both under current rules, since %s) ===" % HEAD_TO_HEAD_CUTOFF)
    print("  all figures NET of %.2f%% round-trip fees" % FEE_PCT_ROUND_TRIP)
    print("  %-15s %4s %6s %9s %6s %11s" % ("strategy", "n", "WR%", "net$", "PF", "exp$/trade"))
    for name, s in (("momentum", mom), ("mean_reversion", mr)):
        if s is None:
            print("  %-15s %4d %6s %9s %6s %11s" % (name, 0, "-", "-", "-", "-"))
        else:
            print("  %-15s %4d %6.1f %9.2f %6s %11.2f" % (
                name, s["n"], s["wr"], s["net"], _fmt_pf(s["pf"]), s["exp"]))

    print("  VERDICT:")
    if not mom and not mr:
        print("    No trades under current rules yet (both gated off while BTC < daily EMA50).")
        print("    Comparison begins once BTC reclaims its daily EMA50 and entries resume.")
        return
    if not (mom and mr):
        only = "momentum" if mom else "mean_reversion"
        print("    Only %s has traded so far - need both active for a fair comparison." % only)
        return
    lead_net = "momentum" if mom["net"] > mr["net"] else "mean_reversion"
    lead_exp = "momentum" if mom["exp"] > mr["exp"] else "mean_reversion"
    enough = mom["n"] >= H2H_MIN and mr["n"] >= H2H_MIN
    note = "" if enough else "  (<%d trades each - NOT conclusive yet)" % H2H_MIN
    print("    Total $ (grows the account): %s ahead." % lead_net)
    print("    Per-trade edge (frequency-normalised): %s ahead.%s" % (lead_exp, note))
    if lead_net != lead_exp:
        print("    Split verdict - one wins on volume, the other on edge quality. Watch both.")


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
        head_to_head(trades)
        return

    # Backtest avgW/avgL were quoted net of a 0.20% round-trip fee, so subtract
    # the real fee here too or the comparison is rigged in the strategy's favour.
    pcts = [((t.get("pnl_percent", 0) or 0) - FEE_PCT_ROUND_TRIP) for t in mr]
    avg_w = sum(p for p in pcts if p > 0) / max(1, len([p for p in pcts if p > 0]))
    avg_l = sum(p for p in pcts if p <= 0) / max(1, len([p for p in pcts if p <= 0]))
    s = _strat_stats(mr)
    gross = sum(t.get("pnl_usdt", 0) or 0 for t in mr)
    fees = gross - s["net"]
    pf = s["pf"]

    reasons = {}
    for t in mr:
        r = t.get("exit_reason", "?")
        reasons[r] = reasons.get(r, 0) + 1

    print("\nGROSS:     net=$%.2f   (this is what trades.json stores - fees are paid" % gross)
    print("           in BNB so fees_usdt is always 0 and every raw figure is gross)")
    print("FEES:      -$%.2f  (%.2f%% round trip x %d trades)" % (fees, FEE_PCT_ROUND_TRIP, len(mr)))
    print("\nLIVE:      n=%d  WR=%.1f%%  PF=%s  net=$%.2f  avgW=%.2f%%  avgL=%.2f%%" % (
        s["n"], s["wr"], _fmt_pf(pf), s["net"], avg_w, avg_l))
    print("BACKTEST:  WR=%.1f%%  PF=%.2f  ---     ---       avgW=%.2f%%  avgL=%.2f%%" % (
        BT["wr"], BT["pf"], BT["avg_w_pct"], BT["avg_l_pct"]))
    print("exit reasons: %s" % reasons)

    print("\nVERDICT:")
    if len(mr) < MIN_TRADES:
        print("  ⏳ Only %d/%d trades - NOT yet statistically meaningful; treat below as directional." % (
            len(mr), MIN_TRADES))

    if pf is None:
        print("  \U0001f7e1 PF undefined (no losing trade yet) - too early to read as a win.")
    elif pf < 1.0:
        print("  \U0001f534 PF %.2f < 1.0 - LOSING. If it holds over %d+ trades, DISABLE (see kill switch below)." % (pf, MIN_TRADES))
    elif pf < 1.3:
        print("  \U0001f7e1 PF %.2f below backtest 1.82 - marginal; watch closely." % pf)
    else:
        print("  \U0001f7e2 PF %.2f in line with backtest." % pf)

    if s["wr"] < 60:
        print("  \U0001f7e1 WR %.1f%% (after fees) below backtest ~70%% - dips may be reverting less than modeled." % s["wr"])
    if avg_w < BT["avg_w_pct"] * 0.7:
        print("  \U0001f7e1 avgW %.2f%% << backtest %.2f%% - winners are being cut short." % (avg_w, BT["avg_w_pct"]))
        print("     Known structural cause: the live exit compares the CURRENT TICK to EMA20 and")
        print("     fires the instant price touches it, while the backtest required a 15m CLOSE")
        print("     >= EMA20 (a higher exit). Live entry/exit also read the in-progress 15m bar")
        print("     (df.iloc[-1]), not the last closed one. Both clip winners vs the backtest.")
    if reasons.get("stop_loss", 0) > len(mr) * 0.4:
        print("  \U0001f7e1 >40%% exiting on stop (backtest exits mostly at the EMA20 target) - entries reverting less than modeled.")

    print("\n  Kill switch if the edge isn't real:")
    print("  cd /opt/Binance_Bot && sed -i 's/ENABLE_MEAN_REVERSION=true/ENABLE_MEAN_REVERSION=false/' .env && \\")
    print("    rm -f data/bot.lock && docker compose up -d --force-recreate")

    head_to_head(trades)


if __name__ == "__main__":
    main()
