"""Register van kandidaat-woorden over alle vergaderingen heen, en het maken van een nieuwe lijstversie.

Stroom:
  1. vergelijk.py  -> zet de kandidaten van een vergadering automatisch in register.csv
  2. Jij beoordeelt in register.csv (Excel): kolom 'status' op goedgekeurd / afgewezen / twijfel,
     'lijstterm' en 'sounds like voorstel' zo nodig corrigeren, 'vertrouwelijk' op ja bij klant- of persoonsnamen.
  3. python register.py batch v5 --proef   -> laat zien wat er zou gebeuren
     python register.py batch v5           -> woordenlijst_v5.csv (voor de beheerder) + wijzigingen_v5.csv
                                              + changelog in de statusnotitie; status wordt 'verstuurd v5'
  4. python register.py stand              -> aantallen per status (geen inhoud)

register.csv blijft lokaal: er staan stukjes gesprek in. Naar de statusnotitie (stand.md) gaan alleen aantallen
en goedgekeurde termen (vertrouwelijke als [vertrouwelijk]).
"""

import argparse
import csv
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

MAP = Path(os.environ.get("WOORDENBOEK_MAP", Path(__file__).parent))
REGISTER = MAP / "register.csv"
MEETINGLOG = MAP / "meetings.csv"
WOORDENLIJST = MAP / "woordenlijst.csv"
VERSIE = MAP / "versie.txt"
# Optionele Markdown-notitie (bijv. in een kennisbank) met blokken <!-- stand:start/end --> en <!-- changelog -->.
NOTITIE = Path(os.environ.get("WOORDENBOEK_NOTITIE", MAP / "stand.md"))

LOGVELDEN = ["meeting", "datum vergadering", "verwerkt op", "lijstversie", "woorden HappyScribe", "woorden Teams",
             "overeenkomst", "kandidaten", "eigennaam/afkorting", "op lijst en toch fout",
             "variant al bekend en toch fout", "nieuw in register"]

VELDEN = ["term", "status", "lijstterm", "sounds like voorstel", "vertrouwelijk", "Teams schreef",
          "aantal meetings", "aantal keer", "gezien na verzending", "soort verschil", "eigennaam/afkorting",
          "al op lijst", "variant al bekend", "meetings", "eerst gezien", "verstuurd op", "voorbeeld", "notitie"]
STATUSSEN = ("nieuw", "twijfel", "goedgekeurd", "afgewezen")  # plus 'verstuurd vN'


def plat(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def lees_csv(pad: Path, scheiding: str) -> list[dict]:
    """Excel slaat soms op als ANSI in plaats van UTF-8; beide lezen."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with pad.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f, delimiter=scheiding))
        except UnicodeDecodeError:
            continue
    sys.exit(f"Kan {pad} niet lezen.")


def schrijf_csv(pad: Path, rijen: list[dict], velden: list[str], scheiding: str):
    try:
        with pad.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=velden, delimiter=scheiding, extrasaction="ignore")
            w.writeheader()
            w.writerows(rijen)
    except PermissionError:
        sys.exit(f"{pad.name} is open in Excel. Sluit het bestand en draai opnieuw.")


def lees_register() -> dict[str, dict]:
    if not REGISTER.exists():
        return {}
    return {r["term"].lower(): r for r in lees_csv(REGISTER, ";") if r.get("term")}


def schrijf_register(reg: dict[str, dict]):
    volgorde = {"nieuw": 0, "twijfel": 1, "goedgekeurd": 2, "afgewezen": 4}
    rijen = sorted(reg.values(), key=lambda r: (
        volgorde.get(r["status"], 3), -int(r["aantal meetings"] or 0),
        r["eigennaam/afkorting"] != "ja", -int(r["aantal keer"] or 0)))
    schrijf_csv(REGISTER, rijen, VELDEN, ";")


def splits_varianten(tekst: str) -> dict[str, int]:
    """'Data Vlinder (3x) | Datavlinder (1x)' -> {'Data Vlinder': 3, 'Datavlinder': 1}"""
    uit = {}
    for deel in filter(None, (d.strip() for d in tekst.split("|"))):
        m = re.match(r"^(.*) \((\d+)x\)$", deel)
        naam, n = (m.group(1), int(m.group(2))) if m else (deel, 1)
        uit[naam] = uit.get(naam, 0) + n
    return uit


def voeg_varianten(*teksten: str) -> str:
    totaal = {}
    for t in teksten:
        for naam, n in splits_varianten(t).items():
            totaal[naam] = totaal.get(naam, 0) + n
    return " | ".join(f"{k} ({v}x)" for k, v in sorted(totaal.items(), key=lambda x: -x[1]))


def voeg_sounds_like(*teksten: str) -> str:
    gezien, uit = set(), []
    for t in teksten:
        for v in (x.strip() for x in t.split(";")):
            if v and plat(v) not in gezien:
                gezien.add(plat(v))
                uit.append(v)
    return "; ".join(uit)


def opnemen(kandidaten_csv: Path, meeting: str, bekende_varianten: set[str]) -> tuple[int, int]:
    """Kandidaten van één vergadering in het register zetten. Opnieuw draaien telt niet dubbel."""
    reg = lees_register()
    nieuw = bijgewerkt = 0
    vandaag = date.today().isoformat()
    for k in lees_csv(kandidaten_csv, ";"):
        term = k["kandidaat (HappyScribe)"]
        varianten = splits_varianten(k["Teams schreef"])
        voorstel = "; ".join(v for v in varianten
                             if v != "(niets)" and v.lower() != term.lower() and plat(v) not in bekende_varianten)
        r = reg.get(term.lower())
        if r is None:
            reg[term.lower()] = {
                "term": term, "status": "nieuw", "lijstterm": term, "sounds like voorstel": voorstel,
                "vertrouwelijk": "", "Teams schreef": k["Teams schreef"], "aantal meetings": "1",
                "aantal keer": k["aantal"], "gezien na verzending": "0", "soort verschil": k["soort verschil"],
                "eigennaam/afkorting": k["eigennaam/afkorting"], "al op lijst": k["al op lijst"],
                "variant al bekend": k["Teams-variant al in sounds like"], "meetings": meeting,
                "eerst gezien": vandaag, "verstuurd op": "", "voorbeeld": k["voorbeeld"], "notitie": "",
            }
            nieuw += 1
            continue
        if meeting in [m.strip() for m in r["meetings"].split(",")]:
            continue
        r["meetings"] = f'{r["meetings"]}, {meeting}'
        r["aantal meetings"] = str(int(r["aantal meetings"] or 0) + 1)
        r["aantal keer"] = str(int(r["aantal keer"] or 0) + int(k["aantal"]))
        r["Teams schreef"] = voeg_varianten(r["Teams schreef"], k["Teams schreef"])
        if r["status"].startswith("verstuurd"):
            # Staat al op de lijst en gaat nog steeds fout: belangrijk signaal voor de meting.
            r["gezien na verzending"] = str(int(r["gezien na verzending"] or 0) + 1)
        else:
            r["sounds like voorstel"] = voeg_sounds_like(r["sounds like voorstel"], voorstel)
        bijgewerkt += 1
    schrijf_register(reg)
    werk_stand_bij(reg)
    return nieuw, bijgewerkt


def huidige_versie() -> str:
    return VERSIE.read_text(encoding="utf-8").strip() if VERSIE.exists() else "v1"


def log_meeting(stats: dict):
    """Eén regel per vergadering; opnieuw draaien vervangt de regel."""
    log = lees_csv(MEETINGLOG, ";") if MEETINGLOG.exists() else []
    log = [r for r in log if r["meeting"] != stats["meeting"]] + [stats]
    log.sort(key=lambda r: (r["datum vergadering"], r["meeting"]))
    schrijf_csv(MEETINGLOG, log, LOGVELDEN, ";")
    werk_stand_bij(lees_register())


# ---------- statusnotitie ----------

def werk_stand_bij(reg: dict[str, dict]):
    """Alleen aantallen naar de notitie, geen termen of context."""
    if not NOTITIE.exists():
        return
    meetings = {m.strip() for r in reg.values() for m in r["meetings"].split(",") if m.strip()}
    tel = {}
    for r in reg.values():
        s = "verstuurd" if r["status"].startswith("verstuurd") else r["status"]
        tel[s] = tel.get(s, 0) + 1
    log = lees_csv(MEETINGLOG, ";") if MEETINGLOG.exists() else []
    nog_fout = sum(1 for r in reg.values() if r["status"].startswith("verstuurd") and int(r["gezien na verzending"] or 0) > 0)
    blok = "\n".join([
        "<!-- stand:start -->",
        f"*Bijgewerkt {date.today().isoformat()} door register.py.*",
        "",
        "| | Aantal |",
        "| --- | --- |",
        f"| Vergaderingen vergeleken | {len(meetings)} |",
        *[f"| Kandidaten {s} | {tel.get(s, 0)} |" for s in (*STATUSSEN, "verstuurd")],
        f"| Verstuurd en daarna nog fout gezien | {nog_fout} |",
        "",
        "Per vergadering (namen staan alleen lokaal in meetings.csv):",
        "",
        "| # | Datum | Lijst | Woorden (HS) | Overeenkomst | Kandidaten | Eigennaam/afk. | Op lijst en toch fout | Variant bekend en toch fout | Nieuw in register |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[f'| {i} | {r["datum vergadering"]} | {r["lijstversie"]} | {r["woorden HappyScribe"]} | {r["overeenkomst"]} '
          f'| {r["kandidaten"]} | {r["eigennaam/afkorting"]} | {r["op lijst en toch fout"]} '
          f'| {r["variant al bekend en toch fout"]} | {r["nieuw in register"]} |'
          for i, r in enumerate(log, 1)],
        "<!-- stand:end -->",
    ])
    tekst = NOTITIE.read_text(encoding="utf-8")
    tekst = re.sub(r"<!-- stand:start -->.*?<!-- stand:end -->", lambda _: blok, tekst, flags=re.S)
    NOTITIE.write_text(tekst, encoding="utf-8")


def schrijf_changelog(versie: str, wijzigingen: list[dict]):
    if not NOTITIE.exists():
        print(f"Let op: {NOTITIE} niet gevonden, changelog niet geschreven.")
        return
    regels = [f"### {versie} ({date.today().isoformat()})", "",
              "| Term | Actie | Sounds like erbij | Gezien in vergaderingen |", "| --- | --- | --- | --- |"]
    for w in wijzigingen:
        geheim = w["vertrouwelijk"] == "ja"
        term = "[vertrouwelijk]" if geheim else w["term"]
        sl = "[vertrouwelijk]" if geheim and w["sounds like erbij"] else w["sounds like erbij"]
        regels.append(f'| {term} | {w["actie"]} | {sl} | {w["aantal meetings"]} |')
    regels.append("")
    tekst = NOTITIE.read_text(encoding="utf-8")
    tekst = tekst.replace("<!-- changelog -->", "<!-- changelog -->\n\n" + "\n".join(regels), 1)
    NOTITIE.write_text(tekst, encoding="utf-8")


# ---------- commando's ----------

def batch(versie: str, proef: bool):
    reg = lees_register()
    if any(r["status"] == f"verstuurd {versie}" for r in reg.values()):
        sys.exit(f"Versie {versie} is al verstuurd. Kies een nieuw versienummer.")
    goed = [r for r in reg.values() if r["status"] == "goedgekeurd"]
    if not goed:
        sys.exit("Geen kandidaten met status 'goedgekeurd'.")

    lijst = lees_csv(WOORDENLIJST, ",")
    velden = list(lijst[0].keys())
    k_term, k_sl = velden[0], velden[1]
    index = {plat(r[k_term]): r for r in lijst}

    wijzigingen = []
    for r in goed:
        lijstterm = (r["lijstterm"] or r["term"]).strip()
        voorstel = r["sounds like voorstel"].strip()
        bestaand = index.get(plat(lijstterm))
        if bestaand:
            oud = {plat(v) for v in bestaand[k_sl].split(";") if v.strip()}
            erbij = "; ".join(v.strip() for v in voorstel.split(";") if v.strip() and plat(v) not in oud)
            if not erbij:
                print(f"- {lijstterm}: staat al op de lijst, geen nieuwe sounds like. Overgeslagen.")
                continue
            # Bestaande varianten letterlijk laten staan, alleen achteraan aanvullen.
            bestaand[k_sl] = "; ".join(x for x in (bestaand[k_sl].strip().rstrip(";"), erbij) if x)
            actie = "sounds like toegevoegd"
        else:
            nieuw = {v: "" for v in velden}
            nieuw[k_term], nieuw[k_sl] = lijstterm, voorstel
            lijst.append(nieuw)
            index[plat(lijstterm)] = nieuw
            erbij, actie = voorstel, "nieuwe term"
        wijzigingen.append({"term": lijstterm, "actie": actie, "sounds like erbij": erbij,
                            "aantal meetings": r["aantal meetings"], "vertrouwelijk": r["vertrouwelijk"],
                            "_reg": r})

    print(f"{versie}: {sum(w['actie'] == 'nieuwe term' for w in wijzigingen)} nieuwe termen, "
          f"{sum(w['actie'] != 'nieuwe term' for w in wijzigingen)} termen met extra sounds like, "
          f"lijst wordt {len(lijst)} termen.")
    for w in wijzigingen:
        print(f"  {w['actie']:<24} {w['term']}  +[{w['sounds like erbij']}]")
    if proef:
        print("Proef: niets weggeschreven.")
        return
    if not wijzigingen:
        return

    archief = MAP / "archief"
    archief.mkdir(exist_ok=True)
    shutil.copy2(WOORDENLIJST, archief / f"woordenlijst_voor_{versie}.csv")
    schrijf_csv(MAP / f"woordenlijst_{versie}.csv", lijst, velden, ",")
    schrijf_csv(MAP / f"wijzigingen_{versie}.csv", wijzigingen,
                ["term", "actie", "sounds like erbij", "aantal meetings", "vertrouwelijk"], ";")
    shutil.copy2(MAP / f"woordenlijst_{versie}.csv", WOORDENLIJST)
    VERSIE.write_text(versie, encoding="utf-8")

    vandaag = date.today().isoformat()
    for w in wijzigingen:
        w["_reg"]["status"] = f"verstuurd {versie}"
        w["_reg"]["verstuurd op"] = vandaag
    schrijf_register(reg)
    schrijf_changelog(versie, wijzigingen)
    werk_stand_bij(reg)
    print(f"-> woordenlijst_{versie}.csv (volledige lijst voor de beheerder) en wijzigingen_{versie}.csv")


def stand():
    reg = lees_register()
    tel = {}
    for r in reg.values():
        tel[r["status"]] = tel.get(r["status"], 0) + 1
    for s, n in sorted(tel.items()):
        print(f"{s:<16} {n}")
    werk_stand_bij(reg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("batch", help="goedgekeurde kandidaten in een nieuwe lijstversie zetten")
    b.add_argument("versie", help="bijvoorbeeld v5")
    b.add_argument("--proef", action="store_true", help="alleen laten zien, niets wegschrijven")
    sub.add_parser("stand", help="aantallen per status")
    args = ap.parse_args()
    if args.cmd == "batch":
        batch(args.versie, args.proef)
    else:
        stand()


if __name__ == "__main__":
    main()
