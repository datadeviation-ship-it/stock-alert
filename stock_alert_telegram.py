"""
stock_alert.py — Stock price alert s tri grupe, OHLC historija

GRUPE:
  G1 — Intraday: trenutna cijena >= razina + 0.5% (samo dok je burza otvorena)
  G2 — Close:    bilo koji neprocessirani trading dan je zatvorio >= razina + 0.5%
  G3 — Open:     dan nakon G2 datuma, open >= razina + 0.5% (samo nakon 09:30 ET)

Ključna razlika vs prethodne verzije:
  Fetchamo OHLC za zadnjih 10 trading dana i procesiramo svaki dan zasebno.
  Tako ne propuštamo dane čak i ako skripta nije bila pokrenuta ili je preskočila.
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

PRAG_POSTO   = 0.5   # % iznad razine = proboj
HISTORY_DAYS = 10    # koliko trading dana gledamo unazad za G2/G3

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

# ── TRADING CALENDAR ──────────────────────────────────────────────

ET = zoneinfo.ZoneInfo("America/New_York")

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
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d

def us_holidays(year):
    h = set()
    def obs(d):
        if d.weekday() == 6: return d + timedelta(days=1)
        if d.weekday() == 5: return d - timedelta(days=1)
        return d
    h.add(obs(date(year, 1,  1)))   # New Year
    h.add(_nth_weekday(year, 1, 0, 3))  # MLK
    h.add(_nth_weekday(year, 2, 0, 3))  # Presidents
    # Good Friday
    a = year % 19; b, c = divmod(year, 100); d2, e = divmod(b, 4)
    f = (b+8)//25; g = (b-f+1)//3; hh = (19*a+b-d2-g+15)%30
    i, k = divmod(c, 4); l = (32+2*e+2*i-hh-k)%7
    m = (a+11*hh+22*l)//451; mo = (hh+l-7*m+114)//31; dy = (hh+l-7*m+114)%31+1
    h.add(date(year, mo, dy) - timedelta(days=2))
    h.add(_last_weekday(year, 5, 0))         # Memorial Day
    h.add(obs(date(year, 6, 19)))            # Juneteenth
    h.add(obs(date(year, 7,  4)))            # Independence Day
    h.add(_nth_weekday(year, 9, 0, 1))       # Labor Day
    h.add(_nth_weekday(year, 11, 3, 4))      # Thanksgiving
    h.add(obs(date(year, 12, 25)))           # Christmas
    return h

def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in us_holidays(d.year)

def prev_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d

def next_trading_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d

def last_n_trading_days(n: int, up_to: date = None) -> list:
    """Vraća listu zadnjih n završenih trading dana (bez danas)."""
    if up_to is None:
        up_to = datetime.now(ET).date()
    days = []
    d = up_to - timedelta(days=1)
    while len(days) < n:
        if is_trading_day(d):
            days.append(d)
        d -= timedelta(days=1)
    return sorted(days)  # kronološki

def market_open_now() -> bool:
    now = datetime.now(ET)
    if not is_trading_day(now.date()):
        return False
    from datetime import time as dtime
    return dtime(9, 30) <= now.time() <= dtime(16, 0)

def market_opened_today() -> bool:
    now = datetime.now(ET)
    if not is_trading_day(now.date()):
        return False
    from datetime import time as dtime
    return now.time() >= dtime(9, 30)

# ── STANJE ────────────────────────────────────────────────────────

def ucitaj_poslano():
    if os.path.exists(POSLANO_FILE):
        with open(POSLANO_FILE, "r") as f:
            return json.load(f)
    return {}

def spremi_poslano(poslano):
    with open(POSLANO_FILE, "w") as f:
        json.dump(poslano, f, indent=2, ensure_ascii=False)

# ── FMP API ───────────────────────────────────────────────────────

def dohvati_quote(ticker):
    """Trenutna cijena, open i previousClose."""
    url = (f"https://financialmodelingprep.com/stable/quote"
           f"?symbol={ticker}&apikey={FMP_API_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data and isinstance(data, list) and data[0].get("price"):
            q = data[0]
            return {
                "price": round(float(q.get("price") or 0), 4),
                "open":  round(float(q.get("open")  or 0), 4),
            }
        return None
    except Exception as e:
        print(f"  Greska quote {ticker}: {e}")
        return None

def dohvati_ohlc_historiju(ticker, days=15):
    """
    Fetchaj dnevne OHLC podatke za zadnjih `days` kalendarskih dana.
    Vraća dict {date_str: {"open": ..., "close": ...}}
    """
    end   = datetime.now(ET).date()
    start = end - timedelta(days=days + 20)  # više margine  # malo više za sigurnost
    # Bez &to parametra — FMP vraća najsvježije dostupne podatke
    # &to=danas može rezati zadnji dan ako nije još procesiran na FMP strani
    url = (f"https://financialmodelingprep.com/stable/historical-price-eod/full"
           f"?symbol={ticker}"
           f"&from={start.isoformat()}"
           f"&apikey={FMP_API_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

        # FMP vraća {"historical": [...]} ili direktno listu
        if isinstance(data, dict) and "historical" in data:
            records = data["historical"]
        elif isinstance(data, list):
            records = data
        else:
            return {}

        result = {}
        for row in records:
            d_str = str(row.get("date", ""))[:10]
            if not d_str:
                continue
            result[d_str] = {
                "open":  round(float(row.get("open",  0) or 0), 4),
                "close": round(float(row.get("close", 0) or 0), 4),
            }
        return result
    except Exception as e:
        print(f"  Greska historija {ticker}: {e}")
        return {}

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
            poruka += (f"  *{u['ticker']}*  close `{u['close']:.2f}`"
                       f"  {u['datum']}  ({odmak:+.1f}% od {u['razina']:.2f})\n")

    if grupa3:
        poruka += "\n*③ Otvorilo iznad razine (dan nakon zatvaranja)*\n"
        for u in grupa3:
            odmak = (u["open"] - u["razina"]) / u["razina"] * 100
            poruka += (f"  *{u['ticker']}*  open `{u['open']:.2f}`"
                       f"  {u['datum']}  ({odmak:+.1f}% od {u['razina']:.2f})\n")

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
    now_et = datetime.now(ET)
    today  = now_et.date()

    print(f"Provjera: {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")

    if not is_trading_day(today):
        print(f"  Danas ({today.strftime('%A %d.%m.')}) nije radni dan burze. Izlazim.")
        return

    burza_otvorena = market_open_now()
    burza_otvorila = market_opened_today()
    prag           = 1 + PRAG_POSTO / 100
    today_s        = today.isoformat()

    # Zadnjih HISTORY_DAYS završenih trading dana (bez danas)
    hist_days = last_n_trading_days(HISTORY_DAYS, today)

    print(f"  Burza otvorena: {'DA' if burza_otvorena else 'NE'} | "
          f"Otvorila: {'DA' if burza_otvorila else 'NE'} | "
          f"Provjera dana: {hist_days[0].isoformat()} — {hist_days[-1].isoformat()}")

    poslano = ucitaj_poslano()
    grupa1, grupa2, grupa3 = [], [], []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = d["razina"]

        # Dohvati OHLC historiju i trenutni quote paralelno
        historija = dohvati_ohlc_historiju(ticker, days=HISTORY_DAYS + 5)
        quote     = dohvati_quote(ticker) if burza_otvorena else None

        price = quote["price"] if quote else None
        open_ = quote["open"]  if quote else None

        # Ako burza nije otvorena ali imamo OHLC, uzmi open iz historije za danas
        # (ili ako je quote dostupan, koristi taj open)
        if not open_ and today_s in historija:
            open_ = historija[today_s]["open"]

        price_s = f"{price:.2f}" if price is not None else "—"
        open_s  = f"{open_:.2f}"  if open_  is not None else "—"
        print(f"  {ticker:<8}  razina={razina:.2f}  price={price_s}  open={open_s}", end="")

        k1 = f"{ticker}_{razina}_g1"
        k2 = f"{ticker}_{razina}_g2"
        k3 = f"{ticker}_{razina}_g3"

        # ── G1: Intraday proboj ───────────────────────────────────
        if burza_otvorena and price is not None:
            if price >= razina * prag:
                prev_g1 = poslano.get(k1, {})
                if prev_g1.get("datum") != today_s:
                    odmak = (price - razina) / razina * 100
                    print(f"\n    G1: {price:.2f} (+{odmak:.1f}%)", end="")
                    grupa1.append({"ticker": ticker, "cijena": price, "razina": razina})
                    poslano[k1] = {"datum": today_s, "cijena": price,
                                   "poslano": now_et.isoformat()}
            else:
                if k1 in poslano and poslano[k1].get("datum") != today_s:
                    del poslano[k1]

        # ── G2: Prođi kroz sve historical dane i traži close >= razine ──
        # Šalje alarm samo jednom po datumu zatvaranja
        sent_g2_dates = set(poslano.get(k2, {}).get("datumi", []))

        for td in hist_days:
            td_s = td.isoformat()
            if td_s in sent_g2_dates:
                continue  # ovaj dan je već obrađen

            ohlc = historija.get(td_s)
            if not ohlc:
                continue

            close = ohlc["close"]
            if close >= razina * prag:
                odmak = (close - razina) / razina * 100
                print(f"\n    G2: close={close:.2f} datum={td_s} (+{odmak:.1f}%)", end="")
                grupa2.append({"ticker": ticker, "close": close,
                               "razina": razina, "datum": td_s})
                sent_g2_dates.add(td_s)

        # Ažuriraj listu G2 datuma u stanju
        if sent_g2_dates:
            # Zadrži samo HISTORY_DAYS najnovijih
            sorted_dates = sorted(sent_g2_dates)[-HISTORY_DAYS:]
            poslano[k2] = {"datumi": sorted_dates}
        elif k2 in poslano:
            del poslano[k2]

        # ── G3: Dan nakon G2 close — open >= razine ──────────────
        # Za svaki G2 datum, provjeri je li idući trading dan otvorilo iznad razine
        if not burza_otvorila:
            print()
            continue

        sent_g3_dates = set(poslano.get(k3, {}).get("datumi", []))
        g2_datumi     = sorted(poslano.get(k2, {}).get("datumi", []))

        for g2_datum_s in g2_datumi:
            g2_datum  = date.fromisoformat(g2_datum_s)
            next_td   = next_trading_day(g2_datum)
            next_td_s = next_td.isoformat()

            if next_td_s in sent_g3_dates:
                continue  # već poslano

            # Provjeri samo ako je idući trading dan <= danas
            if next_td > today:
                continue

            # Dohvati open za next_td
            if next_td == today:
                # Danas — koristi live open
                open_next = open_
            else:
                # Prošli dan — iz historije
                ohlc_next = historija.get(next_td_s)
                open_next = ohlc_next["open"] if ohlc_next else None

            if open_next is None:
                continue

            if open_next >= razina * prag:
                odmak = (open_next - razina) / razina * 100
                print(f"\n    G3: open={open_next:.2f} datum={next_td_s} "
                      f"(G2 close={g2_datum_s}) (+{odmak:.1f}%)", end="")
                grupa3.append({"ticker": ticker, "open": open_next,
                               "razina": razina, "datum": next_td_s})
                sent_g3_dates.add(next_td_s)

        if sent_g3_dates:
            sorted_g3 = sorted(sent_g3_dates)[-HISTORY_DAYS:]
            poslano[k3] = {"datumi": sorted_g3}

        print()  # novi red

    # ── Pošalji ───────────────────────────────────────────────────
    ukupno = len(grupa1) + len(grupa2) + len(grupa3)
    if ukupno:
        print(f"\nSaljem: G1={len(grupa1)}, G2={len(grupa2)}, G3={len(grupa3)}")
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
