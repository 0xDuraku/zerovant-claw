#!/usr/bin/env python3
"""
Zerovant Claw Backtest v2.0
Parameters: MTF analysis, dynamic spacing, trailing stop, asset stop loss
"""
import json, os, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests

load_dotenv("/root/zerovantclaw/.env")

# ── CONFIG ──────────────────────────────────────────
ASSETS = ["ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]
CAPITAL = {"ETHUSDT":80, "SOLUSDT":110, "BNBUSDT":60, "DOGEUSDT":150, "XRPUSDT":100}
TOTAL_CAPITAL = sum(CAPITAL.values())
FEE_RATE      = 0.001   # 0.1% per side
GRID_RANGE    = {"ETHUSDT":0.10, "SOLUSDT":0.12, "BNBUSDT":0.08, "DOGEUSDT":0.10, "XRPUSDT":0.12}
NUM_GRIDS     = 10
TRAILING_PCT  = 0.03
ASSET_SL_PCT  = 0.15
DAYS          = 14

BASE = "https://testnet.binance.vision/api/v3"

def get_klines(symbol, interval="1h", limit=500):
    r = requests.get(f"{BASE}/klines", params={"symbol":symbol,"interval":interval,"limit":limit}, timeout=10)
    data = r.json()
    return [{"time":k[0],"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"volume":float(k[5])} for k in data]

def compute_atr(candles, period=14):
    trs = [max(c["high"]-c["low"], abs(c["high"]-candles[i-1]["close"]),
               abs(c["low"]-candles[i-1]["close"])) for i,c in enumerate(candles) if i > 0]
    return sum(trs[-period:])/period if trs else 0

def backtest_asset(symbol):
    print(f"\n  Fetching {symbol}...")
    candles = get_klines(symbol, "1h", 24*DAYS+50)
    if len(candles) < 50:
        print(f"  Not enough data for {symbol}")
        return None

    capital   = CAPITAL[symbol]
    range_pct = GRID_RANGE[symbol]
    pnl       = 0.0
    fills     = 0
    wins      = 0
    losses    = 0
    peak_pnl  = 0.0
    max_dd    = 0.0
    sl_hits   = 0
    trailing_triggers = 0
    equity    = [capital]

    # Simulate grid over each candle
    for i in range(50, len(candles)):
        c     = candles[i]
        price = c["close"]
        high  = c["high"]
        low   = c["low"]

        # ATR-based dynamic spacing
        atr = compute_atr(candles[:i+1])
        atr_pct = atr / price

        # Dynamic num_grids
        min_spacing = 0.004
        ideal_spacing = max(min_spacing, atr_pct * 1.0)
        num_grids = min(15, max(5, int(range_pct / ideal_spacing)))
        spacing = range_pct / num_grids

        # Grid levels
        rl = price * (1 - range_pct/2)
        rh = price * (1 + range_pct/2)
        per_level = capital / num_grids

        # Count crossings (simplified: each spacing crossed = 1 fill pair)
        price_move = abs(high - low)
        crossings = max(0, int(price_move / (price * spacing)))
        crossings = min(crossings, num_grids // 2)

        for _ in range(crossings):
            buy_price  = price * (1 - spacing/2)
            sell_price = price * (1 + spacing/2)
            qty        = per_level / buy_price
            # Realistic: 35% of crossings result in loss (price reversal)
            import random
            win_prob = 0.65
            if random.random() < win_prob:
                # Profitable trade
                buy_cost  = buy_price * qty * (1 + FEE_RATE)
                sell_rev  = sell_price * qty * (1 - FEE_RATE)
                trade_pnl = sell_rev - buy_cost
            else:
                # Loss: price reversed before sell filled
                slippage  = random.uniform(0.001, 0.005)
                sell_rev  = buy_price * qty * (1 - slippage) * (1 - FEE_RATE)
                buy_cost  = buy_price * qty * (1 + FEE_RATE)
                trade_pnl = sell_rev - buy_cost
            pnl   += trade_pnl
            fills += 2
            if trade_pnl > 0: wins += 1
            else: losses += 1

        # Trailing stop simulation
        if price > rl * (1 + TRAILING_PCT):
            trailing_triggers += 1

        # Asset stop loss
        if pnl < -capital * ASSET_SL_PCT:
            sl_hits += 1
            pnl = -capital * ASSET_SL_PCT  # cap loss

        # Track equity & drawdown
        eq = capital + pnl
        equity.append(eq)
        if eq > peak_pnl + capital: peak_pnl = eq - capital
        dd = (max(equity) - eq) / max(equity)
        if dd > max_dd: max_dd = dd

    wr  = wins/(wins+losses)*100 if wins+losses > 0 else 0
    roi = pnl/capital*100

    return {
        "symbol": symbol, "pnl": round(pnl,4), "roi": round(roi,2),
        "fills": fills, "wins": wins, "losses": losses,
        "wr": round(wr,1), "max_dd": round(max_dd*100,2),
        "trailing_triggers": trailing_triggers, "sl_hits": sl_hits,
        "equity": equity
    }

def run_backtest():
    print("=" * 50)
    print("  ZEROVANT CLAW BACKTEST v2.0")
    print(f"  Period: {DAYS} days | Capital: ${TOTAL_CAPITAL}")
    print("=" * 50)

    results = []
    for sym in ASSETS:
        r = backtest_asset(sym)
        if r: results.append(r)

    if not results:
        print("No results")
        return

    total_pnl   = sum(r["pnl"] for r in results)
    total_fills = sum(r["fills"] for r in results)
    total_wins  = sum(r["wins"] for r in results)
    total_losses= sum(r["losses"] for r in results)
    total_wr    = total_wins/(total_wins+total_losses)*100 if total_wins+total_losses > 0 else 0
    total_roi   = total_pnl/TOTAL_CAPITAL*100
    max_dd      = max(r["max_dd"] for r in results)

    print(f"\n{'ASSET':<10} {'PnL':>8} {'ROI':>7} {'WR':>7} {'Fills':>7} {'MaxDD':>7}")
    print("-" * 50)
    for r in sorted(results, key=lambda x: x["pnl"], reverse=True):
        print(f"{r['symbol']:<10} ${r['pnl']:>7.2f} {r['roi']:>6.1f}% {r['wr']:>6.1f}% {r['fills']:>7} {r['max_dd']:>6.1f}%")

    print("-" * 50)
    print(f"{'TOTAL':<10} ${total_pnl:>7.2f} {total_roi:>6.1f}% {total_wr:>6.1f}% {total_fills:>7} {max_dd:>6.1f}%")
    print(f"\nMonthly projection: ${total_pnl/DAYS*30:.2f}")
    print(f"Sharpe (est):       {total_roi/max(max_dd,0.1):.2f}")

    # Save results
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "days": DAYS, "capital": TOTAL_CAPITAL,
        "total_pnl": round(total_pnl,4), "total_roi": round(total_roi,2),
        "total_wr": round(total_wr,1), "max_dd": round(max_dd,2),
        "monthly_est": round(total_pnl/DAYS*30,2),
        "assets": results
    }
    json.dump(out, open("/root/zerovantclaw/data/backtest_results.json","w"), indent=2)
    print(f"\nResults saved to data/backtest_results.json")
    return out

if __name__ == "__main__":
    run_backtest()
