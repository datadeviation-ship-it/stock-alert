"""
stock_alert.py — Stock alert v7

LOGIKA:

G1 — PROBOJ RAZINE
Dionica je tijekom dana probila zadanu razinu.
Za završene dane koristi se dnevni HIGH.
Za današnji dan, dok je burza otvorena, koristi se live PRICE.

G2 — PROBOJ + CLOSE IZNAD RAZINE
Dionica je tijekom dana probila razinu i zatvorila iznad nje.
Uvjet:
    high >= razina * (1 + PRAG_POSTO / 100)
    close >= razina * (1 + PRAG_POSTO / 100)

G3 — PROBOJ + CLOSE + IDUĆI OPEN IZNAD RAZINE
Dionica je ispunila G2, a idući trading dan otvorila iznad razine.
Uvjet:
    next_open >= razina * (1 + PRAG_POSTO / 100)

Pokretanje:
  python stock_alert.py
  python stock_alert.py test
  python stock_alert.py reset
  python stock_alert.py debug
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime, date, timedelta
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

PRAG_POSTO = 0.5
HISTORY_DAYS = 15

ET = zoneinfo.ZoneInfo("America/New_York")

POSLANO_FILE = os.path.join(
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
    {"ticker": "DG",    "razina": 6.60},
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


def next_trading_day(d):
    d += timedelta(days=1)

    while not is_trading_day(d):
        d += timedelta(days=1)

    return d


def last_n_trading_days(n, before):
    days = []
    d = before - timedelta(days=1)

    while len(days) < n:
        if is_trading_day(d):
            days.append(d)
        d -= timedelta(days=1)

    return sorted(days)


def burza_je_otvorena():
    from datetime import time as dtime

    now = datetime.now(ET)

    return (
        is_trading_day(now.date())
        and dtime(9, 30) <= now.time() <= dtime(16, 0)
    )


# ─────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────

def default_state():
    return {
        "g1": {},
        "g2": {},
        "g3": {},
    }


def ucitaj_poslano():
    if not os.path.exists(POSLANO_FILE):
        return default_state()

    try:
        with open(POSLANO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return default_state()

        data.setdefault("g1", {})
        data.setdefault("g2", {})
        data.setdefault("g3", {})

        return data

    except Exception as e:
        print(f"Ne mogu učitati state file: {e}")
        return default_state()


def spremi_poslano(state):
    with open(POSLANO_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def key_for(ticker, razina):
    return f"{ticker}_{razina:.4f}"


# ─────────────────────────────────────────────────────────────
# FMP
# ─────────────────────────────────────────────────────────────

def dohvati_quote(ticker):
    url = (
        "https://financialmodelingprep.com/stable/quote"
        f"?symbol={ticker}&apikey={FMP_API_KEY}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

        if data and isinstance(data, list):
            q = data[0]

            price = q.get("price")
            open_ = q.get("open")

            if price is None:
                return None

            return {
                "price": round(float(price), 4),
                "open": round(float(open_ or 0), 4),
            }

        return None

    except Exception as e:
        print(f"  quote greska {ticker}: {e}")
        return None


def dohvati_historiju(ticker):
    start = datetime.now(ET).date() - timedelta(days=HISTORY_DAYS * 4)

    url = (
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
        f"?symbol={ticker}&from={start.isoformat()}&apikey={FMP_API_KEY}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())

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
                "open": round(float(row.get("open", 0) or 0), 4),
                "high": round(float(row.get("high", 0) or 0), 4),
                "low": round(float(row.get("low", 0) or 0), 4),
                "close": round(float(row.get("close", 0) or 0), 4),
            }

        return result

    except Exception as e:
        print(f"  historija greska {ticker}: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────

def posalji_telegram_poruku(text):
    if not TELEGRAM_TOKEN:
        print("Telegram greska: TELEGRAM_TOKEN nije postavljen.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("Telegram greska: TELEGRAM_CHAT_ID nije postavljen.")
        return False

    params = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        req = urllib.request.Request(url, data=params, method="POST")

        with urllib.request.urlopen(req, timeout=15) as r:
            odgovor = json.loads(r.read())

        if odgovor.get("ok"):
            print("Telegram poruka poslana.")
            return True

        print(f"Telegram greska: {odgovor}")
        return False

    except Exception as e:
        print(f"Telegram greska: {e}")
        return False


def format_alert(g1, g2, g3):
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")

    poruka = f"*STOCK ALERT* {now}\n"

    if g1:
        poruka += "\n*1) PROBOJ RAZINE*\n"
        for u in g1:
            odmak = (u["vrijednost"] - u["razina"]) / u["razina"] * 100
            poruka += (
                f"*{u['ticker']}* `{u['vrijednost']:.2f}` "
                f"razina `{u['razina']:.2f}` "
                f"{u['datum']} ({odmak:+.2f}%)\n"
            )

    if g2:
        poruka += "\n*2) PROBOJ + CLOSE IZNAD*\n"
        for u in g2:
            odmak = (u["close"] - u["razina"]) / u["razina"] * 100
            poruka += (
                f"*{u['ticker']}* close `{u['close']:.2f}` "
                f"high `{u['high']:.2f}` "
                f"razina `{u['razina']:.2f}` "
                f"{u['datum']} ({odmak:+.2f}%)\n"
            )

    if g3:
        poruka += "\n*3) IDUĆI OPEN IZNAD*\n"
        for u in g3:
            odmak = (u["open"] - u["razina"]) / u["razina"] * 100
            poruka += (
                f"*{u['ticker']}* open `{u['open']:.2f}` "
                f"razina `{u['razina']:.2f}` "
                f"{u['datum']} nakon {u['g2_datum']} ({odmak:+.2f}%)\n"
            )

    return poruka


def posalji_telegram(g1, g2, g3):
    if not (g1 or g2 or g3):
        return False

    poruka = format_alert(g1, g2, g3)
    return posalji_telegram_poruku(poruka)


def test_telegram():
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    text = f"*Stock Alert bot aktivan*\nTest poruka {now}"
    ok = posalji_telegram_poruku(text)

    if ok:
        print("Test poruka poslana.")
    else:
        print("Test poruka NIJE poslana.")


# ─────────────────────────────────────────────────────────────
# GLAVNA LOGIKA
# ─────────────────────────────────────────────────────────────

def provjeri():
    now_et = datetime.now(ET)
    today = now_et.date()
    today_s = today.isoformat()

    print(f"Provjera: {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")
    print(f"State file: {POSLANO_FILE}")
    debug_env()

    if not FMP_API_KEY:
        print("FMP_API_KEY nije postavljen. Prekid.")
        return

    otvorena = burza_je_otvorena()
    hist_days = last_n_trading_days(HISTORY_DAYS, today)
    prag = 1 + PRAG_POSTO / 100

    print(
        f"Burza otvorena: {'DA' if otvorena else 'NE'} | "
        f"History window: {hist_days[0]} — {hist_days[-1]}"
    )
    print()

    state = ucitaj_poslano()

    g1_alerts = []
    g2_alerts = []
    g3_alerts = []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = float(d["razina"])
        trigger = razina * prag
        k = key_for(ticker, razina)

        hist = dohvati_historiju(ticker)
        quote = dohvati_quote(ticker) if otvorena else None

        price = quote["price"] if quote else None
        open_danas = quote["open"] if quote and quote.get("open") else hist.get(today_s, {}).get("open")

        price_s = f"{price:.2f}" if price is not None else "—"
        open_s = f"{open_danas:.2f}" if open_danas is not None else "—"

        print(
            f"{ticker:<8} razina={razina:.2f} trigger={trigger:.2f} "
            f"price={price_s} open={open_s}"
        )

        state["g1"].setdefault(k, {
            "ticker": ticker,
            "razina": razina,
            "datumi": [],
        })

        state["g2"].setdefault(k, {
            "ticker": ticker,
            "razina": razina,
            "datumi": [],
        })

        state["g3"].setdefault(k, {
            "ticker": ticker,
            "razina": razina,
            "datumi": [],
        })

        g1_dates = set(state["g1"][k].get("datumi", []))
        g2_dates = set(state["g2"][k].get("datumi", []))
        g3_dates = set(state["g3"][k].get("datumi", []))

        # ─────────────────────────────────────
        # G1 — završeni dani: high >= trigger
        # ─────────────────────────────────────

        for td in hist_days:
            td_s = td.isoformat()

            if td_s in g1_dates:
                continue

            ohlc = hist.get(td_s)

            if not ohlc:
                continue

            high_val = ohlc.get("high")

            if high_val is None:
                continue

            if high_val >= trigger:
                g1_alerts.append({
                    "ticker": ticker,
                    "vrijednost": high_val,
                    "razina": razina,
                    "datum": td_s,
                })

                g1_dates.add(td_s)

                print(f"  G1: high {high_val:.2f} na {td_s}")

        # ─────────────────────────────────────
        # G1 — danas live: price >= trigger
        # ─────────────────────────────────────

        if otvorena and price is not None:
            if price >= trigger and today_s not in g1_dates:
                g1_alerts.append({
                    "ticker": ticker,
                    "vrijednost": price,
                    "razina": razina,
                    "datum": today_s,
                })

                g1_dates.add(today_s)

                print(f"  G1 LIVE: price {price:.2f} danas")

        state["g1"][k]["datumi"] = sorted(g1_dates)[-HISTORY_DAYS:]

        # ─────────────────────────────────────
        # G2 — high >= trigger i close >= trigger
        # ─────────────────────────────────────

        for td in hist_days:
            td_s = td.isoformat()

            if td_s in g2_dates:
                continue

            ohlc = hist.get(td_s)

            if not ohlc:
                continue

            high_val = ohlc.get("high")
            close_val = ohlc.get("close")

            if high_val is None or close_val is None:
                continue

            if high_val >= trigger and close_val >= trigger:
                g2_alerts.append({
                    "ticker": ticker,
                    "high": high_val,
                    "close": close_val,
                    "razina": razina,
                    "datum": td_s,
                })

                g2_dates.add(td_s)

                print(f"  G2: high {high_val:.2f}, close {close_val:.2f} na {td_s}")

        state["g2"][k]["datumi"] = sorted(g2_dates)[-HISTORY_DAYS:]

        # ─────────────────────────────────────
        # G3 — nakon G2, idući trading day open >= trigger
        # ─────────────────────────────────────

        for g2_d_s in sorted(g2_dates):
            g2_d = date.fromisoformat(g2_d_s)
            next_d = next_trading_day(g2_d)
            next_s = next_d.isoformat()

            if next_s in g3_dates:
                continue

            if next_d > today:
                continue

            if next_d == today:
                open_val = open_danas
            else:
                open_val = hist.get(next_s, {}).get("open")

            if open_val is None:
                continue

            if open_val >= trigger:
                g3_alerts.append({
                    "ticker": ticker,
                    "open": open_val,
                    "razina": razina,
                    "datum": next_s,
                    "g2_datum": g2_d_s,
                })

                g3_dates.add(next_s)

                print(f"  G3: open {open_val:.2f} na {next_s}, nakon G2 {g2_d_s}")

        state["g3"][k]["datumi"] = sorted(g3_dates)[-HISTORY_DAYS:]

    ukupno = len(g1_alerts) + len(g2_alerts) + len(g3_alerts)

    print()
    print(f"Rezultat: G1={len(g1_alerts)}, G2={len(g2_alerts)}, G3={len(g3_alerts)}, ukupno={ukupno}")

    if ukupno:
        print(f"Saljem Telegram: {ukupno} alarm(a)")
        telegram_ok = posalji_telegram(g1_alerts, g2_alerts, g3_alerts)

        if telegram_ok:
            spremi_poslano(state)
            print("State spremljen.")
        else:
            print("Telegram nije poslan. State nije spremljen.")
    else:
        print("Nema novih upozorenja.")
        spremi_poslano(state)

    print(f"Gotovo: {datetime.now(ET).strftime('%H:%M:%S ET')}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    arg = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""

    if arg == "test":
        test_telegram()

    elif arg == "reset":
        if os.path.exists(POSLANO_FILE):
            os.remove(POSLANO_FILE)
            print("Resetirano — stock_alert_poslano.json obrisan.")
        else:
            print("Nema što resetirati.")

    elif arg == "debug":
        debug_env()

    else:
        provjeri()
