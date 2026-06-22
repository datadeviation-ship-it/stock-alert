"""
stock_alert.py

CILJ:
- Provjeravati open price nakon otvaranja USA burze.
- Provjera traje od 09:30 ET do 15:00 ET.
- Alarm se šalje samo ako je:
    1) prethodni trading day close >= zadana razina
    2) današnji open >= zadana razina

NEMA:
- prethodnog high uvjeta
- G2/G3 logike
- dodatnog praga 0.5 %
- status poruke ako nema alarma
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime, date, timedelta, time as dtime
import zoneinfo


# ============================================================
# ENV
# ============================================================

FMP_API_KEY = os.environ.get("FMP_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


# ============================================================
# SETTINGS
# ============================================================

ET = zoneinfo.ZoneInfo("America/New_York")
ZAGREB = zoneinfo.ZoneInfo("Europe/Zagreb")

# Provjera od otvaranja USA burze do sat vremena prije zatvaranja.
# 09:30–15:00 ET
# Ljeti je to 15:30–21:00 Zagreb.
# Zimi je to također 15:30–21:00 Zagreb, dok su SAD i Europa usklađeni,
# ali postoje prijelazni tjedni zbog različitih datuma promjene vremena.
MARKET_OPEN = dtime(9, 30)
LAST_OPEN_CHECK = dtime(15, 0)

TELEGRAM_MAX_LEN = 3500

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "stock_alert_poslano.json"
)


# ============================================================
# DIONICE
# ============================================================

DIONICE = [
    {"ticker": "NBIS", "razina": 279.50},
    {"ticker": "UPS", "razina": 110.50},
    {"ticker": "LRCX", "razina": 393.50},
    {"ticker": "PGR", "razina": 207.00},
    {"ticker": "MCD", "razina": 288.50},
    {"ticker": "GOOGL", "razina": 373.50},
    {"ticker": "GD", "razina": 367.50},
    {"ticker": "SEI", "razina": 79.00},
    {"ticker": "CX", "razina": 13.40},
    {"ticker": "BHP", "razina": 93.00},
    {"ticker": "BE", "razina": 303.50},
    {"ticker": "CRS", "razina": 564.00},
    {"ticker": "DAVE", "razina": 309.00},
    {"ticker": "DGII", "razina": 68.60},
    {"ticker": "EGO", "razina": 38.20},
    {"ticker": "EVRG", "razina": 84.50},
    {"ticker": "EMR", "razina": 152.60},
    {"ticker": "AMD", "razina": 527.80},
    {"ticker": "FCX", "razina": 70.30},
    {"ticker": "FDX", "razina": 338.00},
    {"ticker": "FRO", "razina": 39.50},
    {"ticker": "FTNT", "razina": 148.80},
    {"ticker": "IVZ", "razina": 29.50},
    {"ticker": "NVS", "razina": 152.50},
    {"ticker": "POWL", "razina": 310.00},
    {"ticker": "CYTK", "razina": 78.70},
    {"ticker": "FPS", "razina": 63.00},
    {"ticker": "OC", "razina": 128.50},
    {"ticker": "ENTG", "razina": 159.50},
    {"ticker": "SIMO", "razina": 294.00},
    {"ticker": "GRMN", "razina": 244.00},
    {"ticker": "TER", "razina": 422.00},
    {"ticker": "TRV", "razina": 311.00},
    {"ticker": "ARM", "razina": 412.00},
    {"ticker": "AGX", "razina": 728.00},
    {"ticker": "CEG", "razina": 273.00},
    {"ticker": "OSCR", "razina": 29.15},
    {"ticker": "CAT", "razina": 942.00},
    {"ticker": "VMC", "razina": 303.00},
    {"ticker": "DOCN", "razina": 181.00},
    {"ticker": "VDC", "razina": 687.00},
    {"ticker": "STX", "razina": 1030.00},
    {"ticker": "NN", "razina": 23.55},
    {"ticker": "BAP", "razina": 375.00},
    {"ticker": "AYA", "razina": 21.50},
]


# ============================================================
# DEBUG
# ============================================================

def debug_env():
    print("ENV provjera:")
    print(f"  FMP_API_KEY exists:      {bool(FMP_API_KEY)}")
    print(f"  TELEGRAM_TOKEN exists:   {bool(TELEGRAM_TOKEN)}")
    print(f"  TELEGRAM_CHAT_ID exists: {bool(TELEGRAM_CHAT_ID)}")
    print("  Stvarne vrijednosti tokena se ne ispisuju.")
    print()


# ============================================================
# US TRADING CALENDAR
# ============================================================

def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    count = 0

    while True:
        if d.weekday() == weekday:
            count += 1
            if count == n:
                return d

        d += timedelta(days=1)


def _last_weekday(year, month, weekday):
    if month < 12:
        d = date(year, month + 1, 1) - timedelta(days=1)
    else:
        d = date(year, 12, 31)

    while d.weekday() != weekday:
        d -= timedelta(days=1)

    return d


def us_holidays(year):
    def obs(d):
        if d.weekday() == 6:
            return d + timedelta(days=1)

        if d.weekday() == 5:
            return d - timedelta(days=1)

        return d

    h = set()

    h.add(obs(date(year, 1, 1)))          # New Year
    h.add(_nth_weekday(year, 1, 0, 3))    # Martin Luther King Jr. Day
    h.add(_nth_weekday(year, 2, 0, 3))    # Presidents' Day

    # Good Friday calculation
    a = year % 19
    b, c = divmod(year, 100)
    d2, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    hh = (19 * a + b - d2 - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - hh - k) % 7
    m = (a + 11 * hh + 22 * l) // 451
    mo = (hh + l - 7 * m + 114) // 31
    dy = (hh + l - 7 * m + 114) % 31 + 1

    h.add(date(year, mo, dy) - timedelta(days=2))  # Good Friday

    h.add(_last_weekday(year, 5, 0))       # Memorial Day
    h.add(obs(date(year, 6, 19)))          # Juneteenth
    h.add(obs(date(year, 7, 4)))           # Independence Day
    h.add(_nth_weekday(year, 9, 0, 1))     # Labor Day
    h.add(_nth_weekday(year, 11, 3, 4))    # Thanksgiving
    h.add(obs(date(year, 12, 25)))         # Christmas

    return h


def is_trading_day(d):
    return d.weekday() < 5 and d not in us_holidays(d.year)


def previous_trading_day(d):
    d -= timedelta(days=1)

    while not is_trading_day(d):
        d -= timedelta(days=1)

    return d


def market_open_alert_window(now_et=None):
    if now_et is None:
        now_et = datetime.now(ET)

    if not is_trading_day(now_et.date()):
        return False

    current_time = now_et.time()

    return MARKET_OPEN <= current_time <= LAST_OPEN_CHECK


def open_window_text():
    return "09:30–15:00 ET"


# ============================================================
# STATE
# ============================================================

def default_state():
    return {
        "sent_open_alerts": {}
    }


def key_for(ticker, razina):
    return f"{ticker}_{razina:.4f}"


def load_state():
    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return default_state()

        data.setdefault("sent_open_alerts", {})
        return data

    except Exception as e:
        print(f"Ne mogu učitati state file: {e}")
        return default_state()


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def already_sent_today(state, key, today_s):
    sent = state.get("sent_open_alerts", {})
    return today_s in sent.get(key, [])


def mark_sent_today(state, key, today_s):
    state.setdefault("sent_open_alerts", {})
    state["sent_open_alerts"].setdefault(key, [])

    if today_s not in state["sent_open_alerts"][key]:
        state["sent_open_alerts"][key].append(today_s)

    state["sent_open_alerts"][key] = sorted(
        state["sent_open_alerts"][key]
    )[-20:]


# ============================================================
# FMP
# ============================================================

def http_get_json(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_quote(ticker):
    url = (
        "https://financialmodelingprep.com/stable/quote"
        f"?symbol={urllib.parse.quote(ticker)}"
        f"&apikey={FMP_API_KEY}"
    )

    try:
        data = http_get_json(url, timeout=15)

        if not data or not isinstance(data, list):
            return None

        q = data[0]

        open_ = q.get("open")
        price = q.get("price")

        if open_ is None:
            return None

        return {
            "open": float(open_),
            "price": float(price) if price is not None else None,
        }

    except Exception as e:
        print(f"Quote greška {ticker}: {e}")
        return None


def fetch_eod_history(ticker, from_date):
    url = (
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
        f"?symbol={urllib.parse.quote(ticker)}"
        f"&from={from_date.isoformat()}"
        f"&apikey={FMP_API_KEY}"
    )

    try:
        data = http_get_json(url, timeout=20)

        if isinstance(data, dict):
            records = data.get("historical", data.get("data", []))
        elif isinstance(data, list):
            records = data
        else:
            return {}

        result = {}

        for row in records:
            ds = str(row.get("date", ""))[:10]

            if not ds:
                continue

            result[ds] = {
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
            }

        return result

    except Exception as e:
        print(f"Povijest greška {ticker}: {e}")
        return {}


# ============================================================
# TELEGRAM
# ============================================================

def split_message(text, max_len=TELEGRAM_MAX_LEN):
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""

    for line in lines:
        if len(current) + len(line) > max_len:
            if current.strip():
                chunks.append(current)

            current = line
        else:
            current += line

    if current.strip():
        chunks.append(current)

    return chunks


def send_telegram_message(text):
    if not TELEGRAM_TOKEN:
        print("Telegram greška: TELEGRAM_TOKEN nije postavljen.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("Telegram greška: TELEGRAM_CHAT_ID nije postavljen.")
        return False

    params = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        req = urllib.request.Request(url, data=params, method="POST")

        with urllib.request.urlopen(req, timeout=15) as r:
            response = json.loads(r.read())

        if response.get("ok"):
            print("Telegram poruka poslana.")
            return True

        print(f"Telegram greška: {response}")
        return False

    except Exception as e:
        print(f"Telegram greška: {e}")
        return False


def send_long_telegram_message(text):
    chunks = split_message(text)

    print(f"Telegram poruka ima {len(text)} znakova.")
    print(f"Šaljem u {len(chunks)} dijelova.")

    all_ok = True

    for chunk in chunks:
        ok = send_telegram_message(chunk)

        if not ok:
            all_ok = False
            break

    return all_ok


def format_open_alert(alerts, today_s, prev_s):
    now_et = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    now_zg = datetime.now(ZAGREB).strftime("%d.%m.%Y %H:%M Zagreb")

    lines = []
    lines.append("OPEN PRICE ALERT")
    lines.append(now_et)
    lines.append(now_zg)
    lines.append("")
    lines.append(f"Trading day: {today_s}")
    lines.append(f"Prethodni trading day: {prev_s}")
    lines.append("")
    lines.append("Uvjet:")
    lines.append("Prethodni close >= razina")
    lines.append("Današnji open >= razina")
    lines.append("")
    lines.append("Ticker | Razina | Prev close | Open | Open vs razina")

    for a in alerts:
        lines.append(
            f"{a['ticker']} | "
            f"{a['razina']:.2f} | "
            f"{a['prev_close']:.2f} | "
            f"{a['open']:.2f} | "
            f"{a['open_vs_razina_pct']:+.2f}%"
        )

    return "\n".join(lines)


def test_telegram():
    now_et = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    now_zg = datetime.now(ZAGREB).strftime("%d.%m.%Y %H:%M Zagreb")

    text = f"Stock Alert bot aktivan\n{now_et}\n{now_zg}"

    ok = send_telegram_message(text)

    if ok:
        print("Test poruka poslana.")
    else:
        print("Test poruka NIJE poslana.")


# ============================================================
# MAIN LOGIKA
# ============================================================

def provjeri(force=False):
    now_et = datetime.now(ET)
    now_zg = datetime.now(ZAGREB)

    today = now_et.date()
    today_s = today.isoformat()

    print(f"Provjera ET:     {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")
    print(f"Provjera Zagreb: {now_zg.strftime('%d.%m.%Y %H:%M:%S Zagreb')}")
    print(f"State file: {STATE_FILE}")
    debug_env()

    if not FMP_API_KEY:
        print("FMP_API_KEY nije postavljen. Prekid.")
        send_telegram_message(
            "OPEN PRICE ALERT greška: FMP_API_KEY nije postavljen."
        )
        return

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram ENV nije kompletan. Prekid.")
        return

    if not force and not market_open_alert_window(now_et):
        print(
            f"Nije vrijeme za open provjeru. "
            f"Dozvoljeni prozor je {open_window_text()}."
        )
        print("Nema Telegram slanja.")
        return

    if not is_trading_day(today):
        print("Danas nije US trading day. Prekid.")
        return

    prev_day = previous_trading_day(today)
    prev_s = prev_day.isoformat()

    print(f"Trading day: {today_s}")
    print(f"Prethodni trading day: {prev_s}")
    print(f"Alert window: {open_window_text()}")
    print(f"Force mode: {force}")
    print()

    state = load_state()

    alerts = []

    checked = 0
    prev_close_ok_count = 0
    open_ok_count = 0
    missing_prev_eod = 0
    missing_open = 0
    already_sent_count = 0

    history_from = prev_day - timedelta(days=7)

    for item in DIONICE:
        ticker = item["ticker"].strip().upper()
        razina = float(item["razina"])
        k = key_for(ticker, razina)

        if already_sent_today(state, k, today_s):
            already_sent_count += 1
            print(f"{ticker:<8} već poslano danas — preskačem.")
            continue

        checked += 1

        hist = fetch_eod_history(ticker, history_from)
        prev_ohlc = hist.get(prev_s)

        if not prev_ohlc:
            missing_prev_eod += 1
            print(f"{ticker:<8} nema EOD podatke za {prev_s}")
            continue

        prev_close = prev_ohlc.get("close")

        if prev_close is None or prev_close <= 0:
            missing_prev_eod += 1
            print(f"{ticker:<8} nema valjani prethodni close za {prev_s}")
            continue

        prev_close_ok = prev_close >= razina

        if not prev_close_ok:
            print(
                f"{ticker:<8} NE | "
                f"razina={razina:.2f} "
                f"prev_close={prev_close:.2f} "
                f"uvjet_prev_close=NE"
            )
            continue

        prev_close_ok_count += 1

        quote = fetch_quote(ticker)

        if not quote:
            missing_open += 1
            print(
                f"{ticker:<8} prethodni close OK, "
                f"ali nema quote/open podatka."
            )
            continue

        open_today = quote.get("open")

        if open_today is None or open_today <= 0:
            missing_open += 1
            print(
                f"{ticker:<8} prethodni close OK, "
                f"ali današnji open nije dostupan."
            )
            continue

        open_ok = open_today >= razina
        open_vs_razina_pct = (open_today - razina) / razina * 100

        print(
            f"{ticker:<8} "
            f"razina={razina:.2f} "
            f"prev_close={prev_close:.2f} "
            f"open={open_today:.2f} "
            f"open_vs_razina={open_vs_razina_pct:+.2f}% "
            f"ALARM={'DA' if open_ok else 'NE'}"
        )

        if open_ok:
            open_ok_count += 1

            alerts.append({
                "ticker": ticker,
                "razina": razina,
                "prev_close": prev_close,
                "open": open_today,
                "open_vs_razina_pct": open_vs_razina_pct,
            })

            mark_sent_today(state, k, today_s)

    print()
    print(f"Provjereno tickera: {checked}")
    print(f"Prethodni close iznad razine: {prev_close_ok_count}")
    print(f"Današnji open iznad razine: {open_ok_count}")
    print(f"Nema prethodni EOD: {missing_prev_eod}")
    print(f"Nema današnji open: {missing_open}")
    print(f"Već poslano danas: {already_sent_count}")
    print(f"Novi alarmi: {len(alerts)}")
    print()

    if not alerts:
        print("Nema novih open price alarma. Ne šaljem Telegram poruku.")
        save_state(state)
        print("State spremljen.")
        return

    message = format_open_alert(alerts, today_s, prev_s)
    telegram_ok = send_long_telegram_message(message)

    if telegram_ok:
        save_state(state)
        print("State spremljen.")
    else:
        print("Telegram nije uspješno poslan. State se neće spremiti.")
        return

    print(f"Gotovo ET:     {datetime.now(ET).strftime('%H:%M:%S ET')}")
    print(f"Gotovo Zagreb: {datetime.now(ZAGREB).strftime('%H:%M:%S Zagreb')}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import sys

    arg = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""

    if arg == "test":
        test_telegram()

    elif arg == "reset":
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("Resetirano — stock_alert_poslano.json obrisan.")
        else:
            print("Nema što resetirati.")

    elif arg == "debug":
        debug_env()

    elif arg == "force":
        provjeri(force=True)

    else:
        provjeri(force=False)
