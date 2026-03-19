#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta

s = json.load(open('/root/zerovantclaw/data/grid_state.json'))

# 1. Inject asset_pnl into each grid
asset_pnl = s.get('asset_pnl', {})
for sym, g in s.get('grids', {}).items():
    if sym in asset_pnl:
        g['realized_pnl'] = asset_pnl[sym]

# 2. Total capital — ambil dari grid capitals, jangan hardcode
calc_total = sum(g.get('capital', 0) for g in s.get('grids', {}).values())
if calc_total > 0:
    s['total_capital'] = round(calc_total, 2)

# 3. Today snapshot — WIB = UTC+7
wib = timezone(timedelta(hours=7))
now_wib = datetime.now(wib)
today_wib = now_wib.strftime('%Y-%m-%d')

realized      = s.get('realized_pnl') or 0
day_start_pnl = s.get('daily_start_pnl') or 0
day_start_fills = s.get('daily_start_fills') or 0
total_fills   = s.get('total_fills') or 0

day_pnl   = round(float(realized) - float(day_start_pnl), 4)
day_fills = int(total_fills) - int(day_start_fills)

# Fee estimate for today
fs = s.get('fee_simulation', {})
fee_rate = float(fs.get('fee_rate') or 0.001)
# Estimate avg trade value from alltime data
total_fee_alltime = abs(float(fs.get('fee_impact') or 0))
total_fills_alltime = int(total_fills)
avg_trade_val = (total_fee_alltime / (fee_rate * 2 * total_fills_alltime)) if total_fills_alltime > 0 else 50
today_fee_est = day_fills * avg_trade_val * fee_rate * 2
today_net     = round(day_pnl - today_fee_est, 4)

s['today_snapshot'] = {
    "date":        today_wib,
    "pnl":         day_pnl,
    "fills":       day_fills,
    "cumulative":  round(float(realized), 4),
    "roi_pct":     round(day_pnl / max(s.get('total_capital', 500), 1) * 100, 3),
    "fee_est":     round(-today_fee_est, 4),
    "net_pnl":     today_net,
}

# 4. Clean daily_pnl_history — no live entries
history = s.get('daily_pnl_history', {})
for k in list(history.keys()):
    if history[k].get('live'):
        del history[k]
s['daily_pnl_history'] = history

# Inject grid_config dari state grids (bukan hardcode dari source)
grids = s.get('grids', {})
grid_config = {}
for sym in ['ETHUSDT','SOLUSDT','BNBUSDT','DOGEUSDT','XRPUSDT']:
    cap = float(grids.get(sym, {}).get('capital', 0))
    grid_config[sym] = {"capital": cap}
s["grid_config"] = grid_config
# Fix grid_capitals juga
s["grid_capitals"] = {sym: cfg["capital"] for sym, cfg in grid_config.items()}
# Fix total_capital
s["total_capital"] = sum(cfg["capital"] for cfg in grid_config.values() if cfg["capital"] > 0)

json.dump(s, open('/var/www/zerovantclaw/data/grid_state.json', 'w'), indent=2)
print(f"✅ today_snapshot: pnl={day_pnl} fills={day_fills} net={today_net}")
