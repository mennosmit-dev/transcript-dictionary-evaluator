"""Maakt de fictieve voorbeeldvergaderingen in deze map.

Per vergadering een referentie-transcript in HappyScribe-stijl (.md) en een
Teams-transcript (.docx) met typische fouten op jargon en namen.
Alles is verzonnen: Northwind Labs, Fluxgrid, Orbitly, SnelSync, DataVlinder en de sprekers.

Gebruik:
    python examples/make_examples.py
"""

from pathlib import Path

from docx import Document

HIER = Path(__file__).parent

# (spreker, seconden, referentietekst, wat Teams ervan maakte)
MEETINGS = {
    "meeting1": {
        "titel": "Northwind Labs - Fluxgrid kick-off",
        "datum": "March 2, 2026, 9:00AM",
        "beurten": [
            ("Jan de Vries", 3,
             "Goedemorgen allemaal, welkom bij de kick-off van het Fluxgrid dashboard voor Northwind Labs.",
             "Goedemorgen allemaal, welkom bij de kick off van het flux grid dashboard voor Northwind Lapse."),
            ("Sofie Bakker", 11,
             "Dank je Jan. We koppelen eerst de data uit Orbitly aan het churnmodel, dan kijken we naar de KPI's.",
             "Dank je Jan. We koppelen eerst de data uit Orbit Lee aan het turn model, dan kijken we eh naar de KPI's."),
            ("Ravi Kapoor", 24,
             "Sounds good. The NWL pipeline runs every night, so the refresh should be fine. I'll check SnelSync tomorrow.",
             "Sounds good. The NWO pipeline runs every night, so the refresh should be fine. I'll check snel sink tomorrow."),
            ("Jan de Vries", 38,
             "Top. En DataVlinder, hebben we daar al toegang toe?",
             "Top. En data vlinder, hebben we daar al toegang toe?"),
            ("Sofie Bakker", 45,
             "Nog niet, ik vraag het aan Ravi. Het Fluxgrid team wil eerst een demo.",
             "Nog niet, ik vraag het aan Robbie. Het flux grid team wil eerst een demo."),
            ("Ravi Kapoor", 52,
             "Okay, then let's plan the demo next week.",
             "Okay, so let's plan the demo next week."),
        ],
    },
    "meeting2": {
        "titel": "Northwind Labs - churnmodel review",
        "datum": "March 9, 2026, 9:00AM",
        "beurten": [
            ("Sofie Bakker", 2,
             "Vandaag bespreken we de eerste resultaten van het churnmodel in Fluxgrid.",
             "Vandaag bespreken we de eerste resultaten van het churn model in Flux Grid."),
            ("Ravi Kapoor", 15,
             "The precision is 0.82 on the Orbitly data, but recall drops for the NWL enterprise segment.",
             "The precision is 0.82 on the Orbit Lee data, but recall drops for the N W L enterprise segment."),
            ("Jan de Vries", 31,
             "Kunnen we SnelSync gebruiken om de features dagelijks te verversen?",
             "Kunnen we snel sink gebruiken om de features dagelijks te verversen?"),
            ("Ravi Kapoor", 40,
             "Yes, SnelSync supports that. The DataVlinder connector is already live.",
             "Yes, snelsync supports that. The data flinder connector is already live."),
            ("Sofie Bakker", 52,
             "Mooi. Dan zet ik de KPI-radar op de agenda voor volgende week, samen met Ravi.",
             "Mooi. Dan zet ik de KPI radar op de agenda voor volgende week, samen met Robbie."),
        ],
    },
    "meeting3": {
        "titel": "Northwind Labs - Fluxgrid demo",
        "datum": "March 16, 2026, 9:00AM",
        "beurten": [
            ("Jan de Vries", 4,
             "Welkom bij de demo van Fluxgrid. Ravi, wil jij beginnen?",
             "Welkom bij de demo van Fluxgrid. Robbie, wil jij beginnen?"),
            ("Ravi Kapoor", 10,
             "Sure. This is the Orbitly feed, it lands in the NWL lakehouse every hour.",
             "Sure. This is the Orbitly feed, it lands in the NWO lake house every hour."),
            ("Sofie Bakker", 22,
             "En de SnelSync job draait daarna, toch?",
             "En de snel sink job draait daarna, toch?"),
            ("Ravi Kapoor", 30,
             "Correct. The KPI-radar shows churn risk per segment from the churnmodel.",
             "Correct. The KPI radar shows churn risk per segment from the turn model."),
            ("Jan de Vries", 41,
             "Super, dan sturen we dit naar DataVlinder voor feedback.",
             "Super, dan sturen we dit naar data vlinder voor feedback."),
        ],
    },
}


def schrijf_md(pad: Path, m: dict):
    """HappyScribe-export: '[00:00:03.00] **Speaker 1:** tekst'."""
    nummers = {}
    regels = [f"# {m['titel']}", ""]
    for spreker, sec, ref, _ in m["beurten"]:
        nr = nummers.setdefault(spreker, len(nummers) + 1)
        regels += [f"[00:00:{sec:02d}.00] **Speaker {nr}:** {ref}", ""]
    pad.write_text("\n".join(regels), encoding="utf-8")


def schrijf_docx(pad: Path, m: dict):
    """Teams-export: per beurt één alinea 'Naam   0:03', regelafbreking, tekst."""
    doc = Document()
    doc.add_paragraph(m["titel"])
    doc.add_paragraph(m["datum"])
    for spreker, sec, _, teams in m["beurten"]:
        p = doc.add_paragraph()
        kop = p.add_run(f"{spreker}   0:{sec:02d}")
        kop.add_break()
        p.add_run(teams)
    doc.save(pad)


if __name__ == "__main__":
    for naam, m in MEETINGS.items():
        schrijf_md(HIER / f"{naam}.md", m)
        schrijf_docx(HIER / f"{naam}.docx", m)
        print(f"{naam}.md + {naam}.docx")
