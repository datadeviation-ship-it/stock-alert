import urllib.request
import urllib.parse
import json
import os
from datetime import datetime

# KONFIGURACIJA
import os
FMP_API_KEY      = os.environ.get("FMP_API_KEY", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

PRAG_POSTO = 0.5

# LISTA DIONICA — samo US tržište
DIONICE = [
    {
        "ticker":   "TDG",
        "naziv":    "TransDigm Group",
        "razina":   1350.00,
        "tip":      "iznad",
        "napomena": "ATH zona",
    },
    {
        "ticker":   "TDG",
        "naziv":    "TransDigm Group",
        "razina":   1100.00,
        "tip":      "ispod",
        "napomena": "Stop-loss razina",
    },
    {
        "ticker":   "NTDOY",
        "naziv":    "Nintendo ADR",
        "razina":   14.50,
        "tip":      "iznad",
        "napomena": "Switch 2 momentum",
    },
    {
        "ticker":   "NTDOY",
        "naziv":    "Nintendo ADR",
        "razina":   9.50,
        "tip":      "ispod",
        "napomena": "Dodaj poziciju",
    },
    {
        "ticker":   "AN",
        "naziv":    "AutoNation",
        "razina":   210.00,
        "tip":      "iznad",
        "napomena": "Ciklicni vrhunac zona",
    },
    {
        "ticker":   "AN",
        "naziv":    "AutoNation",
        "razina":   155.00,
        "tip":      "ispod",
        "napomena": "Jaka podrska",
    },
    {
        "ticker":   "CHTR",
        "naziv":    "Charter Communications",
        "razina":   250.00,
        "tip":      "iznad",
        "napomena": "FCF infleksija bull case",
    },
    {
        "ticker":   "CHTR",
        "naziv":    "Charter Communications",
        "razina":   140.00,
        "tip":      "ispod",
        "napomena": "Bear scenarij",
    },
    {
        "ticker":   "BRK-B",
        "naziv":    "Berkshire Hathaway B",
        "razina":   480.00,
        "tip":      "iznad",
        "napomena": "Novo 52-tjedno visoko",
    },
    {
        "ticker":   "BRK-B",
        "naziv":    "Berkshire Hathaway B",
        "razina":   420.00,
        "tip":      "ispod",
        "napomena": "Podrska",
    },
    {
        "ticker":   "META",
        "naziv":    "Meta Platforms",
        "razina":   620.00,
        "tip":      "iznad",
        "napomena": "ATH zona",
    },
    {
        "ticker":   "META",
        "naziv":    "Meta Platforms",
        "razina":   550.00,
        "tip":      "ispod",
        "napomena": "Promatraj reakciju",
    },
    {
        "ticker":   "NVR",
        "naziv":    "NVR Inc.",
        "razina":   8500.00,
        "tip":      "iznad",
        "napomena": "Stanogradnja tailwind",
    },
    {
        "ticker":   "NVR",
        "naziv":    "NVR Inc.",
        "razina":   7000.00,
        "tip":      "ispod",
        "napomena": "Podrska",
    },
]

# PAMCENJE POSLANIH
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

def kljuc(ticker, razina, tip):
    return f"{ticker}_{razina}_{tip}"

# FMP DOHVAT CIJENE
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

# TELEGRAM
def posalji_telegram(upozorenja):
    if not upozorenja:
        return False

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    broj = len(upozorenja)

    poruka = f"*STOCK ALERT* {now}\n"
    poruka += f"_{broj} signal{'a' if broj > 1 else ''}_\n\n"

    for u in upozorenja:
        je_gore   = u["tip"] == "iznad"
        ikona     = "\U0001f7e2" if je_gore else "\U0001f534"
        smjer     = "PROBIO GORE" if je_gore else "PALO ISPOD"
        posto_str = f"+{u['posto']:.2f}%" if je_gore else f"{u['posto']:.2f}%"

        poruka += f"{ikona} *{u['ticker']}*\n"
        poruka += f"Cijena: `{u['cijena']:.2f} USD`\n"
        poruka += f"{smjer} razine `{u['razina']:.2f}` ({posto_str})\n"
        poruka += f"_{u['napomena']}_\n\n"

    poruka += "_Provjeri graf._"

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

# GLAVNA LOGIKA
def provjeri():
    print(f"Provjera: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"Prag: {PRAG_POSTO}%")

    poslano         = ucitaj_poslano()
    nova_upozorenja = []

    unique = {}
    for d in DIONICE:
        if d["ticker"] not in unique:
            unique[d["ticker"]] = None

    print("Dohvacam cijene...")
    for ticker in unique:
        cijena = dohvati_cijenu(ticker)
        unique[ticker] = cijena
        status = f"{cijena:.4f}" if cijena else "nije dostupno"
        print(f"  {ticker:<16} {status}")

    for d in DIONICE:
        ticker   = d["ticker"]
        razina   = d["razina"]
        tip      = d["tip"]
        cijena   = unique.get(ticker)

        if cijena is None:
            continue

        k           = kljuc(ticker, razina, tip)
        posto_odmak = ((cijena - razina) / razina) * 100

        probito = (
            tip == "iznad" and cijena > razina and posto_odmak >= PRAG_POSTO
        ) or (
            tip == "ispod" and cijena < razina and abs(posto_odmak) >= PRAG_POSTO
        )

        if probito:
            if k not in poslano:
                smjer = "gore" if tip == "iznad" else "dolje"
                print(f"ALARM {ticker}: razina {razina:.2f} probita {smjer} ({posto_odmak:+.2f}%)")
                nova_upozorenja.append({
                    "ticker":   ticker,
                    "naziv":    d["naziv"],
                    "cijena":   cijena,
                    "razina":   razina,
                    "tip":      tip,
                    "napomena": d["napomena"],
                    "posto":    posto_odmak,
                })
                poslano[k] = {
                    "poslano_u":         datetime.now().isoformat(),
                    "cijena_u_trenutku": cijena,
                    "odmak_posto":       round(posto_odmak, 4),
                }
            else:
                print(f"Vec poslano: {ticker} razina {razina:.2f}")
        else:
            if k in poslano:
                print(f"Reset: {ticker} razina {razina:.2f}")
                del poslano[k]

    if nova_upozorenja:
        print(f"Saljem Telegram: {len(nova_upozorenja)} upozorenje(a)")
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
