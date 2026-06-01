"""
stock_alert.py — Stock price alert s tri grupe, logika US burze

GRUPE:
  G1 — Intraday: price >= razina + 0.5% (durante trading sesije)
  G2 — Close:    yesterday's close >= razina + 0.5% (postaje aktivan sljedeći dan)
  G3 — Open:     dan nakon G2 zatvaranja, open >= razina + 0.5% (nakon 09:30 ET)

PRAVILA:
  - Pokreće se samo radnim danima (Mon-Fri, nisu US holidays)
  - G1 se prati samo dok je burza otvorena (09:30–16:00 ET)
  - G3 se provjerava tek nakon što burza otvori (>= 09:30 ET)
  - G3 je validan samo ako je previousClose (jučer) bio iznad razine
    I ovo je prvi trading dan NAKON tog zatvaranja
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime, date, timedelta
import zoneinfo

FMP_API_KEY      = os.environ.get("FMP_API_KEY", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

PRAG_POSTO = 0.5   # % iznad razine = proboj

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

POSLANO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "stock_alert_poslano.json"
)

# ── US TRADING CALENDAR ───────────────────────────────────────────

ET = zoneinfo.ZoneInfo("America/New_York")

# Fiksni US blagdani (MM-DD format, godišnje)
US_HOLIDAYS_FIXED = {
    "01-01",  # New Year's Day
    "06-19",  # Juneteenth
    "07-04",  # Independence Day
    "11-11",  # Veterans Day (burza otvorena, ali uključeno kao sigurnosna mreža)
    "12-25",  # Christmas
}

# Promjenjivi US blagdani — generirani dinamički za tekuću godinu
def _nth_weekday(year, month, weekday, n):
    """n-ti weekday (0=Mon) u zadanom mjesecu/godini."""
    d = date(year, month, 1)
    count = 0
    while True:
        if d.weekday() == weekday:
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)

def _last_weekday(year, month, weekday):
    """Zadnji weekday u zadanom mjesecu/godini."""
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d

def us_market_holidays(year):
    """
    Vraća set datuma (date objekti) kada je NYSE zatvorena.
    Pokriva sve relevantne US blagdane.
    """
    holidays = set()

    # New Year's Day
    ny = date(year, 1, 1)
    if ny.weekday() == 6: ny = date(year, 1, 2)   # Sun → Mon
    if ny.weekday() == 5: ny = date(year, 1, 3)   # Sat → Mon (rijetko)
    holidays.add(ny)

    # MLK Day — 3. ponedjeljak u siječnju
    holidays.add(_nth_weekday(year, 1, 0, 3))

    # Presidents' Day — 3. ponedjeljak u veljači
    holidays.add(_nth_weekday(year, 2, 0, 3))

    # Good Friday — 2 dana prije Easter nedjelje
    # Easter algoritam (Anonymous Gregorian)
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    month = (h + l - 7*m + 114) // 31
    day   = ((h + l - 7*m + 114) % 31) + 1
    easter = date(year, month, day)
    holidays.add(easter - timedelta(days=2))

    # Memorial Day — zadnji ponedjeljak u svibnju
    holidays.add(_last_weekday(year, 5, 0))

    # Juneteenth
    jt = date(year, 6, 19)
    if jt.weekday() == 6: jt = date(year, 6, 20)
    if jt.weekday() == 5: jt = date(year, 6, 18)
    holidays.add(jt)

    # Independence Day
    id_ = date(year, 7, 4)
    if id_.weekday() == 6: id_ = date(year, 7, 5)
    if id_.weekday() == 5: id_ = date(year, 7, 3)
    holidays.add(id_)

    # Labor Day — 1. ponedjeljak u rujnu
    holidays.add(_nth_weekday(year, 9, 0, 1))

    # Thanksgiving — 4. četvrtak u studenom
    holidays.add(_nth_weekday(year, 11, 3, 4))

    # Christmas
    xmas = date(year, 12, 25)
    if xmas.weekday() == 6: xmas = date(year, 12, 26)
    if xmas.weekday() == 5: xmas = date(year, 12, 24)
    holidays.add(xmas)

    return holidays

def is_trading_day(d: date = None) -> bool:
    """Je li zadani datum (default: danas ET) radni dan burze."""
    if d is None:
        d = datetime.now(ET).date()
    if d.weekday() >= 5:   # subota ili nedjelja
        return False
    return d not in us_market_holidays(d.year)

def market_open_now() -> bool:
    """Je li burza trenutno otvorena (09:30–16:00 ET)."""
    now = datetime.now(ET)
    if not is_trading_day(now.date()):
        return False
    t = now.time()
    from datetime import time
    return time(9, 30) <= t <= time(16, 0)

def market_opened_today() -> bool:
    """Je li burza već otvorila danas (>= 09:30 ET, trading day)."""
    now = datetime.now(ET)
    if not is_trading_day(now.date()):
        return False
    from datetime import time
    return now.time() >= time(9, 30)

def prev_trading_day(d: date = None) -> date:
    """Vraća prethodni trading dan."""
    if d is None:
        d = datetime.now(ET).date()
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d

def today_et() -> date:
    return datetime.now(ET).date()

# ── STANJE ────────────────────────────────────────────────────────

def ucitaj_poslano():
    if os.path.exists(POSLANO_FILE):
        with open(POSLANO_FILE, "r") as f:
            return json.load(f)
    return {}

def spremi_poslano(poslano):
    with open(POSLANO_FILE, "w") as f:
        json.dump(poslano, f, indent=2, ensure_ascii=False)

# ── PODACI ────────────────────────────────────────────────────────

def dohvati_quote(ticker):
    url = (f"https://financialmodelingprep.com/stable/quote"
           f"?symbol={ticker}&apikey={FMP_API_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data and isinstance(data, list) and data[0].get("price"):
            q = data[0]
            return {
                "price":         round(float(q.get("price")         or 0), 4),
                "open":          round(float(q.get("open")          or 0), 4),
                "previousClose": round(float(q.get("previousClose") or 0), 4),
            }
        return None
    except Exception as e:
        print(f"  Greska {ticker}: {e}")
        return None

# ── TELEGRAM ──────────────────────────────────────────────────────

def posalji_telegram(grupa1, grupa2, grupa3):
    if not (grupa1 or grupa2 or grupa3):
        return False

    now    = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    poruka = f"*STOCK ALERT* {now}\n"

    if grupa1:
        poruka += "\n*① Intraday proboj razine*\n"
        for u in grupa1:
            odmak = (u["cijena"] - u["razina"]) / u["razina"] * 100
            poruka += f"  *{u['ticker']}*  `{u['cijena']:.2f}`  ({odmak:+.1f}% od {u['razina']:.2f})\n"

    if grupa2:
        poruka += "\n*② Zatvorilo iznad razine*\n"
        for u in grupa2:
            odmak = (u["close"] - u["razina"]) / u["razina"] * 100
            poruka += f"  *{u['ticker']}*  close `{u['close']:.2f}`  ({odmak:+.1f}% od {u['razina']:.2f})\n"

    if grupa3:
        poruka += "\n*③ Otvorilo iznad razine (dan nakon zatvaranja)*\n"
        for u in grupa3:
            odmak = (u["open"] - u["razina"]) / u["razina"] * 100
            poruka += f"  *{u['ticker']}*  open `{u['open']:.2f}`  ({odmak:+.1f}% od {u['razina']:.2f})\n"

    params = urllib.parse.urlencode({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       poruka,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        req = urllib.request.Request(url, data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            odgovor = json.loads(r.read())
        if odgovor.get("ok"):
            print("Telegram poruka poslana.")
            return True
        print(f"Telegram greska: {odgovor}")
        return False
    except Exception as e:
        print(f"Telegram greska: {e}")
        return False

def test_telegram():
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    params = urllib.parse.urlencode({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       f"*Stock Alert bot aktivan*\nTest poruka {now}",
        "parse_mode": "Markdown",
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        req = urllib.request.Request(url, data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            odgovor = json.loads(r.read())
        print("Test OK." if odgovor.get("ok") else f"Greska: {odgovor}")
    except Exception as e:
        print(f"Greska: {e}")

# ── PROVJERA ──────────────────────────────────────────────────────

def provjeri():
    now_et  = datetime.now(ET)
    today   = today_et()

    print(f"Provjera: {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")

    # Provjeri trading day
    if not is_trading_day(today):
        print(f"  Danas ({today.strftime('%A %d.%m.')}) nije radni dan burze. Izlazim.")
        return

    burza_otvorena  = market_open_now()
    burza_otvorila  = market_opened_today()
    prev_td         = prev_trading_day(today)

    print(f"  Trading day: DA | Burza otvorena: {'DA' if burza_otvorena else 'NE'} | "
          f"Prethodni trading dan: {prev_td}")

    poslano = ucitaj_poslano()
    prag    = 1 + PRAG_POSTO / 100
    today_s = today.isoformat()          # "2026-05-26"
    prev_s  = prev_td.isoformat()        # "2026-05-23"

    grupa1 = []
    grupa2 = []
    grupa3 = []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = d["razina"]

        quote = dohvati_quote(ticker)
        if quote is None:
            print(f"  {ticker:<8} nije dostupno")
            continue

        price  = quote["price"]
        open_  = quote["open"]
        prev_c = quote["previousClose"]

        print(f"  {ticker:<8}  price={price:.2f}  open={open_:.2f}  "
              f"prevClose={prev_c:.2f}  razina={razina:.2f}", end="")

        k1 = f"{ticker}_{razina}_g1"
        k2 = f"{ticker}_{razina}_g2"
        k3 = f"{ticker}_{razina}_g3"

        # ── G1: Intraday proboj ───────────────────────────────────
        # Samo dok je burza otvorena
        if burza_otvorena:
            if price >= razina * prag:
                # Alarm samo jednom po danu (provjeri datum)
                prev_g1 = poslano.get(k1, {})
                if prev_g1.get("datum") != today_s:
                    odmak = (price - razina) / razina * 100
                    print(f"\n    → G1: {price:.2f} (+{odmak:.1f}%)", end="")
                    grupa1.append({"ticker": ticker, "cijena": price, "razina": razina})
                    poslano[k1] = {
                        "datum":   today_s,
                        "cijena":  price,
                        "poslano": datetime.now(ET).isoformat(),
                    }
            else:
                # Reset G1 kad cijena padne ispod razine (novi dan = nova šansa)
                if k1 in poslano and poslano[k1].get("datum") != today_s:
                    del poslano[k1]

        # ── G2: Zatvaranje iznad razine ───────────────────────────
        # previousClose je zadnje zatvaranje (prethodni trading dan)
        # Bilježi datum zatvaranja kao prev_s da G3 zna koji je to bio dan
        if prev_c >= razina * prag:
            prev_g2 = poslano.get(k2, {})
            # Alarm jednom — kad zabiježimo novo zatvaranje (prev_s)
            if prev_g2.get("close_datum") != prev_s:
                odmak = (prev_c - razina) / razina * 100
                print(f"\n    → G2: close={prev_c:.2f} (+{odmak:.1f}%) od {prev_s}", end="")
                grupa2.append({"ticker": ticker, "close": prev_c, "razina": razina,
                               "close_datum": prev_s})
                poslano[k2] = {
                    "close_datum": prev_s,
                    "close":       prev_c,
                    "poslano":     datetime.now(ET).isoformat(),
                }
        else:
            # Ako previousClose više nije iznad razine, reset G2 i G3
            if k2 in poslano:
                print(f"\n    → G2 reset", end="")
                del poslano[k2]
            if k3 in poslano:
                del poslano[k3]

        # ── G3: Otvaranje iznad razine dan nakon G2 zatvaranja ────
        # Uvjeti:
        #   1. Burza je već otvorila danas (>= 09:30 ET)
        #   2. G2 je bio aktivan za prev_s (prethodni trading dan)
        #   3. Danas open >= razina * prag
        #   4. Alarm još nije poslan za današnji datum
        g2_info = poslano.get(k2, {})
        g2_aktivan = g2_info.get("close_datum") == prev_s

        if burza_otvorila and g2_aktivan and open_ >= razina * prag:
            prev_g3 = poslano.get(k3, {})
            if prev_g3.get("datum") != today_s:
                odmak = (open_ - razina) / razina * 100
                print(f"\n    → G3: open={open_:.2f} (+{odmak:.1f}%) danas {today_s}", end="")
                grupa3.append({"ticker": ticker, "open": open_, "razina": razina})
                poslano[k3] = {
                    "datum":   today_s,
                    "open":    open_,
                    "poslano": datetime.now(ET).isoformat(),
                }

        print()  # novi red po dionici

    # ── Pošalji ───────────────────────────────────────────────────
    ukupno = len(grupa1) + len(grupa2) + len(grupa3)
    if ukupno:
        print(f"\nSaljem Telegram: G1={len(grupa1)}, G2={len(grupa2)}, G3={len(grupa3)}")
        posalji_telegram(grupa1, grupa2, grupa3)
    else:
        print("Nema novih upozorenja.")

    spremi_poslano(poslano)
    print(f"Gotovo: {now_et.strftime('%H:%M:%S ET')}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_telegram()
    else:
        provjeri()
