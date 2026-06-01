"""
stock_alert.py — Stock price alert v4

GRUPE:
  G1 — Intraday: price >= razina + 0.5%  (samo dok je burza otvorena 09:30-16:00 ET)
  G2 — Close:    bilo koji od zadnjih 10 trading dana zatvorio >= razina + 0.5%
  G3 — Open:     dan nakon G2 zatvaranja otvorio >= razina + 0.5%

  G2 i G3 se provjeravaju uvijek (i prije i poslije otvaranja burze).
  G1 samo dok je burza otvorena.

Pokretanje:
  python stock_alert.py           — normalna provjera
  python stock_alert.py test      — test Telegram poruka
  python stock_alert.py reset     — briše poslano.json (nova provjera svega)
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

PRAG_POSTO   = 0.5
HISTORY_DAYS = 10

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
    d, count = date(year, month, 1), 0
    while True:
        if d.weekday() == weekday:
            count += 1
            if count == n: return d
        d += timedelta(days=1)

def _last_weekday(year, month, weekday):
    d = date(year, month+1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while d.weekday() != weekday: d -= timedelta(days=1)
    return d

def us_holidays(year):
    def obs(d):
        if d.weekday() == 6: return d + timedelta(days=1)
        if d.weekday() == 5: return d - timedelta(days=1)
        return d
    h = set()
    h.add(obs(date(year, 1, 1)))
    h.add(_nth_weekday(year, 1, 0, 3))
    h.add(_nth_weekday(year, 2, 0, 3))
    # Good Friday
    a = year%19; b,c = divmod(year,100); d2,e = divmod(b,4)
    f=(b+8)//25; g=(b-f+1)//3; hh=(19*a+b-d2-g+15)%30
    i,k=divmod(c,4); l=(32+2*e+2*i-hh-k)%7
    m=(a+11*hh+22*l)//451; mo=(hh+l-7*m+114)//31; dy=(hh+l-7*m+114)%31+1
    h.add(date(year, mo, dy) - timedelta(days=2))
    h.add(_last_weekday(year, 5, 0))
    h.add(obs(date(year, 6, 19)))
    h.add(obs(date(year, 7, 4)))
    h.add(_nth_weekday(year, 9, 0, 1))
    h.add(_nth_weekday(year, 11, 3, 4))
    h.add(obs(date(year, 12, 25)))
    return h

def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in us_holidays(d.year)

def next_trading_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d): d += timedelta(days=1)
    return d

def last_n_trading_days(n: int, before: date) -> list:
    """Vraća listu zadnjih n trading dana koji su završili (< before)."""
    days, d = [], before - timedelta(days=1)
    while len(days) < n:
        if is_trading_day(d): days.append(d)
        d -= timedelta(days=1)
    return sorted(days)

def burza_je_otvorena() -> bool:
    from datetime import time as dtime
    now = datetime.now(ET)
    return (is_trading_day(now.date()) and
            dtime(9, 30) <= now.time() <= dtime(16, 0))

# ── JSON STATE ────────────────────────────────────────────────────

def ucitaj_poslano():
    if os.path.exists(POSLANO_FILE):
        with open(POSLANO_FILE, "r") as f:
            return json.load(f)
    return {}

def spremi_poslano(p):
    with open(POSLANO_FILE, "w") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)

# ── FMP ───────────────────────────────────────────────────────────

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
                "price": round(float(q.get("price") or 0), 4),
                "open":  round(float(q.get("open")  or 0), 4),
            }
    except Exception as e:
        print(f"  quote greska {ticker}: {e}")
    return None

def dohvati_historiju(ticker):
    """Dohvati dnevne OHLC bez &to ograničenja — FMP vraća najsvježije podatke."""
    start = datetime.now(ET).date() - timedelta(days=HISTORY_DAYS * 3)
    url = (f"https://financialmodelingprep.com/stable/historical-price-eod/full"
           f"?symbol={ticker}&from={start.isoformat()}&apikey={FMP_API_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        records = data.get("historical", data) if isinstance(data, dict) else data
        result = {}
        for row in records:
            ds = str(row.get("date", ""))[:10]
            if ds:
                result[ds] = {
                    "open":  round(float(row.get("open",  0) or 0), 4),
                    "close": round(float(row.get("close", 0) or 0), 4),
                }
        return result
    except Exception as e:
        print(f"  historija greska {ticker}: {e}")
    return {}

# ── TELEGRAM ──────────────────────────────────────────────────────

def posalji_telegram(g1, g2, g3):
    if not (g1 or g2 or g3):
        return False
    now    = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    poruka = f"*STOCK ALERT* {now}\n"
    if g1:
        poruka += "\n*① Intraday proboj*\n"
        for u in g1:
            odmak = (u["cijena"] - u["razina"]) / u["razina"] * 100
            poruka += f"  *{u['ticker']}*  `{u['cijena']:.2f}`  ({odmak:+.1f}%)\n"
    if g2:
        poruka += "\n*② Zatvorilo iznad razine*\n"
        for u in g2:
            odmak = (u["close"] - u["razina"]) / u["razina"] * 100
            poruka += f"  *{u['ticker']}*  close `{u['close']:.2f}`  {u['datum']}  ({odmak:+.1f}%)\n"
    if g3:
        poruka += "\n*③ Otvorilo iznad razine*\n"
        for u in g3:
            odmak = (u["open"] - u["razina"]) / u["razina"] * 100
            poruka += f"  *{u['ticker']}*  open `{u['open']:.2f}`  {u['datum']}  ({odmak:+.1f}%)\n"

    params = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": poruka, "parse_mode": "Markdown"
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            print("Telegram OK.")
            return True
        print(f"Telegram greska: {resp}")
    except Exception as e:
        print(f"Telegram greska: {e}")
    return False

def test_telegram():
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    params = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"*Stock Alert bot aktivan* — test {now}",
        "parse_mode": "Markdown"
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        print("Test OK." if resp.get("ok") else f"Greska: {resp}")
    except Exception as e:
        print(f"Greska: {e}")

# ── PROVJERA ──────────────────────────────────────────────────────

def provjeri():
    now_et  = datetime.now(ET)
    today   = now_et.date()
    today_s = today.isoformat()

    print(f"Provjera: {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")

    if not is_trading_day(today):
        print(f"  Danas ({today.strftime('%A %d.%m.')}) nije radni dan burze. Izlazim.")
        return

    otvorena = burza_je_otvorena()
    prag     = 1 + PRAG_POSTO / 100

    # Zadnjih HISTORY_DAYS završenih trading dana (ne uključuje danas)
    hist_days = last_n_trading_days(HISTORY_DAYS, today)
    print(f"  Burza otvorena: {'DA' if otvorena else 'NE'} | "
          f"Provjera dana: {hist_days[0]} — {hist_days[-1]}")

    poslano = ucitaj_poslano()
    g1, g2, g3 = [], [], []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = d["razina"]
        try:
            hist  = dohvati_historiju(ticker)
            quote = dohvati_quote(ticker) if otvorena else None

            price = quote["price"] if quote else None
            # open danas: iz live quote ako otvorena, inače iz historije
            open_danas = (quote["open"] if quote and quote.get("open")
                          else hist.get(today_s, {}).get("open"))

            ps = f"{price:.2f}" if price is not None else "—"
            os_ = f"{open_danas:.2f}" if open_danas is not None else "—"
            print(f"  {ticker:<8} razina={razina:.2f}  price={ps}  open={os_}", end="")

            k1 = f"{ticker}_{razina}_g1"
            k2 = f"{ticker}_{razina}_g2"
            k3 = f"{ticker}_{razina}_g3"

            # ── G1: intraday (samo dok je burza otvorena) ─────────
            if otvorena and price is not None:
                if price >= razina * prag:
                    if poslano.get(k1, {}).get("datum") != today_s:
                        odmak = (price - razina) / razina * 100
                        print(f"\n    G1: {price:.2f} ({odmak:+.1f}%)", end="")
                        g1.append({"ticker": ticker, "cijena": price, "razina": razina})
                        poslano[k1] = {"datum": today_s}
                else:
                    if k1 in poslano and poslano[k1].get("datum") != today_s:
                        del poslano[k1]

            # ── G2: close iznad razine (zadnjih HISTORY_DAYS dana) ─
            # Radi UVIJEK — i prije i nakon otvaranja
            vec_poslano_g2 = set(poslano.get(k2, {}).get("datumi", []))
            for td in hist_days:
                td_s = td.isoformat()
                if td_s in vec_poslano_g2:
                    continue
                ohlc = hist.get(td_s)
                if not ohlc:
                    continue
                if ohlc["close"] >= razina * prag:
                    odmak = (ohlc["close"] - razina) / razina * 100
                    print(f"\n    G2: close={ohlc['close']:.2f} {td_s} ({odmak:+.1f}%)", end="")
                    g2.append({"ticker": ticker, "close": ohlc["close"],
                               "razina": razina, "datum": td_s})
                    vec_poslano_g2.add(td_s)

            if vec_poslano_g2:
                poslano[k2] = {"datumi": sorted(vec_poslano_g2)[-HISTORY_DAYS:]}
            elif k2 in poslano:
                del poslano[k2]

            # ── G3: open iznad razine dan nakon G2 ────────────────
            # Radi UVIJEK — provjeravamo i prošle i današnji dan
            g2_datumi     = sorted(poslano.get(k2, {}).get("datumi", []))
            vec_poslano_g3 = set(poslano.get(k3, {}).get("datumi", []))

            for g2_d_s in g2_datumi:
                g2_d    = date.fromisoformat(g2_d_s)
                next_d  = next_trading_day(g2_d)
                next_s  = next_d.isoformat()

                if next_s in vec_poslano_g3:
                    continue
                if next_d > today:
                    continue  # još nije stigao taj dan

                # Dohvati open za next_d
                if next_d == today:
                    open_val = open_danas  # live ili iz FMP historije
                else:
                    open_val = hist.get(next_s, {}).get("open")

                if not open_val:
                    continue

                if open_val >= razina * prag:
                    odmak = (open_val - razina) / razina * 100
                    print(f"\n    G3: open={open_val:.2f} {next_s} "
                          f"(G2={g2_d_s}) ({odmak:+.1f}%)", end="")
                    g3.append({"ticker": ticker, "open": open_val,
                               "razina": razina, "datum": next_s})
                    vec_poslano_g3.add(next_s)

            if vec_poslano_g3:
                poslano[k3] = {"datumi": sorted(vec_poslano_g3)[-HISTORY_DAYS:]}

            print()

        except Exception as e:
            print(f"\n  GRESKA {ticker}: {e}")

    # ── Pošalji ───────────────────────────────────────────────────
    ukupno = len(g1) + len(g2) + len(g3)
    if ukupno:
        print(f"\nSaljem: G1={len(g1)}, G2={len(g2)}, G3={len(g3)}")
        posalji_telegram(g1, g2, g3)
    else:
        print("Nema novih upozorenja.")

    spremi_poslano(poslano)
    print(f"Gotovo: {now_et.strftime('%H:%M:%S ET')}")


if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "test":
        test_telegram()
    elif arg == "reset":
        if os.path.exists(POSLANO_FILE):
            os.remove(POSLANO_FILE)
            print("Resetirano — poslano.json obrisan.")
        else:
            print("Nema što resetirati.")
    else:
        provjeri()
