"""
stock_alert.py - G3 open alert 

ŠALJE SAMO GRUPU 3.

CILJ:
- Provjeriti odmah nakon otvaranja USA burze.
- Alarm se šalje samo ako je:
    1) prethodni trading dan imao G2:
       high >= razina * prag
       close >= razina * prag
    2) današnji open je iznad razine/praga:
       open >= razina * prag

Telegram poruka je jednostavna:
Ticker | Razina | Open | Open vs razina

Pokretanje:
  python stock_alert.py
  python stock_alert.py test
  python stock_alert.py reset
  python stock_alert.py debug
  python stock_alert.py force
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime, date, timedelta, time as dtime
import zoneinfo


# ─────────────────────────────────────────────────────────────
# ENV
# ─────────────────────────────────────────────────────────────

FMP_API_KEY = os.environ.get("FMP_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────

# Ako želiš da uvjet bude čista razina bez dodatnog praga, stavi 0.0.
# Trenutno ostavljam 0.5 jer je tako bilo u tvojoj G3 logici.
PRAG_POSTO = 0.5

# Koliko minuta nakon otvaranja USA burze smije poslati alarm.
# 09:30:00 — 09:35:00 ET
OPEN_ALERT_WINDOW_MINUTES = 5

TELEGRAM_MAX_LEN = 3500

ET = zoneinfo.ZoneInfo("America/New_York")

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "stock_alert_poslano.json"
)


# ─────────────────────────────────────────────────────────────
# DIONICE
# ─────────────────────────────────────────────────────────────

DIONICE = [
    {"ticker": "VRSN",  "razina": 310.00},
    {"ticker": "VRNS",  "razina": 36.00},
    {"ticker": "GLNG",  "razina": 57.80},
    {"ticker": "LMT",   "razina": 530.00},
    {"ticker": "APH",   "razina": 118.00},
    {"ticker": "ADP",   "razina": 226.20},
    {"ticker": "AVGO",  "razina": 440.50},
    {"ticker": "DOCN",  "razina": 165.00},
    {"ticker": "NNN",   "razina": 45.80},
    {"ticker": "JNJ",   "razina": 232.00},
    {"ticker": "AAPL",  "razina": 303.00},
    {"ticker": "TTE",   "razina": 94.20},
    {"ticker": "MS",    "razina": 189.60},
    {"ticker": "WMT",   "razina": 135.00},
    {"ticker": "KO",    "razina": 82.00},
    {"ticker": "LRCX",  "razina": 302.00},
    {"ticker": "HEI",   "razina": 301.00},
    {"ticker": "SMCI",  "razina": 36.00},
    {"ticker": "WELL",  "razina": 222.00},
    {"ticker": "GEHC",  "razina": 64.50},
    {"ticker": "APLD",  "razina": 47.80},
    {"ticker": "H",     "razina": 177.50},
    {"ticker": "KLAR",  "razina": 16.80},
    {"ticker": "CSCO",  "razina": 119.50},
    {"ticker": "NVTS",  "razina": 24.20},
    {"ticker": "F",     "razina": 14.85},
    {"ticker": "NOW",   "razina": 106.60},
    {"ticker": "KLAC",  "razina": 1940.00},
    {"ticker": "LEA",   "razina": 141.40},
    {"ticker": "DG",    "razina": 116.60},
    {"ticker": "MET",   "razina": 85.30},
    {"ticker": "VRT",   "razina": 334.60},
    {"ticker": "PAYC",  "razina": 139.30},
    {"ticker": "DOC",   "razina": 19.80},
    {"ticker": "COKE",  "razina": 178.00},
    {"ticker": "SNPS",  "razina": 535.00},
    {"ticker": "SWKS",  "razina": 84.00},
    {"ticker": "SOFI",  "razina": 16.90},
    {"ticker": "ASST",  "razina": 18.25},
    {"ticker": "ANET",  "razina": 165.00},
    {"ticker": "RKLB",  "razina": 139.35},
    {"ticker": "LLY",   "razina": 1110.00},
    {"ticker": "RTX",   "razina": 179.00},
    {"ticker": "SEZL",  "razina": 114.20},
    {"ticker": "AGX",   "razina": 743.00},
    {"ticker": "STM",   "razina": 67.00},
    {"ticker": "RDW",   "razina": 15.50},
    {"ticker": "GRRR",  "razina": 15.80},
    {"ticker": "META",  "razina": 626.00},
]


# ─────────────────────────────────────────────────────────────
# DEBUG
# ─────────────────────────────────────────────────────────────

def debug_env():
    print("ENV provjera:")
    print(f"  FMP_API_KEY exists:      {bool(FMP_API_KEY)}")
    print(f"  TELEGRAM_TOKEN exists:   {bool(TELEGRAM_TOKEN)}")
    print(f"  TELEGRAM_CHAT_ID exists: {bool(TELEGRAM_CHAT_ID)}")
    print("  Stvarne vrijednosti tokena se ne ispisuju.")
    print()


# ─────────────────────────────────────────────────────────────
# TRADING CALENDAR
# ─────────────────────────────────────────────────────────────

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

    h.add(obs(date(year, 1, 1)))
    h.add(_nth_weekday(year, 1, 0, 3))
    h.add(_nth_weekday(year, 2, 0, 3))

    # Good Friday
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

    h.add(date(year, mo, dy) - timedelta(days=2))

    h.add(_last_weekday(year, 5, 0))
    h.add(obs(date(year, 6, 19)))
    h.add(obs(date(year, 7, 4)))
    h.add(_nth_weekday(year, 9, 0, 1))
    h.add(_nth_weekday(year, 11, 3, 4))
    h.add(obs(date(year, 12, 25)))

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

    open_dt = datetime.combine(now_et.date(), dtime(9, 30), tzinfo=ET)
    end_dt = open_dt + timedelta(minutes=OPEN_ALERT_WINDOW_MINUTES)

    return open_dt <= now_et <= end_dt


# ─────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────

def default_state():
    return {
        "sent_g3": {}
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

        data.setdefault("sent_g3", {})

        return data

    except Exception as e:
        print(f"Ne mogu učitati state file: {e}")
        return default_state()


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def already_sent_today(state, key, today_s):
    sent_g3 = state.get("sent_g3", {})
    if today_s in sent_g3.get(key, []):
        return True

    # Kompatibilnost sa starim state formatom ako postoji.
    old_g3 = state.get("g3", {})
    old_item = old_g3.get(key, {})

    if isinstance(old_item, dict):
        old_dates = old_item.get("datumi", [])
        if today_s in old_dates:
            return True

    return False


def mark_sent_today(state, key, today_s):
    state.setdefault("sent_g3", {})
    state["sent_g3"].setdefault(key, [])

    if today_s not in state["sent_g3"][key]:
        state["sent_g3"][key].append(today_s)

    # Čuvaj samo zadnjih 20 zapisa po ticker/razina kombinaciji.
    state["sent_g3"][key] = sorted(state["sent_g3"][key])[-20:]


# ─────────────────────────────────────────────────────────────
# FMP
# ─────────────────────────────────────────────────────────────

def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_quote(ticker):
    url = (
        "https://financialmodelingprep.com/stable/quote"
        f"?symbol={urllib.parse.quote(ticker)}&apikey={FMP_API_KEY}"
    )

    try:
        data = http_get_json(url, timeout=15)

        if not data or not isinstance(data, list):
            return None

        q = data[0]

        price = q.get("price")
        open_ = q.get("open")

        if price is None and open_ is None:
            return None

        return {
            "price": float(price) if price is not None else None,
            "open": float(open_) if open_ is not None else None,
        }

    except Exception as e:
        print(f"  quote greška {ticker}: {e}")
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
        print(f"  povijest greška {ticker}: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────

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


def format_simple_g3_alert(alerts):
    now_et = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")

    lines = []
    lines.append("G3 ALERT — USA OPEN")
    lines.append(now_et)
    lines.append("")
    lines.append("Ticker | Razina | Open | Open vs razina")

    for a in alerts:
        lines.append(
            f"{a['ticker']} | "
            f"{a['razina']:.2f} | "
            f"{a['open']:.2f} | "
            f"{a['open_vs_razina_pct']:+.2f}%"
        )

    return "\n".join(lines)


def send_g3_alerts(alerts):
    if not alerts:
        return False

    message = format_simple_g3_alert(alerts)
    chunks = split_message(message)

    print(f"Telegram poruka ima {len(message)} znakova.")
    print(f"Šaljem u {len(chunks)} dijelova.")

    all_ok = True

    for chunk in chunks:
        ok = send_telegram_message(chunk)

        if not ok:
            all_ok = False
            break

    return all_ok


def test_telegram():
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    text = f"Stock Alert bot aktivan\nTest poruka {now}"

    ok = send_telegram_message(text)

    if ok:
        print("Test poruka poslana.")
    else:
        print("Test poruka NIJE poslana.")


# ─────────────────────────────────────────────────────────────
# MAIN LOGIKA — SAMO G3
# ─────────────────────────────────────────────────────────────

def provjeri(force=False):
    now_et = datetime.now(ET)
    today = now_et.date()
    today_s = today.isoformat()

    print(f"Provjera: {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")
    print(f"State file: {STATE_FILE}")
    debug_env()

    if not FMP_API_KEY:
        print("FMP_API_KEY nije postavljen. Prekid.")
        return

    if not force and not market_open_alert_window(now_et):
        print(
            "Nije vrijeme za G3 open provjeru. "
            f"Bot šalje samo u prvih {OPEN_ALERT_WINDOW_MINUTES} minuta nakon USA opena."
        )
        print("Nema Telegram slanja.")
        return

    if not is_trading_day(today):
        print("Danas nije US trading day. Prekid.")
        return

    prev_day = previous_trading_day(today)
    prev_s = prev_day.isoformat()

    print(f"Trading day: {today_s}")
    print(f"Prethodni trading day za G2: {prev_s}")
    print(f"Alert window: 09:30–09:35 ET")
    print()

    state = load_state()

    alerts = []
    checked = 0
    g2_ok_count = 0
    already_sent_count = 0

    history_from = prev_day - timedelta(days=7)
    prag = 1 + PRAG_POSTO / 100

    for item in DIONICE:
        ticker = item["ticker"].strip().upper()
        razina = float(item["razina"])
        trigger = razina * prag
        k = key_for(ticker, razina)

        if already_sent_today(state, k, today_s):
            already_sent_count += 1
            print(f"{ticker:<8} već poslano danas — preskačem.")
            continue

        checked += 1

        hist = fetch_eod_history(ticker, history_from)
        prev_ohlc = hist.get(prev_s)

        if not prev_ohlc:
            print(f"{ticker:<8} nema EOD podatke za {prev_s}")
            continue

        prev_high = prev_ohlc.get("high")
        prev_close = prev_ohlc.get("close")

        if prev_high is None or prev_close is None:
            print(f"{ticker:<8} nepotpuni EOD podaci za {prev_s}")
            continue

        # G2 uvjet: prethodni dan high + close iznad triggera.
        g2_ok = prev_high >= trigger and prev_close >= trigger

        if not g2_ok:
            print(
                f"{ticker:<8} G2 NE | "
                f"razina={razina:.2f} trigger={trigger:.2f} "
                f"prev_high={prev_high:.2f} prev_close={prev_close:.2f}"
            )
            continue

        g2_ok_count += 1

        quote = fetch_quote(ticker)

        if not quote:
            print(f"{ticker:<8} G2 DA, ali nema quote/open podatka.")
            continue

        open_today = quote.get("open")

        if open_today is None or open_today <= 0:
            print(f"{ticker:<8} G2 DA, ali open nije dostupan.")
            continue

        # G3 uvjet: današnji open iznad triggera.
        g3_ok = open_today >= trigger

        open_vs_razina_pct = (open_today - razina) / razina * 100

        print(
            f"{ticker:<8} G2 DA | "
            f"open={open_today:.2f} razina={razina:.2f} "
            f"open_vs_razina={open_vs_razina_pct:+.2f}% "
            f"G3={'DA' if g3_ok else 'NE'}"
        )

        if g3_ok:
            alerts.append({
                "ticker": ticker,
                "razina": razina,
                "open": open_today,
                "open_vs_razina_pct": open_vs_razina_pct,
            })

            mark_sent_today(state, k, today_s)

    print()
    print(f"Provjereno: {checked}")
    print(f"G2 od jučer: {g2_ok_count}")
    print(f"Već poslano danas: {already_sent_count}")
    print(f"Novi G3 alarmi: {len(alerts)}")
    print()

    if alerts:
        ok = send_g3_alerts(alerts)

        if ok:
            save_state(state)
            print("State spremljen.")
        else:
            print("Telegram nije poslan. State NIJE spremljen.")
    else:
        save_state(state)
        print("Nema novih G3 alarma. State spremljen.")

    print(f"Gotovo: {datetime.now(ET).strftime('%H:%M:%S ET')}")


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

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
