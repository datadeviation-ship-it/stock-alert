"""
stock_alert.py — Stock price alert v6

LOGIKA ALARMA:

G1 — PROBOJ RAZINE
Dionica je tijekom dana, dok je burza otvorena, došla iznad:
    razina * (1 + PRAG_POSTO / 100)

G2 — PROBOJ + CLOSE IZNAD RAZINE
Dionica je imala evidentiran G1 proboj i taj isti trading dan
zatvorila je iznad:
    razina * (1 + PRAG_POSTO / 100)

G3 — G1 + G2 + IDUĆI OPEN IZNAD RAZINE
Dionica je ispunila G1 i G2, a idući trading dan otvorila je iznad:
    razina * (1 + PRAG_POSTO / 100)

Pokretanje:
  python stock_alert.py           — normalna provjera
  python stock_alert.py test      — test Telegram poruka
  python stock_alert.py reset     — briše stock_alert_poslano.json
  python stock_alert.py debug     — provjera ENV varijabli
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime, date, timedelta
import zoneinfo


# ─────────────────────────────────────────────────────────────────────
# ENV VARIJABLE
# ─────────────────────────────────────────────────────────────────────

FMP_API_KEY = os.environ.get("FMP_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


# ─────────────────────────────────────────────────────────────────────
# POSTAVKE
# ─────────────────────────────────────────────────────────────────────

PRAG_POSTO = 0.5
HISTORY_DAYS = 15

ET = zoneinfo.ZoneInfo("America/New_York")

POSLANO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "stock_alert_poslano.json"
)


# ─────────────────────────────────────────────────────────────────────
# LISTA DIONICA
# ─────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────
# DEBUG
# ─────────────────────────────────────────────────────────────────────

def debug_env():
    print("ENV provjera:")
    print(f"  FMP_API_KEY exists:      {bool(FMP_API_KEY)}")
    print(f"  TELEGRAM_TOKEN exists:   {bool(TELEGRAM_TOKEN)}")
    print(f"  TELEGRAM_CHAT_ID exists: {bool(TELEGRAM_CHAT_ID)}")
    print("  Tokeni se ne ispisuju zbog sigurnosti.")
    print()


# ─────────────────────────────────────────────────────────────────────
# TRADING CALENDAR
# ─────────────────────────────────────────────────────────────────────

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


def previous_trading_day(d):
    d -= timedelta(days=1)

    while not is_trading_day(d):
        d -= timedelta(days=1)

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


# ─────────────────────────────────────────────────────────────────────
# JSON STATE
# ─────────────────────────────────────────────────────────────────────

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
        print(f"Upozorenje: ne mogu učitati {POSLANO_FILE}: {e}")
        return default_state()


def spremi_poslano(state):
    with open(POSLANO_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def key_for(ticker, razina):
    return f"{ticker}_{razina:.4f}"


# ─────────────────────────────────────────────────────────────────────
# FMP API
# ─────────────────────────────────────────────────────────────────────

def dohvati_quote(ticker):
    if not FMP_API_KEY:
        print("  FMP_API_KEY nije postavljen.")
        return None

    url = (
        "https://financialmodelingprep.com/stable/quote"
        f"?symbol={ticker}&apikey={FMP_API_KEY}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
            data = json.loads(raw)

        if not data or not isinstance(data, list):
            print(f"  quote nema podatke {ticker}: {data}")
            return None

        q = data[0]

        price = q.get("price")
        open_ = q.get("open")

        if price is None:
            print(f"  quote nema price {ticker}: {q}")
            return None

        return {
            "price": round(float(price), 4),
            "open": round(float(open_ or 0), 4),
        }

    except Exception as e:
        print(f"  quote greska {ticker}: {repr(e)}")
        return None


def dohvati_historiju(ticker):
    if not FMP_API_KEY:
        print("  FMP_API_KEY nije postavljen.")
        return {}

    start = datetime.now(ET).date() - timedelta(days=HISTORY_DAYS * 4)

    url = (
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
        f"?symbol={ticker}&from={start.isoformat()}&apikey={FMP_API_KEY}"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8", errors="replace")
            data = json.loads(raw)

        if isinstance(data, dict):
            records = data.get("historical", [])
        elif isinstance(data, list):
            records = data
        else:
            print(f"  historija neočekivan format {ticker}: {type(data)}")
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
        print(f"  historija greska {ticker}: {repr(e)}")
        return {}


# ─────────────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────────────

def posalji_telegram_poruku(text):
    if not TELEGRAM_TOKEN:
        print("Telegram greska: TELEGRAM_TOKEN nije postavljen.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("Telegram greska: TELEGRAM_CHAT_ID nije postavljen.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    params = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=params, method="POST")

        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
            resp = json.loads(raw)

        print(f"Telegram response: {resp}")

        if resp.get("ok"):
            print("Telegram OK.")
            return True

        print(f"Telegram greska: {resp}")
        return False

    except Exception as e:
        print(f"Telegram exception: {repr(e)}")
        return False


def format_alert_message(g1, g2, g3):
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    poruka = f"STOCK ALERT — {now}\n"

    if g1:
        poruka += "\n1) PROBOJ RAZINE\n"
        poruka += "Dionice koje su tijekom dana probile zadanu razinu:\n"

        for u in g1:
            odmak = (u["price"] - u["razina"]) / u["razina"] * 100
            poruka += (
                f"{u['ticker']} | price {u['price']:.2f} | "
                f"razina {u['razina']:.2f} | {u['datum']} | {odmak:+.2f}%\n"
            )

    if g2:
        poruka += "\n2) PROBOJ + CLOSE IZNAD RAZINE\n"
        poruka += "Dionice koje su probile razinu i zatvorile dan iznad nje:\n"

        for u in g2:
            odmak = (u["close"] - u["razina"]) / u["razina"] * 100
            poruka += (
                f"{u['ticker']} | close {u['close']:.2f} | "
                f"razina {u['razina']:.2f} | {u['datum']} | {odmak:+.2f}%\n"
            )

    if g3:
        poruka += "\n3) PROBOJ + CLOSE + IDUĆI OPEN IZNAD RAZINE\n"
        poruka += "Dionice koje su ispunile prva dva uvjeta i idući dan otvorile iznad razine:\n"

        for u in g3:
            odmak = (u["open"] - u["razina"]) / u["razina"] * 100
            poruka += (
                f"{u['ticker']} | open {u['open']:.2f} | "
                f"razina {u['razina']:.2f} | open datum {u['datum']} | "
                f"G2 datum {u['g2_datum']} | {odmak:+.2f}%\n"
            )

    return poruka


def posalji_telegram(g1, g2, g3):
    if not (g1 or g2 or g3):
        return False

    text = format_alert_message(g1, g2, g3)
    return posalji_telegram_poruku(text)


def test_telegram():
    now = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")
    text = f"Stock Alert bot aktivan — test {now}"
    ok = posalji_telegram_poruku(text)

    if ok:
        print("Test Telegram poruka poslana.")
    else:
        print("Test Telegram poruka NIJE poslana.")


# ─────────────────────────────────────────────────────────────────────
# DUPLIKATI
# ─────────────────────────────────────────────────────────────────────

def provjeri_duplikate():
    seen = {}
    duplicates = []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = float(d["razina"])

        if ticker in seen:
            duplicates.append((ticker, seen[ticker], razina))
        else:
            seen[ticker] = razina

    if duplicates:
        print("UPOZORENJE: imaš duplikate tickera:")
        for ticker, old_level, new_level in duplicates:
            print(f"  {ticker}: {old_level} i {new_level}")
        print()


# ─────────────────────────────────────────────────────────────────────
# GLAVNA PROVJERA
# ─────────────────────────────────────────────────────────────────────

def provjeri():
    now_et = datetime.now(ET)
    today = now_et.date()
    today_s = today.isoformat()

    print(f"Provjera: {now_et.strftime('%d.%m.%Y %H:%M:%S ET')}")
    print(f"State file: {POSLANO_FILE}")
    print()

    debug_env()
    provjeri_duplikate()

    otvorena = burza_je_otvorena()
    prag = 1 + PRAG_POSTO / 100

    hist_days = last_n_trading_days(HISTORY_DAYS, today)

    print(
        f"Burza otvorena: {'DA' if otvorena else 'NE'} | "
        f"Zadnji završeni trading dani: {hist_days[0]} — {hist_days[-1]}"
    )
    print()

    state = ucitaj_poslano()
    novo_state = json.loads(json.dumps(state))

    g1_alerts = []
    g2_alerts = []
    g3_alerts = []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = float(d["razina"])
        trigger = razina * prag
        k = key_for(ticker, razina)

        try:
            hist = dohvati_historiju(ticker)
            quote = dohvati_quote(ticker) if otvorena else None

            price = quote["price"] if quote else None

            if quote and quote.get("open"):
                open_danas = quote["open"]
            else:
                open_danas = hist.get(today_s, {}).get("open")

            price_s = f"{price:.2f}" if price is not None else "—"
            open_s = f"{open_danas:.2f}" if open_danas is not None else "—"

            print(
                f"{ticker:<8} razina={razina:.2f} trigger={trigger:.2f} "
                f"price={price_s} open={open_s}",
                end=""
            )

            # ─────────────────────────────────────────────
            # G1: live proboj dok je burza otvorena
            # ─────────────────────────────────────────────

            g1_dates = set(novo_state["g1"].get(k, {}).get("datumi", []))

            if otvorena and price is not None and price >= trigger:
                if today_s not in g1_dates:
                    odmak = (price - razina) / razina * 100

                    print(
                        f"\n    G1: intraday proboj price={price:.2f} "
                        f"({odmak:+.2f}%)",
                        end=""
                    )

                    g1_alerts.append({
                        "ticker": ticker,
                        "price": price,
                        "razina": razina,
                        "datum": today_s,
                    })

                    g1_dates.add(today_s)

            if g1_dates:
                novo_state["g1"][k] = {
                    "ticker": ticker,
                    "razina": razina,
                    "datumi": sorted(g1_dates)[-HISTORY_DAYS:],
                }

            # ─────────────────────────────────────────────
            # G2: samo ako je taj dan prethodno imao G1
            #     i close je iznad triggera
            # ─────────────────────────────────────────────

            g2_dates = set(novo_state["g2"].get(k, {}).get("datumi", []))
            all_g1_dates = sorted(novo_state["g1"].get(k, {}).get("datumi", []))

            for g1_d_s in all_g1_dates:
                if g1_d_s in g2_dates:
                    continue

                g1_d = date.fromisoformat(g1_d_s)

                # Ne možemo potvrditi close za današnji dan dok dan nije završen.
                if g1_d >= today:
                    continue

                ohlc = hist.get(g1_d_s)

                if not ohlc:
                    continue

                close_val = ohlc.get("close")

                if close_val is None:
                    continue

                if close_val >= trigger:
                    odmak = (close_val - razina) / razina * 100

                    print(
                        f"\n    G2: imao G1 i close={close_val:.2f} "
                        f"{g1_d_s} ({odmak:+.2f}%)",
                        end=""
                    )

                    g2_alerts.append({
                        "ticker": ticker,
                        "close": close_val,
                        "razina": razina,
                        "datum": g1_d_s,
                    })

                    g2_dates.add(g1_d_s)

            if g2_dates:
                novo_state["g2"][k] = {
                    "ticker": ticker,
                    "razina": razina,
                    "datumi": sorted(g2_dates)[-HISTORY_DAYS:],
                }

            # ─────────────────────────────────────────────
            # G3: samo ako postoji G2 datum,
            #     idući trading dan open iznad triggera
            # ─────────────────────────────────────────────

            g3_dates = set(novo_state["g3"].get(k, {}).get("datumi", []))
            all_g2_dates = sorted(novo_state["g2"].get(k, {}).get("datumi", []))

            for g2_d_s in all_g2_dates:
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
                    odmak = (open_val - razina) / razina * 100

                    print(
                        f"\n    G3: nakon G2={g2_d_s}, open={open_val:.2f} "
                        f"{next_s} ({odmak:+.2f}%)",
                        end=""
                    )

                    g3_alerts.append({
                        "ticker": ticker,
                        "open": open_val,
                        "razina": razina,
                        "datum": next_s,
                        "g2_datum": g2_d_s,
                    })

                    g3_dates.add(next_s)

            if g3_dates:
                novo_state["g3"][k] = {
                    "ticker": ticker,
                    "razina": razina,
                    "datumi": sorted(g3_dates)[-HISTORY_DAYS:],
                }

            print()

        except Exception as e:
            print(f"\nGRESKA {ticker}: {repr(e)}")

    ukupno = len(g1_alerts) + len(g2_alerts) + len(g3_alerts)

    print()
    print(
        f"Rezultat: "
        f"G1={len(g1_alerts)}, "
        f"G2={len(g2_alerts)}, "
        f"G3={len(g3_alerts)}, "
        f"ukupno={ukupno}"
    )

    if ukupno:
        print("Šaljem Telegram alert...")

        telegram_ok = posalji_telegram(g1_alerts, g2_alerts, g3_alerts)

        if telegram_ok:
            spremi_poslano(novo_state)
            print("State spremljen jer je Telegram uspješno poslan.")
        else:
            print("Telegram NIJE poslan.")
            print("State NIJE spremljen, da se alert ne izgubi.")
    else:
        print("Nema novih upozorenja.")
        spremi_poslano(novo_state)
        print("State spremljen bez novih alerta.")

    print(f"Gotovo: {datetime.now(ET).strftime('%d.%m.%Y %H:%M:%S ET')}")


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

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
            print("Nema što resetirati — stock_alert_poslano.json ne postoji.")

    elif arg == "debug":
        debug_env()

    else:
        provjeri()
