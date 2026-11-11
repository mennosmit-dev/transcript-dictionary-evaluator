"""Draait de hele stroom op de fictieve voorbeelden en zet het resultaat in examples/output/.

1. meeting1 en meeting2 vergelijken (lijst v1)
2. beoordeling in het register invullen, zoals een mens dat in Excel zou doen
3. register.py batch v2: goedgekeurde termen naar een nieuwe lijstversie
4. meeting3 vergelijken met lijst v2: wat gaat er nog steeds fout?

Gebruik:
    python examples/run_demo.py
"""

import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).parent
ROOT = HIER.parent
UIT = HIER / "output"

MEETINGS = [("meeting1", "2026-03-02"), ("meeting2", "2026-03-09"), ("meeting3", "2026-03-16")]

# Beoordeling na meeting2: (status, vertrouwelijk). Niet genoemd = blijft 'nieuw'.
OORDEEL = {
    "orbitly": ("goedgekeurd", ""),
    "snelsync": ("goedgekeurd", ""),
    "nwl": ("goedgekeurd", ""),
    "datavlinder": ("goedgekeurd", ""),
    "ravi": ("goedgekeurd", "ja"),       # persoonsnaam: in de changelog als [vertrouwelijk]
    "labs": ("afgewezen", ""),           # 'Northwind Labs' staat al op de lijst
    "then": ("afgewezen", ""),           # ruis die door het stopwoordfilter glipte
    "fluxgrid": ("twijfel", ""),         # al op de lijst, variant al bekend
    "churnmodel": ("twijfel", ""),
}

STAND = """# Woordenlijst: stand

<!-- stand:start -->
<!-- stand:end -->

## Changelog

<!-- changelog -->
"""


def draai(*args):
    env = dict(os.environ, WOORDENBOEK_MAP=str(UIT))
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, env=env, check=True)


def vergelijk(meeting, datum):
    draai("vergelijk.py", HIER / f"{meeting}.md", HIER / f"{meeting}.docx",
          "--datum", datum, "--uit", UIT, "--lijst", UIT / "woordenlijst.csv")


def beoordeel():
    pad = UIT / "register.csv"
    with pad.open(encoding="utf-8-sig", newline="") as f:
        rijen = list(csv.DictReader(f, delimiter=";"))
        velden = list(rijen[0].keys())
    for r in rijen:
        status, geheim = OORDEEL.get(r["term"].lower(), (r["status"], r["vertrouwelijk"]))
        r["status"], r["vertrouwelijk"] = status, geheim
    with pad.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=velden, delimiter=";")
        w.writeheader()
        w.writerows(rijen)


if __name__ == "__main__":
    shutil.rmtree(UIT, ignore_errors=True)
    UIT.mkdir()
    shutil.copy2(HIER / "woordenlijst.csv", UIT / "woordenlijst.csv")
    (UIT / "versie.txt").write_text("v1", encoding="utf-8")
    (UIT / "stand.md").write_text(STAND, encoding="utf-8")

    for meeting, datum in MEETINGS[:2]:
        vergelijk(meeting, datum)
    beoordeel()
    draai("register.py", "batch", "v2")
    vergelijk(*MEETINGS[2])
    draai("register.py", "stand")
