import urllib.request
import urllib.parse
import json
import os
from datetime import datetime

FMP_API_KEY      = os.environ.get("FMP_API_KEY", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

PRAG_POSTO = 0.5

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
    {"ticker": "WELL",  "razina": 222.00},
    {"ticker": "GEHC",  "razina": 64.80},
    {"ticker": "APLD",  "razina": 47.80},
    {"ticker": "LRCX",  "razina": 302.00},
    {"ticker": "H",  "razina": 177.50},
    {"ticker": "KLAR",  "razina": 16.80},
    {"ticker": "CSCO",  "razina": 119.50},
    {"ticker": "NVTS",  "razina": 24.20},
    {"ticker": "AGX",  "razina": 743.00},
    {"ticker": "STM",  "razina": 67.00},
    {"ticker": "RDW",  "razina": 15.50},
    {"ticker": "GRRR",  "razina": 15.80},
]

POSLANO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "stock_alert_poslano.json"
)

def ucitaj_poslano():
    if os.path.exists(POSLANO_FILE):
        with open(POSLANO_FILE, "r") as f:
            return json.load(f)
    return {}

def spremi_poslano(poslano):
    with open(POSLANO_FILE, "w") as f:
        json.dump(poslano, f, indent=2, ensure_ascii=False)

def dohvati_cijenu(ticker):
    url = (f"https://financialmodelingprep.com/stable/quote"
           f"?symbol={ticker}&apikey={FMP_API_KEY}")
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data and isinstance(data, list) and data[0].get("price"):
            return round(float(data[0]["price"]), 4)
        return None
    except Exception as e:
        print(f"Greska {ticker}: {e}")
        return None

def posalji_telegram(upozorenja):
    if not upozorenja:
        return False

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    poruka = f"*STOCK ALERT* {now}\n\n"

    for u in upozorenja:
        poruka += f"*{u['ticker']}*   `{u['cijena']:.2f} USD`\n"

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
        else:
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
        if odgovor.get("ok"):
            print("Test poruka poslana.")
        else:
            print(f"Greska: {odgovor}")
    except Exception as e:
        print(f"Greska: {e}")

def provjeri():
    print(f"Provjera: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

    poslano         = ucitaj_poslano()
    nova_upozorenja = []

    for d in DIONICE:
        ticker = d["ticker"]
        razina = d["razina"]
        k      = f"{ticker}_{razina}"

        cijena = dohvati_cijenu(ticker)
        if cijena is None:
            print(f"  {ticker:<8} nije dostupno")
            continue

        print(f"  {ticker:<8} {cijena:.4f}")

        posto_odmak = ((cijena - razina) / razina) * 100
        probilo     = cijena > razina and posto_odmak >= PRAG_POSTO

        if probilo:
            if k not in poslano:
                print(f"  ALARM {ticker}: {cijena:.2f} probilo {razina:.2f} ({posto_odmak:+.2f}%)")
                nova_upozorenja.append({
                    "ticker": ticker,
                    "cijena": cijena,
                })
                poslano[k] = {
                    "poslano_u":         datetime.now().isoformat(),
                    "cijena_u_trenutku": cijena,
                }
            else:
                print(f"  Vec poslano: {ticker}")
        else:
            if k in poslano:
                print(f"  Reset: {ticker}")
                del poslano[k]

    if nova_upozorenja:
        print(f"Saljem Telegram: {len(nova_upozorenja)} alarm(a)")
        posalji_telegram(nova_upozorenja)
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
