"""
stock_alert_telegram.py
=======================
Prati cijene dionica i šalje Telegram poruku kada dionica
probije zadanu razinu za više od 0,5%.

Potrebno:
    pip install --user requests

Pokretanje:
    python stock_alert_telegram.py

Postavljanje Telegram bota (3 minute):
    1. Otvori Telegram → traži @BotFather
    2. Pošalji /newbot → daj ime botu → dobiješ TOKEN
    3. Otvori svog novog bota → pošalji mu bilo što (npr. "zdravo")
    4. Otvori u browseru:
       https://api.telegram.org/bot<TOKEN>/getUpdates
    5. U JSON odgovoru pronađi "id" unutar "chat" — to je tvoj CHAT_ID
    6. Upiši TOKEN i CHAT_ID dolje
"""

import urllib.request
import urllib.parse
import json
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  KONFIGURACIJA
# ─────────────────────────────────────────────

import os

FMP_API_KEY      = os.environ.get("UuXfLNxQPWcQH9hTR7LGrZRyTYo6SCi6", "")
TELEGRAM_TOKEN   = os.environ.get("8789938727:AAGYZ3-aeR5UeYNhijK6jR02c4sCR7nbQTE", "")
TELEGRAM_CHAT_ID = os.environ.get("885140350", "")    

PRAG_POSTO = 0.5   # alarm kada cijena probije razinu za 0,5%+

# ─────────────────────────────────────────────
#  LISTA DIONICA
# ─────────────────────────────────────────────

DIONICE = [
    # ── Tvoje pozicije ───────────────────────
    {
        "ticker":   "FFH.TO",
        "naziv":    "Fairfax Financial",
        "valuta":   "CAD",
        "razina":   1500.00,
        "tip":      "iznad",
        "napomena": "Otpor — razmatraj prodaju",
    },
    {
        "ticker":   "FFH.TO",
        "naziv":    "Fairfax Financial",
        "valuta":   "CAD",
        "razina":   1300.00,
        "tip":      "ispod",
        "napomena": "Podrška — razmatraj dodavanje",
    },
    {
        "ticker":   "TDG",
        "naziv":    "TransDigm Group",
        "valuta":   "USD",
        "razina":   1350.00,
        "tip":      "iznad",
        "napomena": "ATH zona",
    },
    {
        "ticker":   "TDG",
        "naziv":    "TransDigm Group",
        "valuta":   "USD",
        "razina":   1100.00,
        "tip":      "ispod",
        "napomena": "Stop-loss razina",
    },
    {
        "ticker":   "NTDOY",
        "naziv":    "Nintendo ADR",
        "valuta":   "USD",
        "razina":   14.50,
        "tip":      "iznad",
        "napomena": "Switch 2 momentum",
    },
    {
        "ticker":   "NTDOY",
        "naziv":    "Nintendo ADR",
        "valuta":   "USD",
        "razina":   9.50,
        "tip":      "ispod",
        "napomena": "Dodaj poziciju",
    },
    {
        "ticker":   "AN",
        "naziv":    "AutoNation",
        "valuta":   "USD",
        "razina":   210.00,
        "tip":      "iznad",
        "napomena": "Ciklični vrhunac zona",
    },
    {
        "ticker":   "AN",
        "naziv":    "AutoNation",
        "valuta":   "USD",
        "razina":   155.00,
        "tip":      "ispod",
        "napomena": "Jaka podrška",
    },
    {
        "ticker":   "VIDRALA.MC",
        "naziv":    "Vidrala",
        "valuta":   "EUR",
        "razina":   105.00,
        "tip":      "iznad",
        "napomena": "Proboj otpora",
    },
    {
        "ticker":   "VIDRALA.MC",
        "naziv":    "Vidrala",
        "valuta":   "EUR",
        "razina":   82.00,
        "tip":      "ispod",
        "napomena": "Podrška",
    },
    # ── Dodatne dionice ──────────────────────
    {
        "ticker":   "CHTR",
        "naziv":    "Charter Communications",
        "valuta":   "USD",
        "razina":   250.00,
        "tip":      "iznad",
        "napomena": "FCF infleksija — bull case",
    },
    {
        "ticker":   "CHTR",
        "naziv":    "Charter Communications",
        "valuta":   "USD",
        "razina":   140.00,
        "tip":      "ispod",
        "napomena": "Bear scenarij",
    },
    {
        "ticker":   "BRK-B",
        "naziv":    "Berkshire Hathaway B",
        "valuta":   "USD",
        "razina":   480.00,
        "tip":      "iznad",
        "napomena": "Novo 52-tjedno visoko",
    },
    {
        "ticker":   "META",
        "naziv":    "Meta Platforms",
        "valuta":   "USD",
        "razina":   550.00,
        "tip":      "ispod",
        "napomena": "Promatraj reakciju",
    },
    {
        "ticker":   "NVR",
        "naziv":    "NVR Inc.",
        "valuta":   "USD",
        "razina":   8500.00,
        "tip":      "iznad",
        "napomena": "Stanogradnja tailwind",
    },
    # ── Europske dionice ─────────────────────
    {
        "ticker":   "AIR.PA",
        "naziv":    "Airbus",
        "valuta":   "EUR",
        "razina":   175.00,
        "tip":      "iznad",
        "napomena": "Obrambeni aerospace bull",
    },
    {
        "ticker":   "AIR.PA",
        "naziv":    "Airbus",
        "valuta":   "EUR",
        "razina":   140.00,
        "tip":      "ispod",
        "napomena": "Supply chain rizik",
    },
    {
        "ticker":   "SAP.DE",
        "naziv":    "SAP SE",
        "valuta":   "EUR",
        "razina":   240.00,
        "tip":      "iznad",
        "napomena": "Cloud momentum — ATH zona",
    },
    {
        "ticker":   "SAP.DE",
        "naziv":    "SAP SE",
        "valuta":   "EUR",
        "razina":   156.00,
        "tip":      "iznad",
        "napomena": "Dugoročna podrška",
    },
    {
        "ticker":   "MC.PA",
        "naziv":    "LVMH",
        "valuta":   "EUR",
        "razina":   462.00,
        "tip":      "ispod",
        "napomena": "Luxury recovery — China demand",
    },
    {
        "ticker":   "MC.PA",
        "naziv":    "LVMH",
        "valuta":   "EUR",
        "razina":   480.00,
        "tip":      "ispod",
        "napomena": "Višegodišnja podrška",
    },
]

# ─────────────────────────────────────────────
#  PAMĆENJE POSLANIH — sprječava duplikate
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
#  FMP — DOHVAT CIJENA
# ─────────────────────────────────────────────

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
        print(f"    Greška {ticker}: {e}")
        return None

# ─────────────────────────────────────────────
#  TELEGRAM — SLANJE PORUKE
# ─────────────────────────────────────────────

def posalji_telegram(upozorenja):
    """Šalje jednu Telegram poruku sa svim upozorenjima."""
    if not upozorenja:
        return False

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    linije = [f"📊 *Dionica probila razinu* — {now}\n"]

    for u in upozorenja:
        je_gore   = u["tip"] == "iznad"
        ikona     = "🟢" if je_gore else "🔴"
        smjer     = "GORE" if je_gore else "DOLJE"
        posto_str = f"+{u['posto']:.2f}%" if je_gore else f"{u['posto']:.2f}%"

        linije.append(
            f"{ikona} *{u['ticker']}* — {u['naziv']}\n"
            f"   Cijena: `{u['cijena']:.2f} {u['valuta']}`\n"
            f"   {smjer} od razine `{u['razina']:.2f}` ({posto_str})\n"
            f"   _{u['napomena']}_\n"
        )

    linije.append("_Nije investicijski savjet._")
    tekst = "\n".join(linije)

    # Telegram sendMessage API poziv
    params = urllib.parse.urlencode({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       tekst,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        req = urllib.request.Request(url, data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            odgovor = json.loads(r.read())
        if odgovor.get("ok"):
            print(f"  Telegram poruka poslana.")
            return True
        else:
            print(f"  Telegram greška: {odgovor}")
            return False
    except Exception as e:
        print(f"  Telegram greška: {e}")
        return False


def test_telegram():
    """Pošalji test poruku da provjeriš radi li veza."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    params = urllib.parse.urlencode({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       f"Provjera veze — {now}\nStock alert bot aktivan.",
        "parse_mode": "Markdown",
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        req = urllib.request.Request(url, data=params, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            odgovor = json.loads(r.read())
        if odgovor.get("ok"):
            print("  Test poruka uspješno poslana na Telegram.")
        else:
            print(f"  Test greška: {odgovor}")
    except Exception as e:
        print(f"  Test greška: {e}")

# ─────────────────────────────────────────────
#  GLAVNA LOGIKA
# ─────────────────────────────────────────────

def provjeri():
    print(f"\n{'='*55}")
    print(f"  Provjera: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"  Prag: {PRAG_POSTO}%")
    print(f"{'='*55}")

    poslano         = ucitaj_poslano()
    nova_upozorenja = []

    # Skupi unique tickere
    unique = {}
    for d in DIONICE:
        if d["ticker"] not in unique:
            unique[d["ticker"]] = None

    # Dohvati sve cijene
    print("\n  Dohvaćam cijene...\n")
    for ticker in unique:
        cijena = dohvati_cijenu(ticker)
        unique[ticker] = cijena
        status = f"{cijena:.4f}" if cijena else "nije dostupno"
        print(f"  {ticker:<16} {status}")

    print()

    # Provjeri razine
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
            tip == "iznad"
            and cijena > razina
            and posto_odmak >= PRAG_POSTO
        ) or (
            tip == "ispod"
            and cijena < razina
            and abs(posto_odmak) >= PRAG_POSTO
        )

        if probito:
            if k not in poslano:
                smjer = "gore" if tip == "iznad" else "dolje"
                print(f"  ALARM  {ticker}: razina {razina:.2f} "
                      f"probita {smjer} ({posto_odmak:+.2f}%)")
                nova_upozorenja.append({
                    "ticker":   ticker,
                    "naziv":    d["naziv"],
                    "cijena":   cijena,
                    "razina":   razina,
                    "tip":      tip,
                    "napomena": d["napomena"],
                    "valuta":   d["valuta"],
                    "posto":    posto_odmak,
                })
                poslano[k] = {
                    "poslano_u":         datetime.now().isoformat(),
                    "cijena_u_trenutku": cijena,
                    "odmak_posto":       round(posto_odmak, 4),
                }
            else:
                print(f"  vec poslano  {ticker} razina {razina:.2f}")
        else:
            if k in poslano:
                print(f"  reset  {ticker} razina {razina:.2f} "
                      f"— cijena se vratila")
                del poslano[k]

    # Pošalji Telegram
    if nova_upozorenja:
        print(f"\n  Šaljem Telegram — {len(nova_upozorenja)} upozorenje(a)...")
        posalji_telegram(nova_upozorenja)
    else:
        print("\n  Nema novih upozorenja.")

    spremi_poslano(poslano)
    print(f"\n  Gotovo — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*55}\n")


# ─────────────────────────────────────────────
#  POKRETANJE
#
#  Normalno pokretanje:
#      python stock_alert_telegram.py
#
#  Samo test Telegrama (bez provjere cijena):
#      python stock_alert_telegram.py test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("\n  Šaljem test poruku na Telegram...")
        test_telegram()
    else:
        provjeri()
