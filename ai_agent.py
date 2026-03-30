#!/usr/bin/env python3
"""
Zerovant Claw — Full Autonomous AI Agent
Uses Claude to make all trading decisions
"""
import os, json, requests, time
from datetime import datetime, timezone
from urllib.parse import urlencode
import hmac, hashlib

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VENICE_API_KEY    = os.environ.get("VENICE_API_KEY", "")

# ── DATA COLLECTORS ──────────────────────────────────────

def get_price_data(symbols=["ETHUSDT","TAOUSDT","BTCUSDT","SOLUSDT"]):
    """Get price + OHLCV + indicators"""
    data = {}
    for sym in symbols:
        try:
            # Price
            r = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                params={"symbol": sym}, timeout=5)
            t = r.json()

            # Klines 4h (last 48)
            kr = requests.get("https://api.binance.com/api/v3/klines",
                params={"symbol": sym, "interval": "4h", "limit": 48}, timeout=5)
            klines = kr.json()
            closes = [float(k[4]) for k in klines]
            highs  = [float(k[2]) for k in klines]
            lows   = [float(k[3]) for k in klines]
            vols   = [float(k[5]) for k in klines]

            # Indicators
            ma20 = sum(closes[-20:]) / 20
            std20 = (sum((x-ma20)**2 for x in closes[-20:]) / 20) ** 0.5
            bb_upper = ma20 + 2*std20
            bb_lower = ma20 - 2*std20
            bb_width = (bb_upper - bb_lower) / ma20

            # RSI 14
            gains = [max(closes[i]-closes[i-1],0) for i in range(1,15)]
            losses = [max(closes[i-1]-closes[i],0) for i in range(1,15)]
            avg_gain = sum(gains)/14; avg_loss = sum(losses)/14
            rsi = 100 - (100/(1+avg_gain/avg_loss)) if avg_loss > 0 else 100

            # ATR
            atrs = [highs[i]-lows[i] for i in range(len(klines))]
            atr_pct = (sum(atrs[-14:])/14) / closes[-1] * 100

            # Volume trend
            vol_trend = sum(vols[-8:])/sum(vols[-16:-8]) if sum(vols[-16:-8]) > 0 else 1

            data[sym] = {
                "price": float(t["lastPrice"]),
                "change_24h": float(t["priceChangePercent"]),
                "volume_24h_m": round(float(t["quoteVolume"])/1_000_000, 1),
                "rsi": round(rsi, 1),
                "bb_width": round(bb_width, 4),
                "atr_pct": round(atr_pct, 2),
                "vol_trend": round(vol_trend, 2),
                "ma20": round(ma20, 2),
                "price_vs_ma": round((float(t["lastPrice"])-ma20)/ma20*100, 2),
            }
        except Exception as e:
            data[sym] = {"error": str(e)}
    return data

def get_fear_greed():
    """Fear & Greed Index"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except:
        return {"value": 50, "label": "Neutral"}

def get_crypto_news(limit=5):
    """Latest crypto news via RSS"""
    try:
        r = requests.get(
            "https://cryptopanic.com/api/v1/posts/?auth_token=pub_free&kind=news&currencies=ETH,BTC&limit=10",
            timeout=8)
        posts = r.json().get("results", [])[:limit]
        return [{"title": p["title"], "sentiment": p.get("votes",{}).get("positive",0) - p.get("votes",{}).get("negative",0)}
                for p in posts]
    except:
        # Fallback ke RSS
        try:
            r = requests.get("https://cointelegraph.com/rss", timeout=5)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.text)
            items = root.findall(".//item")[:limit]
            return [{"title": item.find("title").text, "sentiment": 0} for item in items]
        except:
            return []

def get_funding_rates(symbols=["ETHUSDT","BTCUSDT"]):
    """Funding rates dari Binance Futures"""
    rates = {}
    for sym in symbols:
        try:
            r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": sym}, timeout=5)
            d = r.json()
            rates[sym] = round(float(d.get("lastFundingRate", 0)) * 100, 4)
        except:
            rates[sym] = 0
    return rates

def get_portfolio_context(state):
    """Extract relevant portfolio context dari state"""
    fills = state.get("fills_log", [])
    recent = fills[-20:] if fills else []

    # Recent PnL trend
    recent_pnl = sum(float(f.get("pnl",0)) for f in recent if f.get("pnl"))

    # Per-asset performance
    asset_stats = {}
    for f in fills[-100:]:
        sym = f.get("symbol","")
        if not sym: continue
        if sym not in asset_stats:
            asset_stats[sym] = {"fills": 0, "pnl": 0, "wins": 0}
        asset_stats[sym]["fills"] += 1
        pnl = float(f.get("pnl", 0))
        asset_stats[sym]["pnl"] += pnl
        if pnl > 0: asset_stats[sym]["wins"] += 1

    return {
        "total_capital": state.get("total_capital", 0),
        "start_capital": state.get("start_capital", 0),
        "net_pnl": float(state.get("fee_simulation",{}).get("simulated_pnl", 0)),
        "total_fills": state.get("total_fills", 0),
        "win_rate": state.get("win_loss",{}).get("wins",0) / max(state.get("total_fills",1),1) * 100,
        "recent_pnl_20": round(recent_pnl, 4),
        "asset_stats": asset_stats,
        "current_pairs": {sym: cfg.get("capital",0) for sym, cfg in
                         state.get("grids",{}).items() if cfg.get("capital",0) > 0},
    }

# ── AI DECISION ENGINE ───────────────────────────────────

def ai_agent_decide(state, available_symbols=None):
    """
    Full autonomous AI decision via Claude.
    Returns complete trading plan.
    """
    if not ANTHROPIC_API_KEY:
        return _fallback_decision(state)

    if available_symbols is None:
        available_symbols = ["ETHUSDT","TAOUSDT","BTCUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]

    # Collect all data
    price_data   = get_price_data(available_symbols)
    fear_greed   = get_fear_greed()
    news         = get_crypto_news(5)
    funding      = get_funding_rates(["ETHUSDT","BTCUSDT"])
    portfolio    = get_portfolio_context(state)

    # Build prompt
    prompt = f"""You are an autonomous crypto grid trading AI agent managing a real portfolio.
Make optimal trading decisions based on all available data.

## PORTFOLIO STATE
Total Capital: ${portfolio['total_capital']}
Start Capital: ${portfolio['start_capital']}
Net PnL: ${portfolio['net_pnl']:+.2f}
Win Rate: {portfolio['win_rate']:.1f}%
Total Fills: {portfolio['total_fills']}
Recent PnL (last 20 fills): ${portfolio['recent_pnl_20']:+.4f}
Current Pairs: {json.dumps(portfolio['current_pairs'])}
Asset Performance (last 100 fills): {json.dumps(portfolio['asset_stats'], indent=2)}

## MARKET DATA
{json.dumps(price_data, indent=2)}

## SENTIMENT
Fear & Greed Index: {fear_greed['value']}/100 ({fear_greed['label']})
Funding Rates: {json.dumps(funding)}

## LATEST NEWS
{chr(10).join([f"- {n['title']} (sentiment: {'+' if n['sentiment']>0 else ''}{n['sentiment']})" for n in news])}

## YOUR TASK
Analyze all data and return a JSON trading plan with these exact fields:
{{
  "reasoning": "brief explanation of key factors",
  "market_condition": "BULLISH|BEARISH|SIDEWAYS|VOLATILE",
  "pairs": [
    {{
      "symbol": "ETHUSDT",
      "capital_pct": 0.6,
      "num_grids": 10,
      "range_pct": 0.08,
      "action": "TRADE|PAUSE|SKIP",
      "reason": "why"
    }}
  ],
  "risk_level": "LOW|MEDIUM|HIGH",
  "alert": null
}}

Rules:
- Max 2 active pairs
- Capital must sum to 1.0 across active pairs
- If market is BEARISH with fear<30, consider PAUSE for all
- Choose pairs with highest volume AND suitable volatility for grid trading
- range_pct between 0.05-0.15 based on ATR
- num_grids between 8-15 based on volatility
- Return ONLY valid JSON, no markdown"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        text = r.json()["content"][0]["text"]
        # Clean and parse
        text = text.strip().replace("```json","").replace("```","").strip()
        decision = json.loads(text)
        decision["source"] = "claude"
        decision["ts"] = datetime.now(timezone.utc).isoformat()
        return decision
    except Exception as e:
        print(f"AI agent error: {e}")
        return _fallback_decision(state)

def _fallback_decision(state):
    """Fallback ke pair scanner jika AI tidak available"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("pair_scanner",
            os.path.join(os.path.dirname(__file__), "pair_scanner.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        best = mod.scan_best_pairs(top_n=2)
    except:
        best = [{"symbol":"ETHUSDT"},{"symbol":"TAOUSDT"}]

    total = float(state.get("total_capital", 100))
    return {
        "reasoning": "AI unavailable, using pair scanner fallback",
        "market_condition": "SIDEWAYS",
        "pairs": [
            {"symbol": best[0]["symbol"], "capital_pct": 0.6,
             "num_grids": 10, "range_pct": 0.08, "action": "TRADE", "reason": "top scored"},
            {"symbol": best[1]["symbol"], "capital_pct": 0.4,
             "num_grids": 10, "range_pct": 0.08, "action": "TRADE", "reason": "top scored"},
        ],
        "risk_level": "MEDIUM",
        "alert": None,
        "source": "fallback",
        "ts": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    import json as _json
    print("Testing AI Agent...")

    # Test data collection
    print("\n[1] Fear & Greed:", get_fear_greed())
    print("\n[2] Funding rates:", get_funding_rates())
    print("\n[3] News:")
    for n in get_crypto_news(3):
        print(f"  - {n['title'][:60]}")

    print("\n[4] Price data (ETH):")
    pd = get_price_data(["ETHUSDT"])
    print(_json.dumps(pd["ETHUSDT"], indent=2))

    print("\n[5] AI Decision (no state):")
    decision = ai_agent_decide({
        "total_capital": 413,
        "start_capital": 500,
        "fee_simulation": {"simulated_pnl": -47},
        "total_fills": 100,
        "win_loss": {"wins": 45},
        "fills_log": [],
        "grids": {}
    })
    print(_json.dumps(decision, indent=2))
