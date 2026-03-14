# Zerovant Claw — AI Grid Trading Bot

Automated grid trading bot with AI decision engine running on Binance.

## Live Dashboard
https://zerovantclaw.xyz

## Performance (14-Day Testnet)
- Net PnL: +$117.86 (+23.6% ROI)
- Win Rate: 65.7% (620W / 323L)
- Sharpe Ratio: 27.27
- Max Drawdown: 4.10%
- Total Fills: 2,219
- Per Day: $8.42/day

## Asset Allocation
| Asset | Allocation | Win Rate | Profit Factor |
|-------|-----------|----------|---------------|
| ETH/USDT | 70% | 80.9% | 12.67 |
| BNB/USDT | 20% | 69.6% | 3.70 |
| SOL/USDT | 10% | 57.3% | 1.64 |

## Features
- AI decision engine (Venice AI + rule-based fallback)
- Multi-asset grid trading (ETH, BNB, SOL)
- Auto-rebalance by performance score
- Daily compound (50% of net profit)
- Per-asset stop loss (15%, 4h cooldown)
- Trailing stop (3% gain trigger)
- Flash crash protection (8% drop detection)
- Balance change detection (auto pause/adjust)
- Telegram notifications
- Auto data backup (every 30 min to GitHub)
- 3-layer state restore on restart

## Stack
- Python 3.12
- Binance API (Spot)
- Venice AI / Anthropic Claude (AI decisions)
- Telegram Bot API
- systemd service

## Environment Variables
```
BINANCE_MAINNET_API_KEY=
BINANCE_MAINNET_SECRET=
BINANCE_MODE=mainnet
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
VENICE_API_KEY=
ANTHROPIC_API_KEY=
```

## Services
```
zerovant-grid.service    — Main trading bot
zerovant-tgbot.service   — Telegram command bot
zerovant-watchdog.service — Auto-restart watchdog
```

## Dashboard
Live dashboard at https://zerovantclaw.xyz built with vanilla JS, fetches data from `/api/state` endpoint served by Nginx.

## SaaS
Available as a service at https://app.zerovantclaw.xyz — $10/month.

## License
Private — All rights reserved
