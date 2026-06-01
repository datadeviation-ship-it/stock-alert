import urllib.request
import urllib.parse
import json
import os
from datetime import datetime

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
    """
    Vraća dict s ključevima:
      price      — trenutna cijena (intraday)
      open       — otvaranje danas
      previousClose — zatvaranje jučer
    """
    url = (f"https://financialmodelingprep.com/stable/quote"
           f"?symbol={ticker}&apikey={FMP_API_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data and isinstance(data, list) and data[0].get("price"):
            q = data[0]
            return {
                "price":         round(float(q.get("price", 0) or 0), 4),
                "open":          round(float(q.get("open", 0) or 0), 4),
                "previousClose": round(float(q.get("previousClose", 0) or 0), 4),
            }
        return None
    except Exception as e:
        print(f"  Greska {ticker}: {e}")
        return None

# ── TELEGRAM ──────────────────────────────────────────────────────

def posalji_telegram(grupa1, grupa2, grupa3):
    """
    Šalje jednu poruku s tri sekcije.
    Grupu šalje samo ako ima stavki.
    """
    if not (grupa1 or grupa2 or grupa3):
        return False

    now    = datetime.now().strftime("%d.%m.%Y %H:%M")
    poruka = f"*STOCK ALERT* {now}\n"

    if grupa1:
        poruka += "\n*① Intraday proboj razine*\n"
        for u in grupa1:
            odmak = ((u["cijena"] - u["razina"]) / u["razina"]) * 100
            poruka += f"  *{u['ticker']}*  `{u['cijena']:.2f}`  ({odmak:+.1f}% od {u['razina']:.2f})\n"

    if grupa2:
        poruka += "\n*② Zatvorilo iznad razine*\n"
        for u in grupa2:
            odmak = ((u["close"] - u["razina"]) / u["razina"]) * 100
            poruka += f"  *{u['ticker']}*  close `{u['close']:.2f}`  ({odmak:+.1f}% od {u['razina']:.2f})\n"

    if grupa3:
        poruka += "\n*③ Danas otvorilo iznad razine*\n"
        for u in grupa3:
            odmak = ((u["open"] - u["razina"]) / u["razina"]) * 100
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
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
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

# ── LOGIKA PROVJERE ───────────────────────────────────────────────

def provjeri():
    """
    Tri grupe alarma:

    GRUPA 1 — Intraday proboj:
      Trenutna cijena > razina * (1 + PRAG_POSTO/100)
      Alarm se šalje jednom dok cijena padne ispod razine.

    GRUPA 2 — Zatvaranje iznad razine:
      previousClose > razina * (1 + PRAG_POSTO/100)
      Uvjet: prethodni dan je zatvorio iznad razine.
      Alarm se šalje jednom po sesiji zatvaranja.

    GRUPA 3 — Otvaranje iznad razine (dan nakon zatvaranja):
      Uvjet: previousClose je već bio iznad razine (tj. grupa 2 je zadovoljena)
             I danas open > razina * (1 + PRAG_POSTO/100)
      Ovo je najjači signal — probijena razina + gap open iznad nje.
    """
    print(f"Provjera: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

    poslano  = ucitaj_poslano()
    grupa1   = []  # intraday proboj
    grupa2   = []  # zatvorilo iznad
    grupa3   = []  # otvorilo iznad (dan nakon zatvaranja)

    prag = 1 + PRAG_POSTO / 100

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

        print(f"  {ticker:<8}  price={price:.2f}  open={open_:.2f}  prevClose={prev_c:.2f}  razina={razina:.2f}")

        # ── Ključevi za praćenje stanja ──────────────────────────
        k1 = f"{ticker}_{razina}_g1"   # intraday
        k2 = f"{ticker}_{razina}_g2"   # close
        k3 = f"{ticker}_{razina}_g3"   # open

        # ── GRUPA 1: intraday proboj ──────────────────────────────
        if price >= razina * prag:
            if k1 not in poslano:
                odmak = (price - razina) / razina * 100
                print(f"    G1 ALARM: {ticker} {price:.2f} (+{odmak:.1f}%)")
                grupa1.append({"ticker": ticker, "cijena": price, "razina": razina})
                poslano[k1] = {
                    "poslano_u": datetime.now().isoformat(),
                    "cijena":    price,
                }
        else:
            # Reset kad cijena padne ispod razine
            if k1 in poslano:
                print(f"    G1 reset: {ticker}")
                del poslano[k1]

        # ── GRUPA 2: zatvaranje iznad razine ─────────────────────
        # previousClose je zadnje zatvaranje (jučerašnji dan)
        if prev_c >= razina * prag:
            if k2 not in poslano:
                odmak = (prev_c - razina) / razina * 100
                print(f"    G2 ALARM: {ticker} close={prev_c:.2f} (+{odmak:.1f}%)")
                grupa2.append({"ticker": ticker, "close": prev_c, "razina": razina})
                poslano[k2] = {
                    "poslano_u": datetime.now().isoformat(),
                    "close":     prev_c,
                }
        else:
            if k2 in poslano:
                print(f"    G2 reset: {ticker}")
                del poslano[k2]

        # ── GRUPA 3: otvaranje iznad razine (dan nakon close) ─────
        # Uvjet: previousClose je bio iznad razine (G2 zadovoljen)
        #        I današnji open je iznad razine
        prev_close_probijen = prev_c >= razina * prag
        open_iznad          = open_  >= razina * prag

        if prev_close_probijen and open_iznad:
            if k3 not in poslano:
                odmak = (open_ - razina) / razina * 100
                print(f"    G3 ALARM: {ticker} open={open_:.2f} (+{odmak:.1f}%)")
                grupa3.append({"ticker": ticker, "open": open_, "razina": razina})
                poslano[k3] = {
                    "poslano_u": datetime.now().isoformat(),
                    "open":      open_,
                }
        else:
            # Reset G3 kad uvjet prestane biti zadovoljen
            if k3 in poslano:
                print(f"    G3 reset: {ticker}")
                del poslano[k3]

    # ── Pošalji sve grupe u jednoj poruci ────────────────────────
    ukupno = len(grupa1) + len(grupa2) + len(grupa3)
    if ukupno:
        print(f"\nSaljem Telegram: G1={len(grupa1)}, G2={len(grupa2)}, G3={len(grupa3)}")
        posalji_telegram(grupa1, grupa2, grupa3)
    else:
        print("Nema novih upozorenja.")

    spremi_poslano(poslano)
    print(f"Gotovo: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_telegram()
    else:
        provjeri()
