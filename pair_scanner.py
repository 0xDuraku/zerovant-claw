#!/usr/bin/env python3
"""
Dynamic Pair Scanner — pilih 2 pair terbaik untuk grid trading
Kriteria: volume tinggi, volatility optimal (1-5%), trend tidak extreme
"""
import requests, json
from datetime import datetime, timezone

def scan_best_pairs(top_n=2, min_vol_m=50, min_vol_pct=0.5, max_vol_pct=8.0):
    # Get 24h tickers
    r = requests.get('https://api.binance.com/api/v3/ticker/24hr', timeout=10)
    tickers = {t['symbol']: t for t in r.json() if t['symbol'].endswith('USDT')}
    
    # Get klines untuk hitung BB width (sideways indicator)
    candidates = []
    for sym, t in tickers.items():
        vol_m = float(t['quoteVolume']) / 1_000_000
        pct = abs(float(t['priceChangePercent']))
        price = float(t['lastPrice'])
        
        # Filter dasar
        if vol_m < min_vol_m: continue
        if pct < min_vol_pct or pct > max_vol_pct: continue
        if price < 0.01: continue
        
        # Skip stablecoins
        if any(s in sym for s in ['USDC','BUSD','TUSD','DAI','FDUSD','USD1']): continue
        
        candidates.append({
            'symbol': sym,
            'price': price,
            'vol_m': round(vol_m, 1),
            'pct_24h': round(float(t['priceChangePercent']), 2),
            'score': 0
        })
    
    # Score each candidate dengan klines
    for c in candidates:
        try:
            # Get 4h klines (48 candles = 8 hari)
            kr = requests.get('https://api.binance.com/api/v3/klines',
                params={'symbol': c['symbol'], 'interval': '4h', 'limit': 48}, timeout=5)
            klines = kr.json()
            if not klines: continue
            
            closes = [float(k[4]) for k in klines]
            highs  = [float(k[2]) for k in klines]
            lows   = [float(k[3]) for k in klines]
            vols   = [float(k[5]) for k in klines]
            
            # BB width (volatility measure)
            ma20 = sum(closes[-20:]) / 20
            std20 = (sum((x-ma20)**2 for x in closes[-20:]) / 20) ** 0.5
            bb_width = (std20 * 2) / ma20
            
            # Volume trend (naik = bagus)
            vol_trend = sum(vols[-8:]) / sum(vols[-16:-8]) if sum(vols[-16:-8]) > 0 else 1
            
            # ATR
            atrs = [highs[i] - lows[i] for i in range(len(klines))]
            atr_pct = (sum(atrs[-14:]) / 14) / closes[-1] * 100
            
            # Score: BB width optimal (0.02-0.08), volume naik, ATR moderate
            score = 0
            if 0.02 <= bb_width <= 0.08: score += 3
            elif 0.01 <= bb_width <= 0.12: score += 1
            if vol_trend > 1.1: score += 2
            if 0.5 <= atr_pct <= 3.0: score += 2
            if c['vol_m'] > 200: score += 2
            elif c['vol_m'] > 100: score += 1
            
            c['score'] = score
            c['bb_width'] = round(bb_width, 4)
            c['atr_pct'] = round(atr_pct, 2)
            c['vol_trend'] = round(vol_trend, 2)
            
        except: continue
    
    # Sort by score
    candidates = [c for c in candidates if c.get('score', 0) > 0]
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return candidates[:top_n]

if __name__ == '__main__':
    print(f"Scanning best pairs... [{datetime.now(timezone.utc).strftime('%H:%M UTC')}]")
    best = scan_best_pairs(top_n=5)
    for i, c in enumerate(best):
        print(f"{i+1}. {c['symbol']:12} score={c['score']} bb={c.get('bb_width','?')} atr={c.get('atr_pct','?')}% vol=${c['vol_m']}M trend={c.get('vol_trend','?')}")
    
    # Save result
    json.dump({'pairs': best, 'ts': datetime.now(timezone.utc).isoformat()},
              open('/root/zerovantclaw/best_pairs.json','w'), indent=2)
    print(f"\nBest 2: {[c['symbol'] for c in best[:2]]}")
