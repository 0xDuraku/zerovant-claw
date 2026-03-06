import os, json, time, requests, logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv('/root/zerovantclaw/.env')

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = str(os.environ.get("TELEGRAM_CHAT_ID", ""))
STATE_FILE = "/root/zerovantclaw/data/grid_state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

def send(text, reply_markup=None):
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json=payload, timeout=8)
    except Exception as e:
        log.error(f"send error: {e}")

def edit(chat_id, msg_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": msg_id,
               "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/editMessageText",
                      json=payload, timeout=8)
    except:
        pass

def answer_callback(callback_id, text=""):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
                      json={"callback_query_id": callback_id, "text": text}, timeout=5)
    except:
        pass

def load_state():
    try:
        return json.load(open(STATE_FILE))
    except:
        return {}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2, default=str)

def set_menu_button():
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/setChatMenuButton",
                      json={"chat_id": CHAT_ID,
                            "menu_button": {"type": "commands"}}, timeout=8)
        requests.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands",
                      json={"commands": [
                          {"command": "menu",    "description": "Menu utama"},
                          {"command": "status",  "description": "Status & PnL"},
                          {"command": "grids",   "description": "Status semua grid"},
                          {"command": "stop",    "description": "Emergency stop"},
                          {"command": "start",   "description": "Resume bot"},
                          {"command": "pause",   "description": "Pause trading"},
                          {"command": "resume",  "description": "Resume trading"},
                          {"command": "report",  "description": "Daily report sekarang"},
                      ]}, timeout=8)
    except Exception as e:
        log.error(f"menu button error: {e}")

# ── KEYBOARD LAYOUTS ─────────────────────────────────

MAIN_MENU_KB = {"inline_keyboard": [
    [{"text": "\U0001f4ca Status",    "callback_data": "cb_status"},
     {"text": "\U0001f4c8 Grids",     "callback_data": "cb_grids"}],
    [{"text": "\U0001f4b0 PnL Detail","callback_data": "cb_pnl"},
     {"text": "\U0001f916 AI Log",    "callback_data": "cb_ailog"}],
    [{"text": "\u2699 Controls",      "callback_data": "cb_controls"},
     {"text": "\U0001f4c5 History",   "callback_data": "cb_history"}],
    [{"text": "\U0001f4b9 Compound",  "callback_data": "cb_compound"},
     {"text": "\U0001f504 Refresh",   "callback_data": "cb_refresh_main"}],
]}

CONTROLS_KB = {"inline_keyboard": [
    [{"text": "\u23f8 Pause All",      "callback_data": "cb_pause"},
     {"text": "\u25b6 Resume All",     "callback_data": "cb_resume"}],
    [{"text": "\U0001f6d1 EMERGENCY STOP", "callback_data": "cb_stop"}],
    [{"text": "\U0001f7e2 Start Bot",      "callback_data": "cb_startbot"}],
    [{"text": "\u25c0 Back",               "callback_data": "cb_main"}],
]}

CONFIRM_STOP_KB = {"inline_keyboard": [
    [{"text": "\u2705 YA, STOP SEMUA", "callback_data": "cb_confirm_stop"},
     {"text": "\u274c Batal",          "callback_data": "cb_controls"}],
]}

BACK_KB = {"inline_keyboard": [
    [{"text": "\U0001f504 Refresh",    "callback_data": "cb_refresh_back"},
     {"text": "\u25c0 Main Menu",      "callback_data": "cb_main"}],
]}

# ── MESSAGE BUILDERS ─────────────────────────────────

def build_status():
    s      = load_state()
    fs     = s.get("fee_simulation", {})
    wl     = s.get("win_loss", {})
    wins   = wl.get("wins", 0)
    losses = wl.get("losses", 0)
    wr     = wins / (wins + losses) * 100 if wins + losses > 0 else 0
    net    = float(fs.get("simulated_pnl", 0))
    gross  = float(fs.get("gross_pnl", 0))
    fills  = s.get("total_fills", 0)
    sharpe = float(s.get("sharpe_ratio", 0))
    capital = 500
    balance = capital + net
    # Hitung today PnL langsung dari state
    realized   = float(s.get("realized_pnl", 0))
    day_start  = float(s.get("daily_start_pnl", realized))
    today      = round(realized - day_start, 4)
    today_net  = round(today * 0.85, 4)  # estimasi setelah fee
    active = sum(1 for g in s.get("grids", {}).values() if g.get("active"))
    es     = s.get("emergency_stop", False)
    wib    = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M WIB")

    if es:
        status_icon = "\U0001f6d1"
    elif active == 5:
        status_icon = "\U0001f7e2"
    else:
        status_icon = "\U0001f7e1"

    return (
        f"{status_icon} <b>ZEROVANT CLAW STATUS</b>\n"
        f"\U0001f550 {wib}\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f4b0 <b>Balance: ${balance:.2f}</b> (NET est)\n"
        f"\U0001f4c8 All-time Net: <b>${net:+.4f}</b> ({net/capital*100:+.2f}%)\n"
        f"\U0001f4c5 Today: ${today:+.4f} gross | ${today_net:+.4f} net\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f3af Win Rate: <b>{wr:.1f}%</b> ({wins}W/{losses}L)\n"
        f"\U0001f4ca Sharpe: {sharpe:.2f}\n"
        f"\u26a1 Total Fills: {fills:,}\n"
        f"\U0001f7e2 Active Grids: {active}/5\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        + ("\U0001f6d1 EMERGENCY STOP ACTIVE" if es else "\u2705 Bot running normally")
    )

def build_grids():
    s      = load_state()
    grids  = s.get("grids", {})
    prices = s.get("last_prices", {})
    lines  = ["\U0001f4c8 <b>ACTIVE GRIDS</b>\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"]
    for sym in ["ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]:
        g      = grids.get(sym, {})
        active = g.get("active", False)
        icon   = "\U0001f7e2" if active else "\U0001f534"
        price  = prices.get(sym, 0)
        rl     = g.get("range_low", 0)
        rh     = g.get("range_high", 0)
        fills  = g.get("fills", 0)
        pnl    = g.get("realized_pnl", 0)
        orders = g.get("open_orders", 0)
        short  = sym.replace("USDT", "")
        pos_pct = (price - rl) / (rh - rl) * 100 if rh > rl else 0
        bar_filled = int(pos_pct / 10)
        bar = "\u2588" * bar_filled + "\u2591" * (10 - bar_filled)
        lines.append(
            f"{icon} <b>{short}</b> ${price:,.4f}\n"
            f"   [{bar}] {pos_pct:.0f}%\n"
            f"   Range: ${rl:.4f} - ${rh:.4f}\n"
            f"   Fills: {fills} | PnL: ${pnl:+.4f} | Orders: {orders}"
        )
    return "\n".join(lines)

def build_pnl():
    s         = load_state()
    asset_pnl = s.get("asset_pnl", {})
    fs        = s.get("fee_simulation", {})
    gross     = float(fs.get("gross_pnl", 0))
    net       = float(fs.get("simulated_pnl", 0))
    fee       = gross - net
    lines = ["\U0001f4b0 <b>PnL BREAKDOWN</b>\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"]
    lines.append(f"Gross: <b>${gross:+.4f}</b>")
    lines.append(f"Fee est: -${abs(fee):.4f}")
    lines.append(f"Net: <b>${net:+.4f}</b>")
    lines.append("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    lines.append("<b>Per Asset:</b>")
    FEE_RATE = 0.001
    fills_log = s.get("fills_log", [])
    for sym in ["ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]:
        g     = float(asset_pnl.get(sym, 0))
        sf    = [f for f in fills_log if f.get("symbol") == sym and f.get("side") == "SELL"]
        f_amt = sum(float(x.get("price", 0)) * float(x.get("qty", 0)) * FEE_RATE * 2 for x in sf)
        n     = g - f_amt
        icon  = "\U0001f7e2" if g >= 0 else "\U0001f534"
        short = sym.replace("USDT", "")
        lines.append(f"{icon} {short}: ${g:+.4f} gross | ${n:+.4f} net")
    return "\n".join(lines)

def build_history():
    s     = load_state()
    hist  = s.get("daily_pnl_history", {})
    snap  = s.get("today_snapshot", {}) or {}
    lines = ["\U0001f4c5 <b>DAILY PnL HISTORY</b>\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"]
    for date in sorted(hist.keys()):
        d     = hist[date]
        pnl   = float(d.get("pnl", 0))
        fills = d.get("fills", 0)
        icon  = "\U0001f7e2" if pnl >= 0 else "\U0001f534"
        lines.append(f"{icon} {date}: <b>${pnl:+.4f}</b> ({fills} fills)")
    if snap:
        today_pnl = float(snap.get("pnl", 0))
        icon = "\U0001f7e2" if today_pnl >= 0 else "\U0001f534"
        lines.append(f"{icon} TODAY LIVE: <b>${today_pnl:+.4f}</b> ({snap.get('fills', 0)} fills)")
    return "\n".join(lines)

def build_ailog():
    s    = load_state()
    logs = s.get("ai_log", [])[-8:]
    lines = ["\U0001f916 <b>AI LOG (latest 8)</b>\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"]
    for entry in reversed(logs):
        action = entry.get("action", "")
        sym    = entry.get("symbol", "")
        reason = entry.get("reason", "")[:60]
        if action == "REBALANCE":
            icon = "\U0001f504"
        elif action == "CANCEL":
            icon = "\u23f9"
        else:
            icon = "\u2139"
        lines.append(f"{icon} <b>{sym}</b>: {action}\n   {reason}")
    return "\n".join(lines) if logs else "No AI log yet"

# ── ACTIONS ──────────────────────────────────────────


def build_compound():
    s  = load_state()
    lc = s.get("last_compound", {})
    caps = s.get("grid_capitals", {
        "ETHUSDT": 80, "SOLUSDT": 110, "BNBUSDT": 60,
        "DOGEUSDT": 150, "XRPUSDT": 100
    })
    lc_caps = s.get("last_compound", {}).get("capitals")
    if lc_caps:
        caps = lc_caps
    total    = s.get("total_capital", sum(caps.values()))
    gained   = total - 500
    net_pnl  = float(s.get("fee_simulation", {}).get("simulated_pnl", 0))
    SEP = "─" * 20
    lines = ["💹 <b>COMPOUND INFO</b>", SEP]
    lines.append(f"Base capital: <b>$500.00</b>")
    lines.append(f"Current total: <b>${total:.2f}</b> (+${gained:.2f})")
    lines.append(f"Compound rate: 50% of net profit")
    lines.append(f"Net PnL: <b>${net_pnl:+.4f}</b>")
    if lc:
        lines.append(SEP)
        lines.append(f"Last compound: <b>+${lc.get('amount',0):.2f}</b>")
        lines.append(f"From profit: ${lc.get('net_pnl',0):.4f}")
        lines.append(f"New total after: ${lc.get('new_total',0):.2f}")
    lines.append(SEP)
    lines.append("<b>Capital per asset:</b>")
    for sym in ["ETHUSDT","SOLUSDT","BNBUSDT","DOGEUSDT","XRPUSDT"]:
        cap   = float(caps.get(sym, 0))
        short = sym.replace("USDT","")
        pct   = cap / total * 100 if total > 0 else 0
        lines.append(f"  {short}: <b>${cap:.2f}</b> ({pct:.1f}%)")
    lines.append(SEP)
    next_c = max(0, net_pnl * 0.5)
    lines.append(f"Next compound est: <b>+${next_c:.2f}</b>")
    lines.append("Runs at 00:00 WIB daily")
    return "\n".join(lines)

def do_pause():
    s = load_state()
    for sym in list(s.get("grids", {}).keys()):
        s["grids"][sym]["active"] = False
        s["grids"][sym]["reason"] = "manual_pause"
    save_state(s)

def do_resume():
    s = load_state()
    s["emergency_stop"] = False
    for sym in list(s.get("grids", {}).keys()):
        s["grids"][sym]["active"] = True
        s["grids"][sym]["reason"] = "manual_resume"
    s["last_ai_check"] = None
    save_state(s)

def do_stop():
    import subprocess
    s = load_state()
    subprocess.run(["systemctl", "stop", "zerovant-grid.service"])
    for sym in list(s.get("grids", {}).keys()):
        s["grids"][sym]["active"] = False
        s["grids"][sym]["reason"] = "emergency_stop"
    s["emergency_stop"] = True
    save_state(s)

def do_startbot():
    import subprocess
    s = load_state()
    subprocess.run(["systemctl", "start", "zerovant-grid.service"])
    s["emergency_stop"] = False
    for sym in list(s.get("grids", {}).keys()):
        s["grids"][sym]["active"] = True
        s["grids"][sym]["reason"] = "manual_start"
    s["last_ai_check"] = None
    save_state(s)

# ── COMMAND & CALLBACK HANDLERS ──────────────────────

def handle_command(text):
    cmd = text.lower().split()[0]
    if cmd in ("/start", "/menu"):
        send("\U0001f916 <b>ZEROVANT CLAW</b>\nPilih menu:", MAIN_MENU_KB)
    elif cmd == "/status":
        send(build_status(), BACK_KB)
    elif cmd == "/grids":
        send(build_grids(), BACK_KB)
    elif cmd == "/stop":
        send("\u26a0 <b>Konfirmasi Emergency Stop?</b>\nSemua grid akan dibatalkan!", CONFIRM_STOP_KB)
    elif cmd == "/pause":
        do_pause()
        send("\u23f8 <b>Bot PAUSED</b>\nSemua grid dihentikan sementara.", BACK_KB)
    elif cmd == "/resume":
        do_resume()
        send("\u25b6 <b>Bot RESUMED</b>\nSemua grid aktif kembali.", BACK_KB)
    elif cmd == "/report":
        send(build_status(), BACK_KB)
    elif cmd == "/compound":
        send(build_compound(), BACK_KB)
    elif cmd == "/help":
        send(
            "\U0001f916 <b>ZEROVANT CLAW COMMANDS</b>\n\n"
            "/menu - Menu utama\n"
            "/status - Status & PnL\n"
            "/grids - Status semua grid\n"
            "/stop - Emergency stop\n"
            "/pause - Pause sementara\n"
            "/resume - Resume trading\n"
            "/report - Daily report\n"
            "/help - Bantuan ini",
            BACK_KB
        )

def handle_callback(callback_id, data, chat_id, msg_id):
    answer_callback(callback_id)
    if data in ("cb_main", "cb_refresh_main"):
        edit(chat_id, msg_id, "\U0001f916 <b>ZEROVANT CLAW</b>\nPilih menu:", MAIN_MENU_KB)
    elif data == "cb_status":
        edit(chat_id, msg_id, build_status(), BACK_KB)
    elif data == "cb_grids":
        edit(chat_id, msg_id, build_grids(), BACK_KB)
    elif data == "cb_pnl":
        edit(chat_id, msg_id, build_pnl(), BACK_KB)
    elif data == "cb_ailog":
        edit(chat_id, msg_id, build_ailog(), BACK_KB)
    elif data == "cb_history":
        edit(chat_id, msg_id, build_history(), BACK_KB)
    elif data == "cb_controls":
        edit(chat_id, msg_id, "\u2699 <b>BOT CONTROLS</b>\nPilih aksi:", CONTROLS_KB)
    elif data == "cb_refresh_back":
        edit(chat_id, msg_id, build_status(), BACK_KB)
    elif data == "cb_pause":
        do_pause()
        edit(chat_id, msg_id, "\u23f8 <b>Bot PAUSED</b>\nSemua grid dihentikan.", CONTROLS_KB)
    elif data == "cb_resume":
        do_resume()
        edit(chat_id, msg_id, "\u25b6 <b>Bot RESUMED</b>\nSemua grid aktif kembali.", CONTROLS_KB)
    elif data == "cb_stop":
        edit(chat_id, msg_id, "\u26a0 <b>Konfirmasi Emergency Stop?</b>\nSemua grid akan dibatalkan!", CONFIRM_STOP_KB)
    elif data == "cb_confirm_stop":
        do_stop()
        edit(chat_id, msg_id, "\U0001f6d1 <b>EMERGENCY STOP EXECUTED</b>\nBot service dihentikan.", CONTROLS_KB)
    elif data == "cb_compound":
        edit(chat_id, msg_id, build_compound(), BACK_KB)
    elif data == "cb_startbot":
        do_startbot()
        edit(chat_id, msg_id, "\U0001f7e2 <b>BOT STARTED</b>\nService dimulai ulang.", CONTROLS_KB)

# ── MAIN POLLING LOOP ────────────────────────────────

def main():
    set_menu_button()
    send("\U0001f916 <b>ZEROVANT CLAW Bot</b> online!\nKetik /menu untuk mulai.", MAIN_MENU_KB)
    log.info("Telegram bot started, polling every 2s...")
    offset = 0
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30, "limit": 10},
                timeout=35
            )
            updates = r.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                if msg:
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    if chat_id != CHAT_ID:
                        continue
                    text = msg.get("text", "")
                    if text.startswith("/"):
                        handle_command(text)
                cb = upd.get("callback_query", {})
                if cb:
                    chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                    if chat_id != CHAT_ID:
                        continue
                    handle_callback(
                        cb["id"],
                        cb.get("data", ""),
                        chat_id,
                        cb.get("message", {}).get("message_id")
                    )
        except Exception as e:
            log.error(f"Poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
