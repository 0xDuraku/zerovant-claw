import os, time, json, logging, hmac, hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import requests

# ── TELEGRAM ────────────────────────────────────────────
def tg(msg: str):
    """Send Telegram notification — silent fail"""
    token   = os.environ.get("TELEGRAM_TOKEN","")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID","")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=8
        )
    except:
        pass

# ── MILESTONE ALERTS ────────────────────────────────────
MILESTONES_NET = [5, 10, 20, 30, 50, 75, 100, 150, 200]  # USD net profit
MILESTONES_WR  = [70, 75, 80, 85, 90]                     # Win rate %
MILESTONES_FILLS = [500, 1000, 2000, 5000]                 # Total fills

def check_milestones(state):
    """Cek dan kirim alert untuk milestone yang baru tercapai"""
    reached = state.get("milestones_reached", [])
    changed = False
    fs      = state.get("fee_simulation", {})
    net_pnl = float(fs.get("simulated_pnl", 0))
    wl      = state.get("win_loss", {})
    wins    = wl.get("wins", 0)
    losses  = wl.get("losses", 0)
    wr      = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    fills   = state.get("total_fills", 0)
    capital = 500
    NL = chr(10)
    for m in MILESTONES_NET:
        key = f"net_{m}"
        if net_pnl >= m and key not in reached:
            reached.append(key)
            roi = m / capital * 100
            msg = f"🏆 MILESTONE +${m} NET{NL}💰 Net PnL: +${net_pnl:.2f}{NL}📈 ROI: +{roi:.1f}%{NL}#zerovant #milestone"
            tg(msg)
            changed = True
    for m in MILESTONES_WR:
        key = f"wr_{m}"
        if wr >= m and key not in reached:
            reached.append(key)
            msg = f"🎯 WIN RATE {m}%{NL}📊 Rate: {wr:.1f}% ({wins}W/{losses}L){NL}#zerovant #winrate"
            tg(msg)
            changed = True
    for m in MILESTONES_FILLS:
        key = f"fills_{m}"
        if fills >= m and key not in reached:
            reached.append(key)
            msg = f"⚡ FILLS {m:,}{NL}🔄 Total: {fills:,}{NL}#zerovant #fills"
            tg(msg)
            changed = True
    history = state.get("daily_pnl_history", {})
    if history:
        best_day  = max((float(d.get("pnl",0)) for d in history.values()), default=0)
        snap      = state.get("today_snapshot", {}) or {}
        today_pnl = float(snap.get("pnl", 0))
        key = f"best_day_{int(best_day*100)}"
        if today_pnl > best_day and today_pnl > 5 and key not in reached:
            reached.append(key)
            msg = f"📅 NEW DAILY RECORD{NL}🌟 Today: +${today_pnl:.4f}{NL}📈 Prev: +${best_day:.4f}{NL}#zerovant #record"
            tg(msg)
            changed = True
    if changed:
        state["milestones_reached"] = reached

def send_daily_report(state):
    """Daily report jam 07:00 WIB — auto pin"""
    from datetime import datetime, timezone, timedelta
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib)

    fs      = state.get("fee_simulation", {})
    wl      = state.get("win_loss", {})
    wins    = wl.get("wins", 0)
    losses  = wl.get("losses", 0)
    wr      = wins/(wins+losses)*100 if (wins+losses) > 0 else 0
    gross   = float(fs.get("gross_pnl", 0))
    net     = float(fs.get("simulated_pnl", 0))
    fills   = state.get("total_fills", 0)
    sharpe  = float(state.get("sharpe_ratio", 0))
    capital = 500
    balance = capital + net

    # Today PnL
    snap      = state.get("today_snapshot", {}) or {}
    today_pnl = float(snap.get("pnl", 0))
    today_net = float(snap.get("net_pnl", 0))
    asset_lines = ""
    for sym, pnl in state.get("asset_pnl", {}).items():
        sym_short = sym.replace("USDT","")
        icon = "+" if float(pnl) >= 0 else "-"
        asset_lines += f"  [{icon}] {sym_short}: ${float(pnl):+.4f}\n"
    msg = (
        f"\U0001f4ca <b>ZEROVANT CLAW - DAILY REPORT</b>\n"
        f"\U0001f4c5 {now.strftime('%d %B %Y')} | {now.strftime('%H:%M')} WIB\n"
        f"\U0001f4b0 <b>Balance: ${balance:.2f}</b> NET est\n"
        f"\U0001f4c8 Today: ${today_pnl:+.4f} gross | ${today_net:+.4f} net\n"
        f"\U0001f4ca All-time Net: ${net:+.4f} ({net/capital*100:+.2f}%)\n"
        f"\U0001f3af Win Rate: {wr:.1f}% ({wins}W/{losses}L)\n"
        f"\U0001f4ca Sharpe: {sharpe:.2f}\n"
        f"\u26a1 Fills: {fills:,}\n"
        f"\U0001f4bc Per Asset:\n{asset_lines}"
        f"#zerovant #daily"
    )

    token   = os.environ.get("TELEGRAM_TOKEN","")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID","")
    if not token or not chat_id: return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=8
        )
        msg_id = r.json().get("result",{}).get("message_id")
        if msg_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/pinChatMessage",
                json={"chat_id": chat_id, "message_id": msg_id, "disable_notification": True},
                timeout=8
            )
            log.info("  📌 Daily report sent & pinned")
    except Exception as e:
        log.warning(f"  Daily report error: {e}")

def check_daily_report(state):
    """Cek apakah sudah waktunya kirim daily report (07:00 WIB)"""
    from datetime import datetime, timezone, timedelta
    wib      = timezone(timedelta(hours=7))
    now      = datetime.now(wib)
    today    = now.strftime("%Y-%m-%d")
    last_rpt = state.get("last_daily_report","")
    # Kirim antara 07:00-07:15 WIB
    if now.hour == 7 and now.minute < 15 and last_rpt != today:
        send_daily_report(state)
        state["last_daily_report"] = today

def apply_compound(state):
    """Compound 50% daily profit ke capital setiap hari saat reset"""
    realized   = float(state.get("realized_pnl", 0))
    day_start  = float(state.get("daily_start_pnl", realized))
    daily_pnl  = realized - day_start
    net_daily  = round(daily_pnl * 0.85, 4)
    if net_daily <= 0:
        return
    total_cap = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
    compound_amt = round(net_daily * COMPOUND_RATE, 2)
    if compound_amt < 0.50:
        return

    # Distribusi proporsional ke asset yang ACTIVE saja
    active_syms = [sym for sym, g in state.get("grids", {}).items()
                   if g.get("active") and GRID_CONFIG.get(sym, {}).get("capital", 0) > 0]
    active_cap = sum(GRID_CONFIG[s]["capital"] for s in active_syms if s in GRID_CONFIG)
    if active_cap <= 0:
        return
    for sym in active_syms:
        if sym not in GRID_CONFIG: continue
        cfg = GRID_CONFIG[sym]
        share = cfg["capital"] / active_cap
        addition = round(compound_amt * share, 2)
        cfg["capital"] = round(cfg["capital"] + addition, 2)

    new_total = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
    state["total_capital"] = new_total
    state["grid_capitals"] = {sym: cfg["capital"] for sym, cfg in GRID_CONFIG.items()}
    # Sync ke state["grids"] agar persistent setelah restart
    for sym, cfg in GRID_CONFIG.items():
        if sym in state.get("grids", {}):
            state["grids"][sym]["capital"] = cfg["capital"]
    state["last_compound"] = {
        "amount": compound_amt,
        "net_pnl": net_daily,
        "new_total": new_total,
        "capitals": {sym: cfg["capital"] for sym, cfg in GRID_CONFIG.items()}
    }
    log.info(f"  🔥 COMPOUND: +${compound_amt:.2f} → total capital ${new_total:.2f}")
    tg("\U0001f4b0 <b>COMPOUND EXECUTED</b>\n"
       "+ $" + str(compound_amt) + " added to capital\n"
       "New total: $" + str(round(new_total, 2)) + "\n"
       "From daily profit: $" + str(round(net_daily, 2)) + "\n"
       "#zerovant #compound")

# ── CONFIG ──────────────────────────────────────────────
TESTNET_BASE  = "https://testnet.binance.vision/api/v3"
MAINNET_BASE  = "https://api.binance.com/api/v3"
MAINNET_MODE  = os.environ.get("BINANCE_MODE", "testnet").lower() == "mainnet"
BASE_URL      = MAINNET_BASE if MAINNET_MODE else TESTNET_BASE

if MAINNET_MODE:
    API_KEY    = os.environ.get("BINANCE_MAINNET_API_KEY", "")
    API_SECRET = os.environ.get("BINANCE_MAINNET_SECRET", "")
else:
    API_KEY    = os.environ.get("BINANCE_TESTNET_API_KEY", "")
    API_SECRET = os.environ.get("BINANCE_TESTNET_SECRET", "")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VENICE_KEY    = os.environ.get("VENICE_API_KEY", "")
USE_VENICE    = bool(VENICE_KEY)  # Auto-switch ke Venice jika key tersedia

ASSETS = ["ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]
# ── RISK MANAGEMENT ────────────────────────────────────
MAX_DAILY_LOSS_PCT  = 0.05   # Stop semua grid kalau loss >5% modal hari ini
ASSET_STOP_LOSS_PCT = 0.15   # Pause asset kalau rugi >15% dari capital asset tsb
ASSET_STOP_COOLDOWN = 4      # Jam cooldown sebelum asset bisa aktif lagi
RANGE_BREACH_PCT    = 0.15   # Cancel grid kalau harga keluar range >15%
MAX_DRAWDOWN_PCT    = 0.10   # Emergency stop kalau drawdown >10% dari peak
DAILY_PROFIT_TARGET = 0.02   # Optional: lock profit kalau sudah +2% hari ini

# Flash crash / news protection
FLASH_CRASH_PCT     = 0.05   # Cancel semua kalau 1 candle bergerak >5%
TRAILING_STOP_PCT   = 0.03   # Geser grid ke atas kalau harga naik >3% dari range_low
TRAILING_LOCK_PCT   = 0.015  # Lock profit — range_low naik mengikuti harga - 1.5%
VOLUME_SPIKE_MULT   = 5.0    # Volume spike = volume > 5x rata-rata 20 candle
BB_EXPLOSION_MULT   = 2.5    # BB width explode = >2.5x dari BB sebelumnya
COOLDOWN_MINUTES    = 30     # Pause trading setelah extreme event

# Optimized for $500 real capital — weighted by backtest ROI
# DOGE/XRP/SOL overweighted (highest ROI), BTC underweighted (lowest ROI per $)
# $500 real capital — BTC removed (min notional too high for small capital)
# Reallocated BTC+BNB share to DOGE/XRP/SOL (higher ROI anyway)
GRID_CONFIG_TESTNET = {
    "ETHUSDT":  {"capital": 350,  "num_grids": 10, "range_pct": 0.10},
    "SOLUSDT":  {"capital": 50, "num_grids": 10, "range_pct": 0.12},
    "BNBUSDT":  {"capital": 100,  "num_grids": 10, "range_pct": 0.08},
    "DOGEUSDT": {"capital": 0, "num_grids": 10, "range_pct": 0.10},
    "XRPUSDT":  {"capital": 0, "num_grids": 10, "range_pct": 0.12},
}
GRID_CONFIG_MAINNET = {
    "ETHUSDT":  {"capital": 350,  "num_grids": 10, "range_pct": 0.10},
    "SOLUSDT":  {"capital": 50,  "num_grids": 10, "range_pct": 0.12},
    "BNBUSDT":  {"capital": 100,  "num_grids": 10, "range_pct": 0.08},
    "DOGEUSDT": {"capital": 0,  "num_grids": 10, "range_pct": 0.10},
    "XRPUSDT":  {"capital": 0,  "num_grids": 10, "range_pct": 0.12},
}
GRID_CONFIG = GRID_CONFIG_MAINNET if MAINNET_MODE else GRID_CONFIG_TESTNET
# Total: $500 | BTC removed (min order $5, $30/10grids=$3 too small)
# Expected monthly: ~$55/month = 11% monthly ROI
CYCLE_MINUTES  = 15
AI_REBALANCE_H = 2
COMPOUND_RATE  = 0.5
DATA_FILE      = "data/grid_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("grid_bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def sign(params):
    query = urlencode(params)
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params

def api_get(endpoint, params={}, auth=False):
    if auth:
        params["timestamp"] = int(time.time() * 1000)
        params = sign(params)
    resp = requests.get(f"{BASE_URL}{endpoint}", params=params,
                        headers={"X-MBX-APIKEY": API_KEY}, timeout=10)
    resp.raise_for_status()
    return resp.json()

def api_post(endpoint, params):
    params["timestamp"] = int(time.time() * 1000)
    params = sign(params)
    resp = requests.post(f"{BASE_URL}{endpoint}", params=params,
                         headers={"X-MBX-APIKEY": API_KEY}, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_price(symbol):
    return float(api_get("/ticker/price", {"symbol": symbol})["price"])

def get_klines(symbol, interval="15m", limit=100):
    data = api_get("/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return [{"open":float(c[1]),"high":float(c[2]),"low":float(c[3]),"close":float(c[4]),"volume":float(c[5])} for c in data]

def cancel_open_orders(symbol):
    try:
        orders = api_get("/openOrders", {"symbol": symbol}, auth=True)
        if not orders:
            return
        for o in orders:
            params = {"symbol": symbol, "orderId": o["orderId"],
                      "timestamp": int(time.time() * 1000)}
            params = sign(params)
            requests.delete(f"{BASE_URL}/order", params=params,
                           headers={"X-MBX-APIKEY": API_KEY}, timeout=10)
        log.info(f"  Cancelled {len(orders)} orders: {symbol}")
    except Exception as e:
        log.warning(f"  Cancel error {symbol}: {e}")

def place_limit_order(symbol, side, price, qty):
    # price precision per asset
    price_prec = {"BTCUSDT":2,"ETHUSDT":2,"SOLUSDT":2,"BNBUSDT":2,"DOGEUSDT":5,"XRPUSDT":4}.get(symbol,2)
    qty_prec = {"BTCUSDT":5,"ETHUSDT":4,"SOLUSDT":3,"BNBUSDT":3,"DOGEUSDT":0,"XRPUSDT":1}.get(symbol,2)
    pd, qd = price_prec, qty_prec
    return api_post("/order", {
        "symbol": symbol, "side": side, "type": "LIMIT",
        "timeInForce": "GTC",
        "price": f"{price:.{pd}f}",
        "quantity": f"{qty:.{qd}f}",
    })

def compute_atr(candles, period=14):
    trs = [max(c["high"]-c["low"], abs(c["high"]-candles[i-1]["close"]),
               abs(c["low"]-candles[i-1]["close"])) for i, c in enumerate(candles) if i > 0]
    return sum(trs[-period:]) / period if trs else 0

def compute_bb_width(candles, period=20):
    closes = [c["close"] for c in candles[-period:]]
    mean = sum(closes) / len(closes)
    std  = (sum((c-mean)**2 for c in closes) / len(closes)) ** 0.5
    return round((std * 2) / mean, 4)

def market_analysis(symbol):
    # 15m — primary timeframe (entry/exit precision)
    c15  = get_klines(symbol, "15m", 100)
    # 1h  — medium timeframe (trend confirmation)
    c1h  = get_klines(symbol, "1h", 50)
    # 4h  — macro timeframe (major trend direction)
    c4h  = get_klines(symbol, "4h", 30)

    price   = c15[-1]["close"]
    atr     = compute_atr(c15)
    bb_w    = compute_bb_width(c15)

    # 15m trend
    ema20   = sum(c["close"] for c in c15[-20:]) / 20
    ema50   = sum(c["close"] for c in c15[-50:]) / 50
    trend15 = "UP" if ema20 > ema50 else "DOWN"

    # 1h trend
    ema20_1h = sum(c["close"] for c in c1h[-20:]) / 20
    ema50_1h = sum(c["close"] for c in c1h[-min(50,len(c1h)):]) / min(50,len(c1h))
    trend1h  = "UP" if ema20_1h > ema50_1h else "DOWN"

    # 4h trend (macro)
    ema10_4h = sum(c["close"] for c in c4h[-10:]) / 10
    ema20_4h = sum(c["close"] for c in c4h[-20:]) / 20
    trend4h  = "UP" if ema10_4h > ema20_4h else "DOWN"

    # Confluence — berapa timeframe setuju
    up_count = [trend15, trend1h, trend4h].count("UP")
    if up_count >= 2:
        trend_confluent = "UP"
    elif up_count <= 1:
        trend_confluent = "DOWN"
    else:
        trend_confluent = "NEUTRAL"

    # Volatility dari 1h BB untuk filter noise
    bb_w_1h = compute_bb_width(c1h)
    vol     = "HIGH" if bb_w > 0.04 else ("MEDIUM" if bb_w > 0.02 else "LOW")

    return {
        "symbol": symbol, "price": price,
        "atr": round(atr,2), "atr_pct": round(atr/price,4),
        "bb_width": bb_w, "bb_width_1h": bb_w_1h,
        "trend": trend_confluent,
        "trend15": trend15, "trend1h": trend1h, "trend4h": trend4h,
        "up_count": up_count,
        "vol_regime": vol,
        "ema20": round(ema20,2), "ema50": round(ema50,2),
        "ema20_1h": round(ema20_1h,2), "ema20_4h": round(ema20_4h,2)
    }

def call_venice_ai(prompt_text):
    """Call Venice AI — OpenAI compatible, no data retention"""
    import openai as openai_lib
    client = openai_lib.OpenAI(
        api_key=VENICE_KEY,
        base_url="https://api.venice.ai/api/v1"
    )
    resp = client.chat.completions.create(
        model="mistral-31-24b",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=1500,
        temperature=0.2,
    )
    return resp.choices[0].message.content

def call_anthropic_ai(prompt_text):
    """Call Anthropic Claude — fallback"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt_text}]
    )
    return msg.content[0].text

def call_ai(prompt_text):
    """Auto-select Venice (cheap) atau Anthropic (fallback)"""
    if USE_VENICE and VENICE_KEY:
        try:
            result = call_venice_ai(prompt_text)
            log.info("  🔥 Venice AI used")
            return result
        except Exception as e:
            log.warning(f"  Venice failed: {e} — fallback to Anthropic")
    return call_anthropic_ai(prompt_text)

def ai_grid_decision(analyses, current_grids):
    if not ANTHROPIC_KEY:
        return rule_based_grid_params(analyses, _current_state)
    # Build performance context untuk auto-tune
    analytics = (_current_state or {}).get("analytics", {})
    asset_pnl = (_current_state or {}).get("asset_pnl", {})
    perf_lines = []
    for sym in ASSETS:
        a   = analytics.get(sym, {})
        pnl = asset_pnl.get(sym, 0)
        g   = current_grids.get(sym, {})
        wr  = a.get("wr", 0)
        pf  = a.get("profit_factor", 0)
        trades = a.get("total_trades", 0)
        g_rh = float(g.get("range_high") or 0)
        g_rl = float(g.get("range_low") or 0)
        g_ng = float(g.get("num_grids") or 1)
        g_pr = float(g.get("current_price") or 1)
        spacing_pct = ((g_rh - g_rl) / g_ng / g_pr * 100) if g_rh > g_rl else 0
        perf_lines.append(f"  {sym}: WR={wr}% PF={pf} trades={trades} pnl=${pnl:+.2f} spacing={spacing_pct:.2f}%")

    prompt = f"""You are a grid trading AI with live performance data. Auto-tune grid parameters.

MARKET CONDITIONS (Multi-Timeframe):
{json.dumps(analyses, indent=2)}

LIVE PERFORMANCE DATA:
{chr(10).join(perf_lines)}

AUTO-TUNE RULES:
1. WR < 50% → widen range by 20%, reduce num_grids
2. WR > 75% → tighten range by 10%, increase num_grids
3. PF < 1.0 → CANCEL until market improves
4. spacing < 0.4% → MUST expand range or reduce grids
5. All 3 TF same direction DOWN → reduce exposure or CANCEL
6. HIGH vol → range * 1.3, fewer grids | LOW vol → range * 0.85, more grids

Respond ONLY in JSON (no markdown):
{{
  "ETHUSDT": {{"action":"REBALANCE","range_low":1900,"range_high":2100,"num_grids":12,"confidence":0.85,"reason":"WR 80% tighten range"}},
  "SOLUSDT": {{"action":"KEEP","range_low":0,"range_high":0,"num_grids":0,"confidence":0.60,"reason":"params optimal"}}
}}
confidence: 0.0-1.0. Actions: REBALANCE, KEEP, CANCEL."""
    try:
        raw = call_ai(prompt)
        text = raw.strip().strip("```json").strip("```").strip()
        decision = json.loads(text)
        log.info("  AI decision received")
        return decision
    except Exception as e:
        log.error(f"  AI error: {e} - fallback to rule-based")
        return rule_based_grid_params(analyses, _current_state)
def rule_based_grid_params(analyses, state=None):
    result = {}
    for a in analyses:
        symbol, price, atr_pct = a["symbol"], a["price"], a["atr_pct"]
        vol, trend = a["vol_regime"], a["trend"]
        ema_diff = abs(a["ema20"] - a["ema50"]) / price
        if ema_diff > 0.03:
            result[symbol] = {"action":"CANCEL","range_low":0,"range_high":0,"num_grids":0,
                              "reason":f"Strong trend ({trend}), EMA diff {ema_diff:.2%}"}
            continue
        # Use backtest-optimized config per asset
        cfg = GRID_CONFIG.get(symbol, {})
        target_range = cfg.get("range_pct", 0.10)

        # Dynamic width based on volatility
        if vol == "HIGH":
            range_pct = min(target_range * 1.3, max(target_range, atr_pct * 2.0))
        elif vol == "MEDIUM":
            range_pct = target_range
        else:
            range_pct = min(target_range * 0.85, max(target_range * 0.7, atr_pct * 1.5))

        # Dynamic grid spacing — spacing harus min 0.4% untuk cover fee
        # Lebih banyak grid saat volatility tinggi (lebih banyak crossing)
        # Lebih sedikit grid saat volatility rendah (hindari terlalu rapat)
        min_spacing = 0.004  # 0.4% minimum
        max_spacing = 0.025  # 2.5% maximum
        if vol == "HIGH":
            # Volatility tinggi — spacing lebih lebar, lebih banyak grid
            ideal_spacing = max(min_spacing, atr_pct * 0.8)
            num_grids = min(20, max(8, int(range_pct / ideal_spacing)))
        elif vol == "MEDIUM":
            ideal_spacing = max(min_spacing, atr_pct * 1.0)
            num_grids = min(15, max(6, int(range_pct / ideal_spacing)))
        else:
            # Volatility rendah — spacing lebih ketat, lebih sedikit grid
            ideal_spacing = max(min_spacing, atr_pct * 1.2)
            num_grids = min(12, max(5, int(range_pct / ideal_spacing)))

        # Clamp spacing agar tidak terlalu kecil atau besar
        actual_spacing = range_pct / num_grids
        if actual_spacing < min_spacing:
            num_grids = max(5, int(range_pct / min_spacing))
        elif actual_spacing > max_spacing:
            num_grids = max(5, int(range_pct / max_spacing))

        log.info(f"  &#9881; {symbol} dynamic grid: {num_grids} grids, spacing={range_pct/num_grids:.2%}, vol={vol}")
        # Asymmetric grid — bias toward trend
        if trend == "DOWN":
            buy_side  = range_pct * 0.62  # more room below — catch bounces
            sell_side = range_pct * 0.38
        elif trend == "UP":
            buy_side  = range_pct * 0.38
            sell_side = range_pct * 0.62  # more room above — ride momentum
        else:
            buy_side  = range_pct * 0.50
            sell_side = range_pct * 0.50
        # Trailing grid — blend current price with previous range center
        grids_state = (state or {}).get("grids", {})
        prev_low  = grids_state.get(symbol, {}).get("range_low") or price
        prev_high = grids_state.get(symbol, {}).get("range_high") or price
        prev_center = (float(prev_low) + float(prev_high)) / 2
        # 80% current price, 20% previous center — smooth trailing
        center = price * 0.85 + prev_center * 0.15
        # Precision berdasarkan harga
        if price < 0.001:  dec = 7
        elif price < 0.01: dec = 6
        elif price < 0.1:  dec = 5
        elif price < 1:    dec = 4
        elif price < 10:   dec = 3
        else:              dec = 2
        rl = round(center * (1 - buy_side),  dec)
        rh = round(center * (1 + sell_side), dec)
        # Sanity check — range must be > 0
        if rl <= 0 or rh <= rl:
            rl = round(price * (1 - range_pct/2), dec)
            rh = round(price * (1 + range_pct/2), dec)
        result[symbol] = {
            "action": "REBALANCE",
            "range_low":  rl,
            "range_high": rh,
            "num_grids": num_grids,
            "reason": f"{vol} vol, {trend} trend, ATR={atr_pct:.2%}"
        }
    return result

def compute_analytics(state):
    """Compute per-asset performance analytics dari fills_log"""
    fills = state.get("fills_log", [])
    analytics = {}
    for sym in ASSETS:
        sells = [f for f in fills if f.get("symbol")==sym and f.get("side")=="SELL" and f.get("pnl") is not None]
        buys  = [f for f in fills if f.get("symbol")==sym and f.get("side")=="BUY"]
        if not sells:
            analytics[sym] = {"wins":0,"losses":0,"wr":0,"avg_win":0,"avg_loss":0,"best":0,"worst":0,"avg_pnl":0,"total_trades":0}
            continue
        wins   = [f for f in sells if float(f.get("pnl",0)) > 0]
        losses = [f for f in sells if float(f.get("pnl",0)) <= 0]
        pnls   = [float(f.get("pnl",0)) for f in sells]
        analytics[sym] = {
            "wins":        len(wins),
            "losses":      len(losses),
            "wr":          round(len(wins)/len(sells)*100, 1),
            "avg_win":     round(sum(float(f["pnl"]) for f in wins)/len(wins), 4) if wins else 0,
            "avg_loss":    round(sum(float(f["pnl"]) for f in losses)/len(losses), 4) if losses else 0,
            "best":        round(max(pnls), 4),
            "worst":       round(min(pnls), 4),
            "avg_pnl":     round(sum(pnls)/len(pnls), 4),
            "total_trades":len(sells),
            "total_buys":  len(buys),
            "profit_factor": round(abs(sum(float(f["pnl"]) for f in wins) / sum(float(f["pnl"]) for f in losses)), 2) if losses and sum(float(f["pnl"]) for f in losses) != 0 else 99,
        }
    state["analytics"] = analytics
    return analytics

def rebalance_capital(state):
    """Rebalance capital allocation based on performance — run daily"""
    asset_pnl = state.get("asset_pnl", {})
    if not asset_pnl or len(asset_pnl) < 2: return
    # Gunakan total_capital dari state, bukan GRID_CONFIG (bisa tidak sync)
    total_cap = float(state.get("total_capital", 0))
    if total_cap <= 0 or total_cap > 10000:
        log.warning(f"  rebalance_capital: invalid total_cap={total_cap}, skip")
        return
    # Sync GRID_CONFIG dari state dulu
    for sym, g in state.get("grids", {}).items():
        if sym in GRID_CONFIG:
            GRID_CONFIG[sym]["capital"] = float(g.get("capital", 0))

    # Hitung score per asset: PnL + win rate
    fills_log = state.get("fills_log", [])
    scores = {}
    for sym in GRID_CONFIG:
        pnl   = asset_pnl.get(sym, 0)
        sells = [f for f in fills_log if f.get("symbol")==sym and f.get("side")=="SELL" and f.get("pnl") is not None]
        wins  = sum(1 for f in sells if float(f.get("pnl",0)) > 0)
        wr    = wins / len(sells) if sells else 0.5
        # Score = normalized PnL + win rate bonus
        scores[sym] = max(0.1, pnl * 0.7 + wr * 0.3)

    total_score = sum(scores.values())
    if total_score <= 0: return

    changes = []
    for sym, cfg in GRID_CONFIG.items():
        share   = scores[sym] / total_score
        # Clamp allocation: min 50% base, max 150% base
        base    = total_cap / len(GRID_CONFIG)
        new_cap = round(max(base * 0.5, min(base * 1.5, total_cap * share)), 0)
        old_cap = cfg["capital"]
        if abs(new_cap - old_cap) >= 5:  # only update if change >=$5
            log.info(f"  &#128200; Capital realloc {sym}: ${old_cap} → ${new_cap} (score={scores[sym]:.3f})")
            cfg["capital"] = new_cap
            changes.append(f"{sym.replace('USDT','')}: ${old_cap:.0f}→${new_cap:.0f}")

    if changes:
        state["last_rebalance_capital"] = datetime.now(timezone.utc).isoformat()
        tg(f"&#9878; <b>CAPITAL REBALANCE</b>\n"
           f"Based on performance scores:\n" +
           "\n".join(changes) +
           f"\nTotal: ${total_cap:.0f}")

def place_grid(symbol, range_low, range_high, num_grids, capital, current_price):
    spacing = (range_high - range_low) / num_grids
    # Enforce minimum spacing = 0.4% of price (2x fee rate untuk net profit)
    min_spacing = current_price * 0.004
    if spacing < min_spacing:
        # Expand range atau kurangi num_grids
        spacing = min_spacing
        range_high = range_low + spacing * num_grids
        log.info(f"  ⚠️ {symbol}: spacing too small, expanded range to {range_low:.4f}-{range_high:.4f}")
    per_level = capital / num_grids
    placed = 0
    for i in range(num_grids + 1):
        price = range_low + i * spacing
        qty   = per_level / price
        side  = "BUY" if price < current_price else "SELL" if price > current_price else None
        if not side: continue
        try:
            place_limit_order(symbol, side, price, qty)
            placed += 1
        except Exception as e:
            log.warning(f"  Order fail {side}@{price:.2f}: {e}")
    log.info(f"  ✅ {placed}/{num_grids} orders placed | {symbol} | range:{range_low:.0f}-{range_high:.0f}")
    return placed

def load_state():
    try:
        s = json.load(open(DATA_FILE))
        if s.get("total_fills", 0) > 0 or s.get("realized_pnl", 0) > 0:
            # Simpan local backup
            import os
            backup_dir = "/tmp/zerovant-state-backup"
            os.makedirs(backup_dir, exist_ok=True)
            json.dump(s, open(f"{backup_dir}/grid_state.json","w"), indent=2, default=str)
            return s
        # State kosong — coba restore dari local backup
        import os, subprocess
        backup_dir = "/tmp/zerovant-state-backup"
        if os.path.exists(f"{backup_dir}/grid_state.json"):
            s2 = json.load(open(f"{backup_dir}/grid_state.json"))
            if s2.get("total_fills", 0) > 0:
                log.warning(f"  ⚠️ Empty state! Restoring {s2.get('total_fills')} fills from /tmp backup")
                json.dump(s2, open(DATA_FILE,"w"), indent=2, default=str)
                return s2
        # Fallback: restore dari git data-backup branch
        try:
            r = subprocess.run(
                ["git","-C","/root/zerovant-backup","show","HEAD:data/grid_state.json"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                s3 = json.loads(r.stdout)
                if s3.get("total_fills", 0) > 0:
                    log.warning(f"  ⚠️ Restoring {s3.get('total_fills')} fills from git backup!")
                    json.dump(s3, open(DATA_FILE,"w"), indent=2, default=str)
                    return s3
        except Exception as e:
            log.error(f"  Git restore failed: {e}")
        return s
    except:
        return {"grids":{},"last_ai_check":None,"total_fills":0,
                "start_time":datetime.now(timezone.utc).isoformat()}

def save_state(state):
    os.makedirs("data", exist_ok=True)
    # Selalu sync capital dari GRID_CONFIG ke state sebelum save
    for sym, cfg in GRID_CONFIG.items():
        if sym in state.get("grids", {}):
            state["grids"][sym]["capital"] = cfg["capital"]
    state["grid_capitals"] = {sym: cfg["capital"] for sym, cfg in GRID_CONFIG.items()}
    # Buat backup sebelum overwrite, tapi hanya kalau fills > 0
    if os.path.exists(DATA_FILE):
        try:
            existing = json.load(open(DATA_FILE))
            if existing.get("total_fills", 0) > state.get("total_fills", 0):
                log.warning(f"  WARN: saving state with fewer fills ({state.get('total_fills')}) than existing ({existing.get('total_fills')}) — keeping backup")
            if existing.get("total_fills", 0) > 10:
                import shutil
                shutil.copy2(DATA_FILE, DATA_FILE + ".bak")
        except:
            pass
    json.dump(state, open(DATA_FILE,"w"), indent=2, default=str)

def check_fills_and_pnl(state):
    """Check filled orders dan hitung realized PnL per grid pair"""
    if "fills_log" not in state:
        state["fills_log"] = []
    if "realized_pnl" not in state:
        state["realized_pnl"] = 0.0
    if "total_rebalances" not in state:
        state["total_rebalances"] = 0
    if "last_prices" not in state:
        state["last_prices"] = {}

    for symbol in ASSETS:
        try:
            # Update live price
            price_data = api_get("/ticker/price", {"symbol": symbol})
            state["last_prices"][symbol] = float(price_data["price"])

            # Ambil filled orders (my trades)
            trades = api_get("/myTrades", {"symbol": symbol, "limit": 10}, auth=True)
            # Deep copy grid — preserve ALL fields including orders_placed
            grid = dict(state["grids"].get(symbol, {}))
            # Use seen_trade_ids (persists across resets) + fills_log
            if "seen_trade_ids" not in state:
                state["seen_trade_ids"] = {}
            if symbol not in state["seen_trade_ids"]:
                state["seen_trade_ids"][symbol] = []
            known = set(state["seen_trade_ids"][symbol])

            # Track inventory per asset
            if "inventory" not in state:
                state["inventory"] = {}
            inv = state["inventory"].get(symbol, 0.0)

            for t in trades:
                tid = t["id"]
                if tid in known:
                    continue
                # New fill!
                side = "BUY" if t["isBuyer"] else "SELL"
                price = float(t["price"])
                qty   = float(t["qty"])
                fee   = float(t.get("commission", 0))
                ts    = datetime.fromtimestamp(t["time"]/1000, tz=timezone.utc)
                # Slippage detection
                order_price = float(t.get("price", price))
                slippage_pct = abs(price - order_price) / order_price if order_price > 0 else 0
                if slippage_pct > 0.005:  # >0.5% slippage — log warning
                    log.warning(f"  ⚠️ SLIPPAGE {symbol} {side}: order={order_price:.4f} fill={price:.4f} slip={slippage_pct:.2%}")
                # Partial fill detection
                is_partial = qty < float(t.get("origQty", qty)) * 0.99 if t.get("origQty") else False
                if is_partial:
                    log.info(f"  ⚡ PARTIAL FILL {symbol} {side}: {qty}/{t.get('origQty')} @ {price:.4f}")

                # Update inventory
                if side == "BUY":
                    inv = round(inv + qty, 8)
                else:
                    inv = round(inv - qty, 8)
                state["inventory"][symbol] = inv

                fill = {
                    "tradeId": tid, "symbol": symbol,
                    "side": side, "price": price, "qty": qty,
                    "fee": fee, "time": ts.strftime("%H:%M:%S"), "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pnl": None, "inventory": inv,
                    "slippage_pct": round(slippage_pct, 5),
                    "is_partial": is_partial
                }

                # Pair BUY+SELL untuk hitung PnL — skip partial fills
                if side == "SELL" and not is_partial:
                    # FIFO pairing — ambil buy PERTAMA (oldest) yang belum dipair
                    buys = [f for f in state["fills_log"]
                            if f.get("symbol")==symbol and f.get("side")=="BUY" and f.get("pnl") is None]
                    if buys:
                        buy = buys[0]  # FIFO: oldest unpaired buy
                        pnl = round((price - buy["price"]) * min(qty, buy["qty"]) - fee, 4)
                        fill["pnl"] = pnl
                        buy["pnl"] = 0  # mark as paired
                        state["realized_pnl"] = round(state.get("realized_pnl", 0) + pnl, 4)
                        if "asset_pnl" not in state:
                            state["asset_pnl"] = {}
                        state["asset_pnl"][symbol] = round(
                            state["asset_pnl"].get(symbol, 0) + pnl, 4)
                        # Win rate tracking
                        if "win_loss" not in state:
                            state["win_loss"] = {"wins":0,"losses":0,"total_win":0.0,"total_loss":0.0,"best":0.0,"worst":0.0}
                        wl = state["win_loss"]
                        if pnl > 0:
                            wl["wins"]      = wl.get("wins",0) + 1
                            wl["total_win"] = round(wl.get("total_win",0) + pnl, 4)
                            wl["best"]      = round(max(wl.get("best",0), pnl), 4)
                        else:
                            wl["losses"]    = wl.get("losses",0) + 1
                            wl["total_loss"]= round(wl.get("total_loss",0) + pnl, 4)
                            wl["worst"]     = round(min(wl.get("worst",0), pnl), 4)
                        if "realized_pnl" not in grid:
                            grid["realized_pnl"] = 0
                        grid["realized_pnl"] = round(grid.get("realized_pnl", 0) + pnl, 4)

                state["fills_log"].append(fill)
                state["total_fills"] = state.get("total_fills", 0) + 1
                state["seen_trade_ids"][symbol].append(tid)
                # Keep seen_trade_ids trim (last 500 per symbol)
                state["seen_trade_ids"][symbol] = state["seen_trade_ids"][symbol][-500:]
                # Daily stop loss check per asset
                asset_daily_pnl = state["asset_pnl"].get(symbol, 0) - state.get("asset_daily_start", {}).get(symbol, 0)
                asset_capital   = GRID_CONFIG.get(symbol, {}).get("capital", 100)
                if asset_capital > 0 and asset_daily_pnl < -(asset_capital * 0.015):  # -1.5% daily stop
                    log.warning(f"  🔥 {symbol}: daily loss {asset_daily_pnl:.4f} > 1.5% — pausing")
                    state["grids"][symbol]["active"] = False
                    state["grids"][symbol]["reason"] = f"daily_stoploss: {asset_daily_pnl:.4f}"
                short2 = symbol.replace("USDT","")
                # Hanya notif SELL dengan PnL — skip BUY spam
                if side == "SELL" and fill.get("pnl") is not None:
                    pnl  = fill["pnl"]
                    icon = "\U0001f7e2" if pnl >= 0 else "\U0001f534"
                    tg(f"{icon} <b>TRADE CLOSED</b> \u2014 {short2}\n"
                       f"\u26a1 {qty:.4f} @ ${price:,.2f}\n"
                       f"\U0001f4b0 PnL: <b>${pnl:+.4f}</b>\n"
                       f"\U0001f4ca Total fills: {state['total_fills']:,}")
                if "fills" not in grid:
                    grid["fills"] = 0
                grid["fills"] = grid.get("fills", 0) + 1
                # Update grid — preserve orders_placed dan field lain
                state["grids"][symbol] = {
                    **state["grids"].get(symbol, {}),
                    "realized_pnl": grid.get("realized_pnl", 0),
                    "fills": grid.get("fills", 0),
                }
                log.info(f"  🔥 FILL: {symbol} {side} {qty} @ ${price:,.2f} | PnL: {fill.get('pnl','pending')}")

        except Exception as e:
            log.warning(f"  Fill check error {symbol}: {e}")

def check_trailing_stop(state):
    """
    Trailing stop per grid — geser range_low ke atas saat harga naik jauh.
    Tujuan: lock profit, hindari harga balik ke bawah range lama.
    """
    grids = state.get("grids", {})
    prices = state.get("last_prices", {})
    triggered = []

    for symbol, grid in grids.items():
        if not grid.get("active", False):
            continue
        price = prices.get(symbol, 0)
        if price <= 0:
            continue

        range_low  = grid.get("range_low", 0)
        range_high = grid.get("range_high", 0)
        if range_low <= 0 or range_high <= 0:
            continue

        range_size = range_high - range_low
        # Harga naik >3% dari range_low
        price_vs_low = (price - range_low) / range_low if range_low > 0 else 0

        if price_vs_low > TRAILING_STOP_PCT:
            # Geser range_low ke price - 1.5% (lock profit di bawah harga)
            new_low  = price * (1 - TRAILING_LOCK_PCT)
            new_high = new_low + range_size  # pertahankan lebar range

            # Jangan geser kalau new_low lebih kecil dari range_low saat ini
            if new_low <= range_low:
                continue

            log.info(f"  &#128200; TRAILING STOP {symbol}: range_low {range_low:.4f} -> {new_low:.4f} (price={price:.4f}, +{price_vs_low:.1%})")

            state["grids"][symbol]["range_low"]  = round(new_low, 4)
            state["grids"][symbol]["range_high"] = round(new_high, 4)
            state["grids"][symbol]["trailing_triggered"] = True
            state["grids"][symbol]["trailing_count"] = grid.get("trailing_count", 0) + 1

            triggered.append({
                "symbol": symbol,
                "old_low": range_low,
                "new_low": round(new_low, 4),
                "price": price,
                "gain_pct": round(price_vs_low * 100, 2)
            })
            short = symbol.replace("USDT","")
            tg(f"&#128200; <b>TRAILING STOP</b> — {short}\nPrice: <b>${price:.4f}</b> (+{price_vs_low:.1%} from low)\nRange: {range_low:.4f}-{range_high:.4f} → {round(new_low,4):.4f}-{round(new_high,4):.4f}\nLock #{grid.get('trailing_count',0)+1}")

    return triggered

def detect_extreme_event(analyses, state) -> dict:
    """
    Detect flash crash, volume spike, BB explosion.
    Returns: {"event": None|"FLASH_CRASH"|"VOLUME_SPIKE"|"BB_EXPLOSION", "detail": str}
    """
    prev_prices = state.get("prev_prices", {})
    prev_bb     = state.get("prev_bb_width", {})

    events = []
    for a in analyses:
        sym   = a["symbol"]
        price = a["price"]
        bb    = a["bb_width"]
        short = sym.replace("USDT","")

        # 1. Flash crash/pump — harga berubah >5% dari cycle sebelumnya
        prev_price = prev_prices.get(sym, price)
        price_change = abs(price - prev_price) / prev_price if prev_price > 0 else 0
        if price_change > FLASH_CRASH_PCT:
            direction = "PUMP 🔥" if price > prev_price else "CRASH 🔥"
            events.append({
                "event": "FLASH_CRASH",
                "sym": short,
                "detail": f"{short} {direction} {price_change:.1%} in 15min (${prev_price:.4f}→${price:.4f})"
            })

        # 2. BB width explosion — volatility tiba-tiba meledak
        prev_bb_width = prev_bb.get(sym, bb)
        if prev_bb_width > 0 and bb > prev_bb_width * BB_EXPLOSION_MULT:
            events.append({
                "event": "BB_EXPLOSION",
                "sym": short,
                "detail": f"{short} BB exploded {bb/prev_bb_width:.1f}x ({prev_bb_width:.3f}→{bb:.3f})"
            })

    # Update previous values
    state["prev_prices"]   = {a["symbol"]: a["price"] for a in analyses}
    state["prev_bb_width"] = {a["symbol"]: a["bb_width"] for a in analyses}

    if events:
        # Return most severe event
        crashes = [e for e in events if e["event"] == "FLASH_CRASH"]
        bb_exp  = [e for e in events if e["event"] == "BB_EXPLOSION"]
        if crashes:
            return crashes[0]
        return bb_exp[0]

    return {"event": None, "detail": ""}

def check_asset_stop_loss(state):
    """
    Stop loss per asset — pause grid jika rugi >15% dari capital asset.
    Auto-resume setelah cooldown 4 jam.
    """
    asset_pnl = state.get("asset_pnl", {})
    grids     = state.get("grids", {})
    now       = datetime.now(timezone.utc)
    paused    = []
    resumed   = []

    for sym, cfg in GRID_CONFIG.items():
        grid = grids.get(sym, {})
        if not grid: continue

        capital   = cfg["capital"]
        pnl       = float(asset_pnl.get(sym, 0))
        loss_pct  = pnl / capital if capital > 0 else 0

        # Cek cooldown — auto resume setelah 4 jam
        sl_paused_at = grid.get("sl_paused_at")
        if sl_paused_at and not grid.get("active", True):
            paused_dt = datetime.fromisoformat(sl_paused_at)
            hours_passed = (now - paused_dt).total_seconds() / 3600
            if hours_passed >= ASSET_STOP_COOLDOWN:
                state["grids"][sym]["active"] = True
                state["grids"][sym]["sl_paused_at"] = None
                log.info(f"  &#9989; {sym} STOP LOSS cooldown done — resuming")
                resumed.append(sym.replace("USDT",""))

        # Cek stop loss
        if loss_pct < -ASSET_STOP_LOSS_PCT and grid.get("active", True):
            log.warning(f"  &#128721; ASSET STOP LOSS {sym}: {loss_pct:.1%} loss (limit {ASSET_STOP_LOSS_PCT:.0%})")
            state["grids"][sym]["active"] = False
            state["grids"][sym]["sl_paused_at"] = now.isoformat()
            cancel_open_orders(sym)
            paused.append(f"{sym.replace('USDT','')}: {loss_pct:.1%}")

    if paused:
        tg(f"&#128721; <b>ASSET STOP LOSS</b>\n" +
           "\n".join(paused) +
           f"\nAuto-resume in {ASSET_STOP_COOLDOWN}h")

    if resumed:
        tg(f"&#9989; <b>ASSET RESUMED</b>\n" +
           ", ".join(resumed) +
           "\nCooldown complete")

def check_risk(state) -> str:
    """
    Returns: 'OK', 'DAILY_LOSS', 'DRAWDOWN', atau 'OK_TARGET_HIT'
    """
    total_capital = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
    realized_pnl  = state.get("realized_pnl", 0)

    # Daily loss check — reset setiap hari
    wib   = timezone(timedelta(hours=7))
    today = datetime.now(wib).strftime("%Y-%m-%d")
    if state.get("daily_reset_date") != today:
        # Save yesterday to history before reset
        prev_date  = state.get("daily_reset_date")
        prev_start = state.get("daily_start_pnl", 0)
        prev_fills = state.get("daily_start_fills", 0)
        if prev_date:
            day_pnl   = round(realized_pnl - prev_start, 4)
            day_fills = state.get("total_fills", 0) - prev_fills
            if "daily_pnl_history" not in state:
                state["daily_pnl_history"] = {}
            state["daily_pnl_history"][prev_date] = {
                "pnl":        day_pnl,
                "fills":      day_fills,
                "cumulative": round(realized_pnl, 4),
                "roi_pct":    round(day_pnl / 500 * 100, 3)
            }
            log.info(f"  Daily snapshot saved: {prev_date} PnL=${day_pnl:+.4f} fills={day_fills}")
        state["daily_reset_date"] = today
        state["daily_start_pnl"]  = realized_pnl
        apply_compound(state)  # Compound 50% profit ke capital
        state["daily_start_fills"] = state.get("total_fills", 0)
        state["daily_peak_pnl"]   = realized_pnl

    daily_start = state.get("daily_start_pnl", 0)
    daily_pnl   = realized_pnl - daily_start
    daily_pct   = daily_pnl / total_capital

    # Update daily peak
    if realized_pnl > state.get("daily_peak_pnl", realized_pnl):
        state["daily_peak_pnl"] = realized_pnl

    # Max drawdown dari peak
    peak_pnl  = state.get("daily_peak_pnl", realized_pnl)
    drawdown  = (peak_pnl - realized_pnl) / total_capital

    if daily_pct < -MAX_DAILY_LOSS_PCT:
        msg = f"🔥 DAILY LOSS LIMIT: {daily_pct:.1%} (limit {MAX_DAILY_LOSS_PCT:.0%})"
        log.warning(msg)
        tg(f"🔥 <b>EMERGENCY STOP</b>\nDaily loss: <b>{daily_pct:.1%}</b>\nAll grids paused")
        return "DAILY_LOSS"

    if drawdown > MAX_DRAWDOWN_PCT:
        msg = f"🔥 MAX DRAWDOWN: {drawdown:.1%} (limit {MAX_DRAWDOWN_PCT:.0%})"
        log.warning(msg)
        tg(f"🔥 <b>DRAWDOWN STOP</b>\nDrawdown: <b>{drawdown:.1%}</b>\nAll grids paused")
        return "DRAWDOWN"

    return "OK"


def check_balance_change(state):
    """
    Deteksi perubahan balance mendadak (user tarik/kurangi dana).
    Jika balance turun >15% dari expected → pause semua grid + alert.
    Jika balance naik >10% → auto adjust capital + alert.
    """
    try:
        # Ambil USDT balance dari Binance
        ts  = int(time.time() * 1000)
        params = {"timestamp": ts}
        params["signature"] = hmac.new(
            API_SECRET.encode(), urlencode(params).encode(), hashlib.sha256
        ).hexdigest()
        r = requests.get(
            f"{BASE_URL}/account",
            headers={"X-MBX-APIKEY": API_KEY},
            params=params, timeout=10
        )
        if r.status_code != 200: return
        # Hanya cek FREE USDT — token lain milik user tidak dihitung
        free_usdt = 0.0
        for b in r.json().get("balances", []):
            if b["asset"] == "USDT":
                free_usdt = float(b["free"])
                break
        usdt_balance = free_usdt

        # Expected capital
        expected = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
        last_known = float(state.get("last_known_balance", expected))

        if last_known == 0:
            state["last_known_balance"] = usdt_balance
            return

        change_pct = (usdt_balance - last_known) / last_known

        if change_pct < -0.15:
            # Balance turun >15% — pause semua grid
            log.warning(f"  ⚠️ BALANCE DROP detected! {last_known:.2f} → {usdt_balance:.2f} ({change_pct*100:.1f}%)")
            for sym in GRID_CONFIG:
                if state.get("grids", {}).get(sym, {}).get("active"):
                    state["grids"][sym]["active"] = False
                    state["grids"][sym]["balance_paused"] = True
            tg(f"⚠️ <b>BALANCE DROP DETECTED</b>\n"
               f"Expected: <b>${last_known:.2f}</b>\n"
               f"Current:  <b>${usdt_balance:.2f}</b>\n"
               f"Change: <b>{change_pct*100:.1f}%</b>\n"
               f"All grids paused. Top up balance or contact support.")
            state["last_known_balance"] = usdt_balance

        elif change_pct > 0.10:
            # Balance naik >10% — auto adjust capital
            log.info(f"  �� BALANCE INCREASE detected! {last_known:.2f} → {usdt_balance:.2f} ({change_pct*100:+.1f}%)")
            ratio = usdt_balance / last_known
            for sym, cfg in GRID_CONFIG.items():
                cfg["capital"] = round(cfg["capital"] * ratio, 2)
                if state.get("grids", {}).get(sym, {}).get("balance_paused"):
                    state["grids"][sym]["active"] = True
                    state["grids"][sym]["balance_paused"] = False
            new_total = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
            state["total_capital"] = new_total
            tg(f"�� <b>BALANCE UPDATED</b>\n"
               f"Previous: <b>${last_known:.2f}</b>\n"
               f"New: <b>${usdt_balance:.2f}</b>\n"
               f"Capital auto-adjusted to ${new_total:.2f}")
            state["last_known_balance"] = usdt_balance

    except Exception as e:
        log.error(f"  check_balance_change error: {e}")


def check_balance_change(state):
    """
    Deteksi perubahan balance mendadak (user tarik/kurangi dana).
    Jika balance turun >15% dari expected → pause semua grid + alert.
    Jika balance naik >10% → auto adjust capital + alert.
    """
    try:
        # Ambil USDT balance dari Binance
        ts  = int(time.time() * 1000)
        params = {"timestamp": ts}
        params["signature"] = hmac.new(
            API_SECRET.encode(), urlencode(params).encode(), hashlib.sha256
        ).hexdigest()
        r = requests.get(
            f"{BASE_URL}/account",
            headers={"X-MBX-APIKEY": API_KEY},
            params=params, timeout=10
        )
        if r.status_code != 200: return
        # Hanya cek FREE USDT — token lain milik user tidak dihitung
        free_usdt = 0.0
        for b in r.json().get("balances", []):
            if b["asset"] == "USDT":
                free_usdt = float(b["free"])
                break
        usdt_balance = free_usdt

        # Expected capital
        expected = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
        last_known = float(state.get("last_known_balance", expected))

        if last_known == 0:
            state["last_known_balance"] = usdt_balance
            return

        change_pct = (usdt_balance - last_known) / last_known

        if change_pct < -0.15:
            # Balance turun >15% — pause semua grid
            log.warning(f"  ⚠️ BALANCE DROP detected! {last_known:.2f} → {usdt_balance:.2f} ({change_pct*100:.1f}%)")
            for sym in GRID_CONFIG:
                if state.get("grids", {}).get(sym, {}).get("active"):
                    state["grids"][sym]["active"] = False
                    state["grids"][sym]["balance_paused"] = True
            tg(f"⚠️ <b>BALANCE DROP DETECTED</b>\n"
               f"Expected: <b>${last_known:.2f}</b>\n"
               f"Current:  <b>${usdt_balance:.2f}</b>\n"
               f"Change: <b>{change_pct*100:.1f}%</b>\n"
               f"All grids paused. Top up balance or contact support.")
            state["last_known_balance"] = usdt_balance

        elif change_pct > 0.10:
            # Balance naik >10% — auto adjust capital
            log.info(f"  �� BALANCE INCREASE detected! {last_known:.2f} → {usdt_balance:.2f} ({change_pct*100:+.1f}%)")
            ratio = usdt_balance / last_known
            for sym, cfg in GRID_CONFIG.items():
                cfg["capital"] = round(cfg["capital"] * ratio, 2)
                if state.get("grids", {}).get(sym, {}).get("balance_paused"):
                    state["grids"][sym]["active"] = True
                    state["grids"][sym]["balance_paused"] = False
            new_total = sum(cfg["capital"] for cfg in GRID_CONFIG.values())
            state["total_capital"] = new_total
            tg(f"�� <b>BALANCE UPDATED</b>\n"
               f"Previous: <b>${last_known:.2f}</b>\n"
               f"New: <b>${usdt_balance:.2f}</b>\n"
               f"Capital auto-adjusted to ${new_total:.2f}")
            state["last_known_balance"] = usdt_balance

    except Exception as e:
        log.error(f"  check_balance_change error: {e}")

def check_range_breach(state, analyses):
    """
    Trailing grid + range breach protection.
    - Kalau harga di top/bottom 20% range → trail (geser range)
    - Kalau harga keluar range + 15% buffer → cancel + rebalance
    """
    for a in analyses:
        sym   = a["symbol"]
        price = a["price"]
        grid  = state.get("grids", {}).get(sym, {})
        if not grid.get("active"): continue
        rl, rh = grid.get("range_low", 0), grid.get("range_high", 0)
        if not rl or not rh: continue

        cfg        = GRID_CONFIG.get(sym, {})
        range_size = rh - rl
        pos_pct    = (price - rl) / range_size if range_size > 0 else 0.5

        # ── TRAILING: harga di top 15% atau bottom 15% ──
        if pos_pct > 0.85 or pos_pct < 0.15:
            # Geser range ke tengah harga sekarang
            half    = range_size / 2
            if price < 0.001:   p_dec = 7
            elif price < 0.01:  p_dec = 6
            elif price < 0.1:   p_dec = 5
            elif price < 1:     p_dec = 4
            elif price < 10:    p_dec = 3
            else:               p_dec = 2
            new_rl  = round(price - half, p_dec)
            new_rh  = round(price + half, p_dec)
            direction = "⬆️ UP" if pos_pct > 0.85 else "⬇️ DOWN"
        # Strong trend warning (trend from analyses)
        a_data = next((x for x in analyses if x["symbol"] == sym), {})
        trend  = a_data.get("trend", "NEUTRAL")
        if pos_pct > 0.80 and trend == "UP":
            log.info(f"  ⚠️ {sym}: strong uptrend at {pos_pct:.0%} — consider waiting for pullback")
        elif pos_pct < 0.20 and trend == "DOWN":
            log.info(f"  WARNING {sym}: strong downtrend at {pos_pct:.0%} — reducing exposure")
            if 'new_rl' in dir() or 'new_rl' in locals():
                placed = place_grid(sym, new_rl, new_rh,
                                    cfg.get("num_grids", 10), cfg.get("capital", 100), price)
                state["grids"][sym] = {
                    **grid,
                    "range_low": new_rl, "range_high": new_rh,
                    "orders_placed": placed,
                    "last_trail": datetime.now(timezone.utc).isoformat(),
                }
                continue

        # ── RANGE BREACH: harga keluar range + buffer 15% ──
        buffer = range_size * RANGE_BREACH_PCT
        if price < rl - buffer or price > rh + buffer:
            log.warning(f"  ⚠️  {sym} RANGE BREACH: price {price} outside {rl}-{rh}")
            tg(f"⚠️ <b>RANGE BREACH</b> — {sym.replace('USDT','')}\n"
               f"Price: ${price} outside ${rl}-${rh}\nGrid cancelled, will rebalance")
            cancel_open_orders(sym)
            state["grids"][sym] = {"active": False,
                                   "reason": f"Range breach: {price:.4f} outside {rl}-{rh}"}
            state["last_ai_check"] = None


_last_update_id = 0

def check_telegram_commands(state):
    global _last_update_id
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": _last_update_id + 1, "timeout": 2, "limit": 5},
            timeout=5
        )
        updates = r.json().get("result", [])
        for upd in updates:
            _last_update_id = upd["update_id"]
            msg = upd.get("message", {})
            if str(msg.get("chat", {}).get("id", "")) != str(chat_id):
                continue
            text = msg.get("text", "").strip().lower()
            log.info(f"  Telegram cmd: {text}")
            if text == "/stop":
                for sym in list(state.get("grids", {}).keys()):
                    cancel_open_orders(sym)
                    state["grids"][sym]["active"] = False
                    state["grids"][sym]["reason"] = "manual_stop"
                state["emergency_stop"] = True
                tg("EMERGENCY STOP\nAll grids cancelled\nSend /start to resume\n#zerovant")
                log.warning("  EMERGENCY STOP via Telegram")
            elif text == "/start":
                state["emergency_stop"] = False
                for sym in list(state.get("grids", {}).keys()):
                    state["grids"][sym]["active"] = True
                    state["grids"][sym]["reason"] = "manual_start"
                state["last_ai_check"] = None
                tg("BOT RESUMED\nAll grids reactivated\n#zerovant")
                log.info("  BOT RESUMED via Telegram")
            elif text == "/status":
                fs     = state.get("fee_simulation", {})
                net    = float(fs.get("simulated_pnl", 0))
                fills  = state.get("total_fills", 0)
                wl     = state.get("win_loss", {})
                wins   = wl.get("wins", 0)
                losses = wl.get("losses", 0)
                wr     = wins / (wins + losses) * 100 if wins + losses > 0 else 0
                active = sum(1 for g in state.get("grids", {}).values() if g.get("active"))
                snap   = state.get("today_snapshot", {}) or {}
                today  = float(snap.get("pnl", 0))
                tg(
                    "BOT STATUS\n"
                    + f"Net PnL: ${net:+.2f}\n"
                    + f"Today: ${today:+.4f}\n"
                    + f"WR: {wr:.1f}% ({wins}W/{losses}L)\n"
                    + f"Fills: {fills:,}\n"
                    + f"Active grids: {active}/5\n"
                    + "#zerovant"
                )
            elif text == "/pause":
                for sym in list(state.get("grids", {}).keys()):
                    cancel_open_orders(sym)
                    state["grids"][sym]["active"] = False
                    state["grids"][sym]["reason"] = "manual_pause"
                tg("BOT PAUSED\nSend /resume to continue\n#zerovant")
            elif text == "/resume":
                for sym in list(state.get("grids", {}).keys()):
                    state["grids"][sym]["active"] = True
                    state["grids"][sym]["reason"] = "manual_resume"
                state["last_ai_check"] = None
                tg("BOT RESUMED\n#zerovant")
            elif text == "/help":
                tg(
                    "ZEROVANT CLAW COMMANDS\n"
                    "/status - cek performa\n"
                    "/stop - emergency stop semua grid\n"
                    "/start - resume setelah stop\n"
                    "/pause - pause sementara\n"
                    "/resume - resume setelah pause\n"
                    "/help - tampilkan ini"
                )
    except Exception as e:
        log.debug(f"  Telegram poll error: {e}")

def run():
    log.info("="*55)
    log.info("  ZEROVANT GRID v1.0 — AI Adaptive Multi-Asset")
    log.info(f"  Assets: {', '.join(ASSETS)}")
    log.info("="*55)
    state = load_state()
    # Sync GRID_CONFIG capital dari state saat startup
    grid_capitals = state.get("grid_capitals", {})
    for sym, cfg in GRID_CONFIG.items():
        cap = None
        if grid_capitals and grid_capitals.get(sym) and float(grid_capitals.get(sym,0)) > 0:
            cap = float(grid_capitals[sym])
        elif state.get("grids",{}).get(sym,{}).get("capital") and float(state["grids"][sym].get("capital",0)) > 0:
            cap = float(state["grids"][sym]["capital"])
        if cap:
            cfg["capital"] = cap
            log.info(f"  Capital restored {sym}: ${cap}")
    # Init daily tracking
    today_init = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if "daily_pnl_history" not in state:
        state["daily_pnl_history"] = {}
    if "daily_start_pnl" not in state:
        state["daily_start_pnl"] = state.get("realized_pnl", 0)
        rebalance_capital(state)
        log.info("  Capital rebalanced based on performance")
    # Always backfill stats on startup
    backfill_stats(state)
    if "daily_start_fills" not in state:
        state["daily_start_fills"] = state.get("total_fills", 0)
    if "last_snapshot_date" not in state:
        state["last_snapshot_date"] = today_init
    save_state(state)
    cycle = 0
    while True:
        cycle += 1
        # Reload state dari file — agar perubahan dari tg_bot (pause/resume/stop) terbaca
        state = load_state()
        now = datetime.now(timezone.utc)
        log.info(f"\n── Cycle #{cycle} | {now.strftime('%H:%M:%S UTC')} ──────────")
        # Refresh derived stats every 4 cycles
        if cycle % 4 == 0:
            backfill_stats(state)
        analyses = []
        for symbol in ASSETS:
            try:
                a = market_analysis(symbol)
                analyses.append(a)
                log.info(f"  {symbol}: ${a['price']:.2f} | {a['vol_regime']} | 15m:{a['trend15']} 1h:{a['trend1h']} 4h:{a['trend4h']} [{a['up_count']}/3] | BB:{a['bb_width']:.3f}")
                # Save current price to grid state for dashboard
                if "grids" not in state:
                    state["grids"] = {}
                if symbol not in state["grids"]:
                    state["grids"][symbol] = {}
                state["grids"][symbol]["current_price"] = float(a["price"])
                # Aggressive rebalance trigger
                g  = state["grids"][symbol]
                rl = float(g.get("range_low") or 0)
                rh = float(g.get("range_high") or 0)
                cp = float(a["price"])
                if rh > rl:
                    pos_pct = (cp - rl) / (rh - rl)
                    if pos_pct > 0.88 or pos_pct < 0.08:
                        # Cooldown check — skip jika rebalance < 90 menit lalu
                        lr = g.get("last_rebalance_time")
                        skip = False
                        if lr:
                            try:
                                elapsed = (now - datetime.fromisoformat(lr)).total_seconds()
                                if elapsed < 5400:
                                    log.info(f"  ⏳ {symbol}: rebalance cooldown {elapsed/60:.0f}/90min")
                                    skip = True
                            except: pass
                        if not skip:
                            log.info(f"  ⚡ {symbol}: price at {pos_pct:.0%} of range — needs rebalance")
                            g["last_rebalance"] = None
            except Exception as e:
                log.error(f"  Analysis fail {symbol}: {e}")
        if not analyses:
            time.sleep(CYCLE_MINUTES * 60); continue
        last = state.get("last_ai_check")
        ai_elapsed = (now - datetime.fromisoformat(last)).total_seconds() if last else 99999
        if not last or ai_elapsed > AI_REBALANCE_H * 3600:
            log.info("  🔥 AI evaluating grid parameters...")
            global _current_state
            _current_state = state
            decisions = ai_grid_decision(analyses, state.get("grids", {}))
            state["last_ai_check"] = now.isoformat()
            state["total_rebalances"] = state.get("total_rebalances", 0) + 1
            if "ai_log" not in state: state["ai_log"] = []
            for a in analyses:
                sym = a["symbol"]
                d   = decisions.get(sym, {})
                action = d.get("action", "KEEP")
                log.info(f"  {sym}: {action} — {d.get('reason','')}")
                state["ai_log"].append({
                    "type": "ai",
                    "action": action,
                    "symbol": sym.replace("USDT",""),
                    "reason": d.get("reason","")[:70],
                    "msg": f"[{now.strftime('%H:%M')}] {sym.replace('USDT','')}: {action} — {d.get('reason','')[:70]}"
                })
                short = sym.replace('USDT','')
                if action in ("REBALANCE","KEEP"):
                    tg(f"🔥 <b>AI REBALANCE</b> — {short}\n🔥 Action: {action}\n🔥 {d.get('reason','')[:80]}")
                elif action == "CANCEL":
                    tg(f"⏸️ <b>GRID PAUSED</b> — {short}\n🔥 {d.get('reason','')[:80]}")
                cancel_open_orders(sym)
                # Position sizing berdasarkan AI confidence
                confidence = float(d.get("confidence", 0.75))
                base_capital = GRID_CONFIG.get(sym, {}).get("capital", 100)
                if confidence >= 0.80:
                    allocated_capital = base_capital * 1.0   # full capital
                    sizing_label = "FULL"
                elif confidence >= 0.50:
                    allocated_capital = base_capital * 0.75  # 75%
                    sizing_label = "REDUCED"
                else:
                    allocated_capital = base_capital * 0.50  # 50%
                    sizing_label = "MINIMAL"
                log.info(f"  &#127919; {sym} confidence={confidence:.0%} → {sizing_label} capital (${allocated_capital:.0f})")
                # Save confidence to state
                if sym in state.get("grids", {}):
                    state["grids"][sym]["ai_confidence"] = confidence
                    state["grids"][sym]["capital_sizing"] = sizing_label

                # Override AI CANCEL jika performance masih bagus
                analytics = state.get("analytics", {})
                a_data   = analytics.get(sym, {})
                pf_live  = float(a_data.get("profit_factor", 0))
                wr_live  = float(a_data.get("wr", 0))
                if action == "CANCEL" and pf_live >= 1.0 and wr_live >= 45:
                    log.info(f"  &#9888; {sym}: AI said CANCEL but PF={pf_live} WR={wr_live}% — overriding to REBALANCE")
                    action = "REBALANCE"
                    if not d.get("range_low") or d.get("range_low", 0) <= 0:
                        cfg_tmp = GRID_CONFIG[sym]
                        half = a["price"] * cfg_tmp["range_pct"] / 2
                        d["range_low"]  = round(a["price"] - half, 4)
                        d["range_high"] = round(a["price"] + half, 4)

                # Jika asset belum ada grid aktif, force init meskipun action KEEP
                current_grid = state.get("grids", {}).get(sym, {})
                has_active_grid = current_grid.get("active") and float(current_grid.get("range_low") or 0) > 0
                if action == "KEEP" and not has_active_grid:
                    log.info(f"  &#128257; {sym}: KEEP but no active grid — forcing REBALANCE init")
                    action = "REBALANCE"
                    # Build range from price if AI didn't provide
                    if not d.get("range_low") or d.get("range_low", 0) <= 0:
                        cfg_tmp = GRID_CONFIG[sym]
                        half = a["price"] * cfg_tmp["range_pct"] / 2
                        d["range_low"]  = round(a["price"] - half, 4)
                        d["range_high"] = round(a["price"] + half, 4)

                if action in ("REBALANCE","KEEP") and d.get("range_low",0) > 0:
                    price = a["price"]
                    cfg   = GRID_CONFIG[sym]

                    # ALWAYS use backtest-optimized num_grids — ignore AI suggestion
                    num_grids = cfg["num_grids"]

                    # Range: use AI suggestion but cap at target_range × 1.2
                    rl, rh = d["range_low"], d["range_high"]
                    max_range = price * cfg["range_pct"] * 1.2
                    actual_range = rh - rl
                    if actual_range > max_range or rl <= 0 or rh <= rl:
                        half = price * cfg["range_pct"] / 2
                        if price < 0.001:   p_dec = 7
                        elif price < 0.01:  p_dec = 6
                        elif price < 0.1:   p_dec = 5
                        elif price < 1:     p_dec = 4
                        elif price < 10:    p_dec = 3
                        else:               p_dec = 2
                        rl = round(price - half, p_dec)
                        rh = round(price + half, p_dec)
                        log.info(f"  ⚠️  Range capped to {cfg['range_pct']*100:.0f}%: {rl}-{rh}")
                    # Final sanity — jika range masih invalid, hitung dari price
                    price_now = a["price"]
                    if rl <= 0 or rh <= 0 or rh <= rl:
                        half = price_now * cfg["range_pct"] / 2
                        if price_now < 0.001:   p_dec = 7
                        elif price_now < 0.01:  p_dec = 6
                        elif price_now < 0.1:   p_dec = 5
                        elif price_now < 1:     p_dec = 4
                        elif price_now < 10:    p_dec = 3
                        else:                   p_dec = 2
                        rl = round(price_now - half, p_dec)
                        rh = round(price_now + half, p_dec)
                        log.info(f"  🔥 Range rebuilt from price: {rl}-{rh}")
                    d["range_low"], d["range_high"] = rl, rh
                    # Force num_grids from config — ignore AI
                    num_grids = cfg["num_grids"]
                    placed = place_grid(sym, rl, rh,
                               num_grids, allocated_capital, a["price"])
                    state["grids"][sym] = {
                        **d, "active": True,
                        "last_rebalance": now.isoformat(),
                        "orders_placed": placed,
                        "realized_pnl": state["grids"].get(sym, {}).get("realized_pnl", 0),
                        "fills": state["grids"].get(sym, {}).get("fills", 0),
                    }
                else:
                    state["grids"][sym] = {"active":False, "reason":d.get("reason","")}
            save_state(state)
        for sym in ASSETS:
            try:
                n = len(api_get("/openOrders", {"symbol": sym}, auth=True))
                log.info(f"  {sym}: {n} open orders")
                # Aggressive rebalance — price out of comfort zone
                g  = state["grids"].get(sym, {})
                cp = g.get("current_price") or 0
                rl = float(g.get("range_low") or 0)
                rh = float(g.get("range_high") or 0)
                if cp and rh > rl:
                    pos_pct = (float(cp) - rl) / (rh - rl)
                    if pos_pct > 0.88 or pos_pct < 0.08:
                        lr = state["grids"][sym].get("last_rebalance_time")
                        skip = False
                        if lr:
                            try:
                                elapsed = (now - datetime.fromisoformat(lr)).total_seconds()
                                if elapsed < 5400:
                                    log.info(f"  ⏳ {sym}: cooldown {elapsed/60:.0f}/90min")
                                    skip = True
                            except: pass
                        if not skip:
                            log.info(f"  ⚡ {sym}: price at {pos_pct:.0%} of range — forcing rebalance")
                            state["grids"][sym]["last_rebalance"] = None
            except Exception as e:
                log.warning(f"  Check fail {sym}: {e}")

        # Emergency stop check
        if state.get('emergency_stop'):
            log.info('  🛑 Emergency stop active — skipping cycle')
            check_telegram_commands(state)
            time.sleep(60)
            continue
        if state.get('emergency_stop'):
            log.info('  Emergency stop active')
            check_telegram_commands(state)
            time.sleep(60)
            continue
        # ── EXTREME EVENT CHECK ─────────────────────
        extreme = detect_extreme_event(analyses, state)
        if extreme["event"]:
            ev   = extreme["event"]
            det  = extreme["detail"]
            log.warning(f"  🔥 EXTREME EVENT: {ev} — {det}")

            # Check apakah masih dalam cooldown
            last_extreme = state.get("last_extreme_event_time")
            in_cooldown  = False
            if last_extreme:
                elapsed = (now - datetime.fromisoformat(last_extreme)).total_seconds() / 60
                in_cooldown = elapsed < COOLDOWN_MINUTES

            if not in_cooldown:
                # Cancel SEMUA grids
                for sym in ASSETS:
                    cancel_open_orders(sym)
                    state["grids"][sym] = {
                        "active": False,
                        "reason": f"{ev}: {det[:60]}"
                    }
                state["last_extreme_event_time"] = now.isoformat()
                state["last_ai_check"] = None  # Force rebalance setelah cooldown

                tg(f"🔥 <b>EXTREME EVENT DETECTED</b>\n"
                   f"Type: <b>{ev}</b>\n"
                   f"Detail: {det}\n"
                   f"Action: All grids cancelled\n"
                   f"Cooldown: {COOLDOWN_MINUTES} minutes")

                log.warning(f"  🔥 ALL GRIDS CANCELLED — cooldown {COOLDOWN_MINUTES}min")
                save_state(state)
                time.sleep(COOLDOWN_MINUTES * 60)
                continue
            else:
                remaining = COOLDOWN_MINUTES - elapsed
                log.info(f"  ⏳ Cooldown active: {remaining:.0f}min remaining")

        # ── RISK CHECK ──────────────────────────────
        risk_status = check_risk(state)
        if risk_status in ("DAILY_LOSS", "DRAWDOWN"):
            # Emergency: cancel semua grids
            for sym in ASSETS:
                cancel_open_orders(sym)
                state["grids"][sym] = {"active": False, "reason": risk_status}
            save_state(state)
            log.warning(f"  🔥 EMERGENCY STOP: {risk_status} — sleeping 1 hour")
            time.sleep(3600)
            continue

        # Range breach check
        check_range_breach(state, analyses)

        # Check fills dan update PnL
        check_fills_and_pnl(state)

        # Trailing stop — lock profit saat harga naik jauh
        trailing = check_trailing_stop(state)
        if trailing:
            for t in trailing:
                log.info(f"  �� TRAILING locked: {t['symbol']} +{t['gain_pct']}% | new_low={t['new_low']}")
        # Compute analytics setiap 4 cycle (1 jam)
        if cycle % 4 == 0:
            compute_analytics(state)
        # Balance change detection setiap 8 cycle (~2 jam)
        if cycle % 8 == 0:
            check_balance_change(state)
        # Balance change detection setiap 8 cycle (~2 jam)
        if cycle % 8 == 0:
            check_balance_change(state)
        # Stop loss per asset
        check_asset_stop_loss(state)
        # Check milestones
        check_milestones(state)
        save_state(state)
        # Daily summary setiap 96 cycle (~24 jam)
        if cycle % 96 == 0:
            pnl = state.get("realized_pnl", 0)
            fills = state.get("total_fills", 0)
            active_n = sum(1 for g in state.get("grids",{}).values() if g.get("active"))
            tg(f"🔥 <b>DAILY SUMMARY</b>\n🔥 Realized PnL: <b>${pnl:+.2f}</b>\n🔥 Total Fills: {fills}\n🔥 Active Grids: {active_n}/3\n🔥 Cycles: {cycle}")
            # Auto-rebalance capital berdasarkan performance
            rebalance_capital(state)
            save_state(state)
        # Update equity history untuk chart
        _start_cap = float(state.get("start_capital", 500))
        _net_pnl = float(state.get("fee_simulation", {}).get("simulated_pnl", 0))
        current_equity = round(_start_cap + _net_pnl, 2)
        # Smooth: equity hanya naik atau turun pelan (max 5% per cycle)
        _last_eq = state["equity_history"][-1] if state.get("equity_history") else _start_cap
        _max_change = _last_eq * 0.05
        if abs(current_equity - _last_eq) > _max_change:
            current_equity = round(_last_eq + (_max_change if current_equity > _last_eq else -_max_change), 2)
        if "equity_history" not in state or state["equity_history"][0] == 1800:
            state["equity_history"] = [500.0]
        cycle_count = state.get("cycle_count", 0) + 1
        state["cycle_count"] = cycle_count
        last_eq = state["equity_history"][-1] if state["equity_history"] else 500.0
        if current_equity != last_eq or cycle_count % 2 == 0:
            state["equity_history"].append(current_equity)
        if len(state["equity_history"]) > 500:
            state["equity_history"] = state["equity_history"][:100:2] + state["equity_history"][-400:]

        # Update AI rebalances count
        if "total_rebalances" not in state:
            state["total_rebalances"] = 0

        # Update open orders count di state
        total_open = 0
        for sym in ASSETS:
            try:
                n = len(api_get("/openOrders", {"symbol": sym}, auth=True))
                if sym in state["grids"] and state["grids"][sym].get("active"):
                    state["grids"][sym]["open_orders"] = n
                    total_open += n
            except: pass
        state["total_open_orders"] = total_open

        # AI log
        if "ai_log" not in state:
            state["ai_log"] = []

        save_state(state)
        # Update today_snapshot setiap cycle
        realized  = float(state.get("realized_pnl", 0))
        day_start = float(state.get("daily_start_pnl", realized))
        today_gross = round(realized - day_start, 4)
        fills_today = state.get("total_fills", 0) - state.get("daily_start_fills", 0)
        state["today_snapshot"] = {
            "pnl":     today_gross,
            "net_pnl": round(today_gross * 0.85, 4),
            "fills":   fills_today
        }
        check_telegram_commands(state)
        log.info(f"  Sleep {CYCLE_MINUTES}min...")
        time.sleep(CYCLE_MINUTES * 60)

def backfill_stats(state):
    """Recalculate all derived stats from fills_log"""
    import math
    fills = state.get("fills_log", [])
    sells = [f for f in fills if f.get("side")=="SELL" and f.get("pnl") not in (None, 0)]

    # Win/loss
    wl = {"wins":0,"losses":0,"total_win":0.0,"total_loss":0.0,"best":0.0,"worst":0.0}
    for f in sells:
        pnl = f.get("pnl", 0)
        if pnl > 0:
            wl["wins"] += 1; wl["total_win"] = round(wl["total_win"]+pnl,4); wl["best"] = round(max(wl["best"],pnl),4)
        else:
            wl["losses"] += 1; wl["total_loss"] = round(wl["total_loss"]+pnl,4); wl["worst"] = round(min(wl["worst"],pnl),4)
    state["win_loss"] = wl

    # Fee simulation
    TAKER = 0.001
    real_pnl = 0.0; rw = 0; rl = 0
    for f in sells:
        gross = f.get("pnl", 0)
        fee   = float(f.get("price",0)) * float(f.get("qty",0)) * TAKER * 2
        net   = gross - fee
        if net > 0: rw += 1
        else: rl += 1
        real_pnl += net
    gross_pnl  = round(sum(f.get("pnl",0) for f in sells), 4)
    fee_impact = round(real_pnl - gross_pnl, 4)
    state["fee_simulation"] = {
        "fee_rate": 0.001, "simulated_pnl": round(real_pnl,4),
        "gross_pnl": gross_pnl,
        "fee_impact": fee_impact,
        "real_win_rate": round(rw/(rw+rl)*100,1) if (rw+rl)>0 else 0,
        "real_wins": rw, "real_losses": rl
    }

    # Sharpe + MaxDD
    equity = state.get("equity_history",[500])
    if len(equity) > 2:
        returns = [(equity[i]-equity[i-1])/equity[i-1] for i in range(1,len(equity))]
        avg_r = sum(returns)/len(returns)
        std_r = math.sqrt(sum((r-avg_r)**2 for r in returns)/len(returns))
        sharpe = (avg_r/std_r)*math.sqrt(365*96) if std_r > 0 else 0
        peak = equity[0]; max_dd = 0.0
        for e in equity:
            if e > peak: peak = e
            dd = (peak-e)/peak*100
            if dd > max_dd: max_dd = dd
        state["sharpe_ratio"]     = round(sharpe, 2)
        state["max_drawdown_pct"] = round(max_dd, 4)

    log.info(f"  Stats backfilled: WR={wl['wins']}/{wl['wins']+wl['losses']} fee_net=${real_pnl:.4f} sharpe={state.get('sharpe_ratio','?')}")

if __name__ == "__main__":
    run()
