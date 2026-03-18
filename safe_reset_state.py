#!/usr/bin/env python3
"""
Safe state reset — preserve semua historical data.
Hanya reset grids dan capital.
Usage: python3 safe_reset_state.py --capital 500
"""
import json, sys, os
from datetime import datetime, timezone

state_file = '/root/zerovantclaw/data/grid_state.json'

# Parse capital dari args
capital = 500.0
for i, arg in enumerate(sys.argv):
    if arg == '--capital' and i+1 < len(sys.argv):
        capital = float(sys.argv[i+1])

if os.path.exists(state_file):
    old = json.load(open(state_file))
else:
    old = {}

# Preserve semua historical data
new_state = {
    # === RESET ===
    "grids": {},
    "total_capital": capital,
    "start_capital": capital,
    "start_time": datetime.now(timezone.utc).isoformat(),
    "last_ai_check": None,
    "equity_history": [capital],
    "daily_start_pnl": old.get("realized_pnl", 0),
    "daily_start_fills": old.get("total_fills", 0),

    # === PRESERVE ===
    "fills_log":          old.get("fills_log", []),
    "total_fills":        old.get("total_fills", 0),
    "realized_pnl":       old.get("realized_pnl", 0),
    "fee_simulation":     old.get("fee_simulation", {}),
    "win_loss":           old.get("win_loss", {}),
    "asset_pnl":          old.get("asset_pnl", {}),
    "analytics":          old.get("analytics", {}),
    "daily_pnl_history":  old.get("daily_pnl_history", {}),
    "seen_trade_ids":     old.get("seen_trade_ids", {}),
    "grid_capitals": {
        "ETHUSDT": round(capital*0.70, 2),
        "BNBUSDT": round(capital*0.20, 2),
        "SOLUSDT": round(capital*0.10, 2),
        "DOGEUSDT": 0.0, "XRPUSDT": 0.0
    },
}

json.dump(new_state, open(state_file,'w'), indent=2, default=str)
print(f"Safe reset done: capital=${capital}")
print(f"Preserved: {len(new_state['fills_log'])} fills, net=${new_state['fee_simulation'].get('simulated_pnl',0):.2f}")
