"""
stock_alert.py - G3 open alert

ŠALJE GRUPU 3 + STATUS PORUKU.

CILJ:
- Provjeriti nakon otvaranja USA burze.
- Alarm se šalje samo ako je:
    1) prethodni trading dan imao G2:
       high >= razina * prag
       close >= razina * prag
    2) današnji open je iznad razine/praga:
       open >= razina * prag

VAŽNO:
- Ako je open provjera za današnji trading dan već uspješno napravljena,
  skripta više ne provjerava isti dan.
- Ako FMP još nema open podatke za G2 kandidate, dan se NE označava kao provjeren,
  kako bi kasniji GitHub cron mogao pokušati ponovno.
- Ako nema novih G3 alarma, šalje se status poruka na Telegram.

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

# Ako želiš čistu razinu bez dodatnog praga, stavi 0.0.
PRAG_POSTO = 0.5

# Koliko minuta nakon otvaranja USA burze smije napraviti open provjeru.
# 20 znači 09:30–09:50 ET.
OPEN_ALERT_WINDOW_MINUTES = 20

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
    {"ticker": "PPC", "razina": 28.90},
    {"ticker": "RDDT", "razina": 183.00},
    {"ticker": "CAT", "razina": 931.00},
    {"ticker": "FTNT", "razina": 148.00},
    {"ticker": "DKNG", "razina": 26.50},
    {"ticker": "UNH", "razina": 403.00},
    {"ticker": "NU", "razina": 12.20},
    {"ticker": "NCLH", "razina": 19.20},
    {"ticker": "BAC", "razina": 54.50},
    {"ticker": "NUE", "razina": 264.00},
    {"ticker": "CLF", "razina": 15.25},
    {"ticker": "MXL", "razina": 104.50},
    {"ticker": "NN", "razina": 24.20},
    {"ticker": "FSLR", "razina": 312.50},
    {"ticker": "RTX", "razina": 179.00},
    {"ticker": "SEI", "razina": 79.00},
    {"ticker": "SMR", "razina": 143.30},
    {"ticker": "SPG", "razina": 208.00},
    {"ticker": "TER", "razina": 423.00},
    {"ticker": "VCC", "razina": 375.00},
    {"ticker": "ROK", "razina": 462.00},
    {"ticker": "IRDM", "razina": 52.00},
    {"ticker": "RPRX", "razina": 56.00},
    {"ticker": "UPS", "razina": 113.00},
    {"ticker": "LLY", "razina": 1122.00},
    {"ticker": "MAC", "razina": 23.00},
    {"ticker": "VNO", "razina": 35.00},
    {"ticker": "NAVN", "razina": 22.80},
    {"ticker": "VRNS", "razina": 35.40},
    {"ticker": "VDAY", "razina": 154.00},
    {"ticker": "QBTS", "razina": 32.40},
    {"ticker": "C", "razina": 133.00},
    {"ticker": "SEZL", "razina": 121.00},
    {"ticker": "TPL", "razina": 409.00},
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
    h.add(_nth_weekday(year, 1, 0, 3))   # Martin Luther King Jr. Day
    h.add(_nth_weekday(year, 2, 0, 3))   # Presidents' Day

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

    h.add(_last_weekday(year, 5, 0))     # Memorial Day
    h.add(obs(date(year, 6, 19)))        # Juneteenth
    h.add(obs(date(year, 7, 4)))         # Independence Day
    h.add(_nth_weekday(year, 9, 0, 1))   # Labor Day
    h.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving
    h.add(obs(date(year, 12, 25)))       # Christmas

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


def open_window_text():
    end_minute_total = 30 + OPEN_ALERT_WINDOW_MINUTES
    end_hour = 9 + end_minute_total // 60
    end_minute = end_minute_total % 60
    return f"09:30–{end_hour:02d}:{end_minute:02d} ET"


# ─────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────

def default_state():
    return {
        "sent_g3": {},
        "open_checks": {}
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
        data.setdefault("open_checks", {})

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


def open_already_checked_today(state, today_s):
    open_checks = state.get("open_checks", {})
    item = open_checks.get(today_s, {})

    if not isinstance(item, dict):
        return False

    return item.get("status") == "checked"


def mark_open_checked_today(
    state,
    today_s,
    checked,
    valid_prev_eod_count,
    g2_ok_count,
    open_valid_count,
    alerts_count,
    note=""
):
    state.setdefault("open_checks", {})

    now_et_s = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")

    state["open_checks"][today_s] = {
        "status": "checked",
        "checked_at_et": now_et_s,
        "checked": checked,
        "valid_prev_eod_count": valid_prev_eod_count,
        "g2_ok_count": g2_ok_count,
        "open_valid_count": open_valid_count,
        "alerts_count": alerts_count,
        "note": note,
    }

    # Čuvaj samo zadnjih 40 dana.
    keys = sorted(state["open_checks"].keys())[-40:]
    state["open_checks"] = {k: state["open_checks"][k] for k in keys}


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


def format_status_message(
    today_s,
    prev_s,
    checked,
    valid_prev_eod_count,
    g2_ok_count,
    open_valid_count,
    quote_missing_for_g2,
    already_sent_count,
    alerts_count,
    mark_checked,
    reason
):
    now_et = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")

    lines = []
    lines.append("G3 OPEN CHECK — STATUS")
    lines.append(now_et)
    lines.append("")
    lines.append(f"Trading day: {today_s}")
    lines.append(f"Prethodni trading day: {prev_s}")
    lines.append("")
    lines.append(f"Provjereno tickera: {checked}")
    lines.append(f"Ima EOD podatke za prethodni dan: {valid_prev_eod_count}")
    lines.append(f"G2 od jučer: {g2_ok_count}")
    lines.append(f"G2 s dostupnim današnjim openom: {open_valid_count}")
    lines.append(f"G2 bez dostupnog opena: {quote_missing_for_g2}")
    lines.append(f"Već poslano danas: {already_sent_count}")
    lines.append(f"Novi G3 alarmi: {alerts_count}")
    lines.append("")
    lines.append(f"Open provjera zaključana za danas: {'DA' if mark_checked else 'NE'}")
    lines.append(f"Razlog: {reason}")

    return "\n".join(lines)


def test_telegram():
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    text = f"Stock Alert bot aktivan\nTest poruka {now}"

    ok = send_telegram_message(text)

    if ok:
        print("Test poruka poslana.")
    else:
        print("Test poruka NIJE poslana.")


# ─────────────────────────────────────────────────────────────
# MAIN LOGIKA — G3 OPEN
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
        send_telegram_message("G3 OPEN CHECK greška: FMP_API_KEY nije postavljen.")
        return

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram ENV nije kompletan. Prekid.")
        return

    if not force and not market_open_alert_window(now_et):
        print(
            "Nije vrijeme za G3 open provjeru. "
            f"Bot radi samo u prozoru {open_window_text()}."
        )
        print("Nema Telegram slanja.")
        return

    if not is_trading_day(today):
        print("Danas nije US trading day. Prekid.")
        if force:
            send_telegram_message(f"G3 OPEN CHECK: {today_s} nije US trading day.")
        return

    prev_day = previous_trading_day(today)
    prev_s = prev_day.isoformat()

    print(f"Trading day: {today_s}")
    print(f"Prethodni trading day za G2: {prev_s}")
    print(f"Alert window: {open_window_text()}")
    print(f"Force mode: {force}")
    print()

    state = load_state()

    if open_already_checked_today(state, today_s) and not force:
        print(f"Open price je već uspješno provjeren za {today_s}.")
        print("Ne provjeravam ponovno isti dan.")
        print("Nema Telegram slanja.")
        return

    alerts = []
    checked = 0
    valid_prev_eod_count = 0
    g2_ok_count = 0
    open_valid_count = 0
    quote_missing_for_g2 = 0
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

        valid_prev_eod_count += 1

        prev_high = prev_ohlc.get("high")
        prev_close = prev_ohlc.get("close")

        if prev_high is None or prev_close is None or prev_high <= 0 or prev_close <= 0:
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
            quote_missing_for_g2 += 1
            print(f"{ticker:<8} G2 DA, ali nema quote/open podatka.")
            continue

        open_today = quote.get("open")

        if open_today is None or open_today <= 0:
            quote_missing_for_g2 += 1
            print(f"{ticker:<8} G2 DA, ali današnji open nije dostupan.")
            continue

        open_valid_count += 1

        # G3 uvjet: današnji open iznad triggera.
        g3_ok = open_today >= trigger

        open_vs_razina_pct = (open_today - razina) / razina * 100

        print(
            f"{ticker:<8} G2 DA | "
            f"open={open_today:.2f} razina={razina:.2f} "
            f"trigger={trigger:.2f} "
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
    print(f"EOD podaci dostupni: {valid_prev_eod_count}")
    print(f"G2 od jučer: {g2_ok_count}")
    print(f"G2 s open podatkom: {open_valid_count}")
    print(f"G2 bez open podatka: {quote_missing_for_g2}")
    print(f"Već poslano danas: {already_sent_count}")
    print(f"Novi G3 alarmi: {len(alerts)}")
    print()

    # Logika zaključavanja dana:
    # 1) Ako nema EOD podataka ni za jednu dionicu, vjerojatno FMP/history problem -> ne zaključavaj.
    # 2) Ako postoje G2 kandidati, ali nijedan nema open podatak, FMP vjerojatno još nije osvježio open -> ne zaključavaj.
    # 3) Ako nema G2 kandidata, provjera je završena -> zaključaj.
    # 4) Ako ima G2 kandidata i svi su imali open ili barem nema missing opena -> zaključaj.

    mark_checked = True
    reason = "Open provjera uspješno završena."

    if valid_prev_eod_count == 0:
        mark_checked = False
        reason = "Nema EOD podataka ni za jednu dionicu. Mogući FMP/history problem."

    elif g2_ok_count > 0 and open_valid_count == 0:
        mark_checked = False
        reason = "Postoje G2 kandidati, ali FMP još nema današnji open podatak."

    elif g2_ok_count > 0 and quote_missing_for_g2 > 0:
        mark_checked = False
        reason = "Neki G2 kandidati nemaju open podatak. Puštam kasniji cron da pokuša ponovno."

    status_msg = format_status_message(
        today_s=today_s,
        prev_s=prev_s,
        checked=checked,
        valid_prev_eod_count=valid_prev_eod_count,
        g2_ok_count=g2_ok_count,
        open_valid_count=open_valid_count,
        quote_missing_for_g2=quote_missing_for_g2,
        already_sent_count=already_sent_count,
        alerts_count=len(alerts),
        mark_checked=mark_checked,
        reason=reason
    )

    telegram_ok = True

    if alerts:
        alert_message = format_simple_g3_alert(alerts)
        telegram_ok = send_long_telegram_message(alert_message)

        # Nakon alarma pošalji i status, da znaš da je provjera zaključana ili ne.
        send_long_telegram_message(status_msg)

    else:
        telegram_ok = send_long_telegram_message(status_msg)

    if mark_checked:
        mark_open_checked_today(
            state=state,
            today_s=today_s,
            checked=checked,
            valid_prev_eod_count=valid_prev_eod_count,
            g2_ok_count=g2_ok_count,
            open_valid_count=open_valid_count,
            alerts_count=len(alerts),
            note=reason
        )
    else:
        print("Open provjera NIJE zaključana za danas.")
        print("Kasniji cron smije pokušati ponovno.")

    if telegram_ok:
        save_state(state)
        print("State spremljen.")
    else:
        # Ako Telegram nije poslan, ne želimo lažno zaključati dan.
        print("Telegram nije uspješno poslan.")
        print("State se neće spremiti kao završena provjera.")
        return

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
