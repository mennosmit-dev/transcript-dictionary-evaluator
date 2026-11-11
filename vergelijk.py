"""Vergelijk een HappyScribe-transcript (.md) met een Teams-transcript (.docx)
en zet de verschillen als kandidaat-woorden voor de Copilot-woordenlijst in een CSV.

Alles draait lokaal; er gaat niets naar buiten.

Gebruik:
    python vergelijk.py happyscribe.md teams.docx --datum 2026-10-07
    python vergelijk.py happyscribe.md teams.docx --meeting teamoverleg-1 --datum 2026-10-07 --debug

Uitvoer:
    uitvoer/<meeting>_kandidaten.csv   kandidaten van deze vergadering
    register.csv                       alle kandidaten over alle vergaderingen (hier beoordeel je)
    meetings.csv                       cijfers per vergadering, voor rapportage
Standaard wordt woordenlijst.csv in deze map als huidige lijst gebruikt. Zie register.py voor de rest.
"""

import argparse
import csv
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree

import register

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Vulwoorden en functiewoorden: een verschil dat alleen hieruit bestaat is ruis.
STOPWOORDEN = set("""
de het een en of maar dus dan als dat die dit deze er hier daar ik je jij u we wij ze zij hij
het is was ben bent zijn wordt worden heb hebt heeft hebben had kan kun kunnen moet moeten wil
willen zal zou gaat gaan ga doe doet doen van in op aan met voor naar om bij uit over tot door
te niet geen wel ook nog al toch even maar heel echt gewoon zo nou ja nee oké ok okay eh uh uhm
hm hmm ehm mm ah oh o nu wat wie waar hoe waarom welke want omdat mijn mij me jouw onze ons hun
the a an and or but so to of in on at for with is are was be it this that you we they i yeah
yes no um uh like just right
""".split())

TIJD = re.compile(r"\[?\(?\b\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\b\)?\]?")
TOKEN = re.compile(r"[&@]?\w+(?:[-'’.&]\w+)*", re.UNICODE)


# ---------- inlezen ----------

def lees_docx(pad: Path) -> list[str]:
    with zipfile.ZipFile(pad) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    regels = []
    for p in root.iter(W_NS + "p"):
        # Teams zet een hele beurt in één alinea met regelafbrekingen: "Naam   0:03<br>tekst".
        delen = []
        for el in p.iter():
            if el.tag == W_NS + "t":
                delen.append(el.text or "")
            elif el.tag in (W_NS + "br", W_NS + "cr"):
                delen.append("\n")
            elif el.tag == W_NS + "tab":
                delen.append(" ")
        regels.extend("".join(delen).split("\n"))
    return regels


def lees_md(pad: Path) -> list[str]:
    tekst = pad.read_text(encoding="utf-8", errors="replace")
    tekst = re.sub(r"[*_#>`]+", " ", tekst)          # markdown-opmaak weg
    return tekst.splitlines()


def schoon(regels: list[str]) -> str:
    """Haal tijdstempels, sprekerlabels en kopregels weg; houd de gesproken tekst over."""
    regels = [r.strip() for r in regels]
    # Korte regels die vaak terugkomen zijn sprekernamen ("Jan de Vries", "Speaker 1").
    kort = Counter(TIJD.sub("", r).strip() for r in regels if len(r.split()) <= 6)
    sprekers = {r for r, n in kort.items() if r and n >= 3 and len(r.split()) <= 4}

    uit = []
    for r in regels:
        if not r or "-->" in r:
            continue
        had_tijd = bool(TIJD.search(r))
        zonder_tijd = TIJD.sub(" ", r).strip()
        if not zonder_tijd:
            continue
        if zonder_tijd in sprekers:
            continue
        # Sprekerregel met tijd, zoals "Jan de Vries   0:03": weg.
        if had_tijd and len(zonder_tijd.split()) <= 4:
            continue
        # Sprekerprefix "Naam: tekst" of "Speaker 1: tekst".
        m = re.match(r"^([^:]{1,40}):\s+(.*)$", zonder_tijd)
        if m and len(m.group(1).split()) <= 4:
            zonder_tijd = m.group(2)
        uit.append(zonder_tijd)
    return "\n".join(uit)


def tokens(tekst: str) -> list[str]:
    return TOKEN.findall(tekst)


def norm(t: str) -> str:
    return t.lower().replace("’", "'")


def plat(woorden) -> str:
    """Vergelijkingsvorm zonder spaties/streepjes: 'cross-sell' == 'cross sell'."""
    return re.sub(r"[\W_]+", "", " ".join(woorden).lower())


# ---------- vergelijken ----------

def lees_lijst(pad: Path | None) -> tuple[list[str], set[str]]:
    """Geeft (termen, bekende 'sounds like'-varianten), beide in platte vorm.

    .csv = het uploadformaat van de Copilot-dictionary: kolom 1 de term,
    kolom 2 de 'Sounds like'-varianten gescheiden door ';'. Anders: één term per regel.
    """
    if not pad:
        return [], set()
    termen, varianten = [], set()
    tekst = pad.read_text(encoding="utf-8-sig", errors="replace")
    if pad.suffix.lower() == ".csv":
        rijen = list(csv.reader(tekst.splitlines()))
        if any(len(r) > 4 for r in rijen):
            sys.exit(f"{pad} is geen geldige CSV meer (rij met te veel kolommen, kapotte quote?).")
        for rij in rijen[1:]:
            if rij and rij[0].strip():
                termen.append(plat([rij[0]]))
                if len(rij) > 1:
                    varianten.update(plat([v]) for v in rij[1].split(";") if v.strip())
    else:
        for r in tekst.splitlines():
            r = r.strip().strip("-*|").strip()
            if r and not r.startswith("#"):
                termen.append(plat([r]))
    return [t for t in termen if t], varianten


def vergelijk(hs: list[str], teams: list[str], max_len: int):
    a = [norm(t) for t in hs]
    b = [norm(t) for t in teams]
    sm = SequenceMatcher(None, a, b, autojunk=False)
    paren = []
    kleine_letter_vormen = {w for w in hs if w.islower()}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            # Zelfde woord, andere hoofdletters: telt alleen bij namen en afkortingen.
            for k in range(i2 - i1):
                h, t = hs[i1 + k], teams[j1 + k]
                if h != t and is_eigennaam([h], kleine_letter_vormen):
                    context = " ".join(hs[max(0, i1 + k - 6):i1 + k] + ["[" + h + "]"] + hs[i1 + k + 1:i1 + k + 7])
                    paren.append((h, t, context, "hoofdletters"))
            continue
        if op not in ("replace", "delete"):
            continue
        if i2 - i1 > max_len or j2 - j1 > max_len:
            continue  # te lang: waarschijnlijk een stuk dat niet goed uitlijnt
        hs_deel, teams_deel = hs[i1:i2], teams[j1:j2]
        if all(norm(w) in STOPWOORDEN for w in hs_deel):
            continue
        if all(w.isdigit() for w in hs_deel):
            continue
        if not teams_deel:
            soort = "ontbreekt in Teams"
        elif plat(hs_deel) == plat(teams_deel):
            soort = "spatie/streepje"  # DataVlinder -> Data Vlinder
        else:
            soort = "ander woord"
        context = " ".join(hs[max(0, i1 - 6):i1] + ["[" + " ".join(hs_deel) + "]"] + hs[i2:i2 + 6])
        paren.append((" ".join(hs_deel), " ".join(teams_deel), context, soort))
    return paren, sm.ratio()


def is_eigennaam(woorden: list[str], kleine_letter_vormen: set[str]) -> bool:
    for w in woorden:
        if norm(w) in STOPWOORDEN:
            continue
        if any(c.isupper() for c in w[1:]) or w.startswith("&"):  # NWL, DataVlinder, &Co
            return True
        if w[:1].isupper() and norm(w) not in kleine_letter_vormen:
            return True
        if any(c.isdigit() for c in w) and any(c.isalpha() for c in w):  # M365
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("happyscribe", type=Path, help="HappyScribe-export (.md)")
    ap.add_argument("teams", type=Path, help="Teams-transcript (.docx)")
    ap.add_argument("--lijst", type=Path, default=Path(register.WOORDENLIJST),
                    help="huidige woordenlijst (standaard woordenlijst.csv in deze map)")
    ap.add_argument("--meeting", help="korte naam van de vergadering (standaard: bestandsnaam)")
    ap.add_argument("--datum", default=date.today().isoformat(), help="datum van de vergadering, JJJJ-MM-DD")
    ap.add_argument("--niet-registreren", action="store_true", help="alleen de CSV maken, register en log niet bijwerken")
    ap.add_argument("--max", type=int, default=5, help="max. woorden per verschil (standaard 5)")
    ap.add_argument("--uit", type=Path, default=Path(__file__).parent / "uitvoer")
    ap.add_argument("--debug", action="store_true", help="schrijf ook de opgeschoonde teksten weg")
    args = ap.parse_args()
    for pad in (args.happyscribe, args.teams, args.lijst):
        if pad and not pad.exists():
            sys.exit(f"Bestand niet gevonden: {pad}  (map: {Path.cwd()})")

    hs_tekst = schoon(lees_md(args.happyscribe))
    teams_tekst = schoon(lees_docx(args.teams))
    hs, teams = tokens(hs_tekst), tokens(teams_tekst)
    if not hs or not teams:
        sys.exit("Een van de transcripten is leeg na opschonen. Draai met --debug en kijk in uitvoer/.")

    paren, overeenkomst = vergelijk(hs, teams, args.max)
    lijst, bekende_varianten = lees_lijst(args.lijst)
    kleine_letter_vormen = {w for w in hs if w.islower()}
    # Spatie/streepje-verschillen bij gewone woorden (e-mail/email) zijn meestal ruis,
    # behalve als de term al op de lijst staat (cross-sell).
    paren = [p for p in paren if p[3] != "spatie/streepje"
             or is_eigennaam(p[0].split(), kleine_letter_vormen)
             or any(t and t in plat([p[0]]) for t in lijst)]

    groepen = defaultdict(list)
    for hs_frase, teams_frase, context, soort in paren:
        groepen[hs_frase.lower()].append((hs_frase, teams_frase, context, soort))

    rijen = []
    for sleutel, items in groepen.items():
        hs_frase = Counter(i[0] for i in items).most_common(1)[0][0]
        teams_varianten = Counter(i[1] or "(niets)" for i in items)
        gelijkenis = max(SequenceMatcher(None, plat([hs_frase]), plat([t])).ratio() for t in teams_varianten)
        p = plat([hs_frase])
        rijen.append({
            "kandidaat (HappyScribe)": hs_frase,
            "Teams schreef": " | ".join(f"{t} ({n}x)" for t, n in teams_varianten.most_common(3)),
            "aantal": len(items),
            "soort verschil": Counter(i[3] for i in items).most_common(1)[0][0],
            "gelijkenis": round(gelijkenis, 2),
            "eigennaam/afkorting": "ja" if is_eigennaam(hs_frase.split(), kleine_letter_vormen) else "",
            "al op lijst": "ja" if lijst and any(t and (t in p or (len(p) >= 4 and p in t)) for t in lijst) else "",
            "Teams-variant al in sounds like": "ja" if any(plat([t]) in bekende_varianten for t in teams_varianten) else "",
            "voorbeeld": items[0][2],
            "oordeel (goed/fout HS/geen term)": "",
        })

    # Eerst wat waarschijnlijk een term is: eigennaam, vaker gezien, klinkt hetzelfde.
    rijen.sort(key=lambda r: (r["eigennaam/afkorting"] == "ja", r["aantal"], r["gelijkenis"]), reverse=True)

    args.uit.mkdir(parents=True, exist_ok=True)
    naam = args.meeting or args.happyscribe.stem
    csv_pad = args.uit / f"{naam}_kandidaten.csv"
    register.schrijf_csv(csv_pad, rijen, list(rijen[0].keys()) if rijen else ["kandidaat (HappyScribe)"], ";")
    if args.debug:
        (args.uit / f"{naam}_schoon_happyscribe.txt").write_text(hs_tekst, encoding="utf-8")
        (args.uit / f"{naam}_schoon_teams.txt").write_text(teams_tekst, encoding="utf-8")

    print(f"HappyScribe: {len(hs)} woorden, Teams: {len(teams)} woorden, overeenkomst {overeenkomst:.0%}")
    print(f"{len(rijen)} kandidaten ({sum(r['eigennaam/afkorting'] == 'ja' for r in rijen)} eigennaam/afkorting)")
    print(f"-> {csv_pad}")
    if not args.niet_registreren:
        nieuw, bijgewerkt = register.opnemen(csv_pad, naam, bekende_varianten)
        register.log_meeting({
            "meeting": naam, "datum vergadering": args.datum, "verwerkt op": date.today().isoformat(),
            "lijstversie": register.huidige_versie(), "woorden HappyScribe": len(hs), "woorden Teams": len(teams),
            "overeenkomst": f"{overeenkomst:.0%}", "kandidaten": len(rijen),
            "eigennaam/afkorting": sum(r["eigennaam/afkorting"] == "ja" for r in rijen),
            "op lijst en toch fout": sum(r["al op lijst"] == "ja" for r in rijen),
            "variant al bekend en toch fout": sum(r["Teams-variant al in sounds like"] == "ja" for r in rijen),
            "nieuw in register": nieuw,
        })
        print(f"Register: {nieuw} nieuw, {bijgewerkt} bijgewerkt -> register.csv, meetings.csv")
    if overeenkomst < 0.6:
        print("Let op: lage overeenkomst. Gaat het om dezelfde opname en hetzelfde stuk? Check met --debug.")


if __name__ == "__main__":
    main()
