import csv
import os
import shutil
import subprocess
import sys

import register as r
from conftest import EXAMPLES, ROOT

KOPPEN = ["kandidaat (HappyScribe)", "Teams schreef", "aantal", "soort verschil", "gelijkenis",
          "eigennaam/afkorting", "al op lijst", "Teams-variant al in sounds like", "voorbeeld"]


def kandidaten(pad, *rijen):
    r.schrijf_csv(pad, [dict(zip(KOPPEN, rij)) for rij in rijen], KOPPEN, ";")
    return pad


def orbitly(teams="Orbit Lee (1x)", aantal="1"):
    return ("Orbitly", teams, aantal, "ander woord", "0.8", "ja", "", "", "uit [Orbitly] aan")


# ---------- varianten samenvoegen ----------

def test_splits_varianten():
    assert r.splits_varianten("Orbit Lee (3x) | Orbitlee (1x) | los") == {"Orbit Lee": 3, "Orbitlee": 1, "los": 1}


def test_voeg_varianten_telt_op():
    assert r.voeg_varianten("NWO (1x)", "NWO (2x) | N W L (1x)") == "NWO (3x) | N W L (1x)"


def test_voeg_sounds_like_zonder_dubbelen():
    assert r.voeg_sounds_like("data vlinder", "Data-Vlinder; data flinder") == "data vlinder; data flinder"


# ---------- register ----------

def test_opnemen_nieuw_en_samenvoegen(map_tmp):
    k1 = kandidaten(map_tmp / "m1.csv", orbitly())
    assert r.opnemen(k1, "meeting1", set()) == (1, 0)
    k2 = kandidaten(map_tmp / "m2.csv", orbitly("Orbit Lee (1x) | Orbit Leigh (1x)", "2"))
    assert r.opnemen(k2, "meeting2", set()) == (0, 1)

    rij = r.lees_register()["orbitly"]
    assert rij["status"] == "nieuw"
    assert rij["meetings"] == "meeting1, meeting2"
    assert (rij["aantal meetings"], rij["aantal keer"]) == ("2", "3")
    assert rij["Teams schreef"] == "Orbit Lee (2x) | Orbit Leigh (1x)"
    assert rij["sounds like voorstel"] == "Orbit Lee; Orbit Leigh"


def test_opnieuw_draaien_telt_niet_dubbel(map_tmp):
    k = kandidaten(map_tmp / "m1.csv", orbitly())
    r.opnemen(k, "meeting1", set())
    assert r.opnemen(k, "meeting1", set()) == (0, 0)
    assert r.lees_register()["orbitly"]["aantal keer"] == "1"


def test_bekende_variant_niet_opnieuw_voorstellen(map_tmp):
    k = kandidaten(map_tmp / "m1.csv", orbitly())
    r.opnemen(k, "meeting1", {"orbitlee"})
    assert r.lees_register()["orbitly"]["sounds like voorstel"] == ""


def test_fout_na_verzending_wordt_geteld(map_tmp):
    r.opnemen(kandidaten(map_tmp / "m1.csv", orbitly()), "meeting1", set())
    reg = r.lees_register()
    reg["orbitly"]["status"] = "verstuurd v2"
    r.schrijf_register(reg)
    r.opnemen(kandidaten(map_tmp / "m3.csv", orbitly("Orbit Leigh (1x)")), "meeting3", set())
    rij = r.lees_register()["orbitly"]
    assert rij["gezien na verzending"] == "1"
    assert rij["sounds like voorstel"] == "Orbit Lee"  # verstuurd: voorstel blijft staan


def test_log_meeting_vervangt_regel(map_tmp):
    basis = {veld: "" for veld in r.LOGVELDEN}
    r.log_meeting({**basis, "meeting": "meeting1", "datum vergadering": "2026-03-02", "kandidaten": 9})
    r.log_meeting({**basis, "meeting": "meeting1", "datum vergadering": "2026-03-02", "kandidaten": 7})
    log = r.lees_csv(map_tmp / "meetings.csv", ";")
    assert len(log) == 1 and log[0]["kandidaten"] == "7"


def test_batch_maakt_nieuwe_lijstversie(map_tmp):
    shutil.copy2(EXAMPLES / "woordenlijst.csv", map_tmp / "woordenlijst.csv")
    r.opnemen(kandidaten(map_tmp / "m1.csv", orbitly(),
                         ("Fluxgrid", "flax grid (1x)", "1", "ander woord", "0.9", "ja", "ja", "", "")),
              "meeting1", set())
    reg = r.lees_register()
    for rij in reg.values():
        rij["status"] = "goedgekeurd"
    r.schrijf_register(reg)

    r.batch("v2", proef=False)

    lijst = {rij["Term (required)"]: rij["Sounds like"] for rij in r.lees_csv(map_tmp / "woordenlijst.csv", ",")}
    assert lijst["Orbitly"] == "Orbit Lee"
    assert lijst["Fluxgrid"] == "flux grid; flux grit; flax grid"  # alleen achteraan aangevuld
    assert (map_tmp / "archief" / "woordenlijst_voor_v2.csv").exists()
    assert r.huidige_versie() == "v2"
    assert all(rij["status"] == "verstuurd v2" for rij in r.lees_register().values())


# ---------- van begin tot eind ----------

def test_vergelijk_van_begin_tot_eind(tmp_path):
    shutil.copy2(EXAMPLES / "woordenlijst.csv", tmp_path / "woordenlijst.csv")
    env = dict(os.environ, WOORDENBOEK_MAP=str(tmp_path))
    subprocess.run([sys.executable, "vergelijk.py", str(EXAMPLES / "meeting1.md"), str(EXAMPLES / "meeting1.docx"),
                    "--datum", "2026-03-02", "--uit", str(tmp_path), "--lijst", str(tmp_path / "woordenlijst.csv")],
                   cwd=ROOT, env=env, check=True, capture_output=True)
    with (tmp_path / "meeting1_kandidaten.csv").open(encoding="utf-8-sig") as f:
        termen = [rij["kandidaat (HappyScribe)"] for rij in csv.DictReader(f, delimiter=";")]
    assert {"Fluxgrid", "Orbitly", "SnelSync", "NWL", "DataVlinder"} <= set(termen)
    assert "kick-off" not in termen  # spatie/streepje bij een gewoon woord is ruis
    log = r.lees_csv(tmp_path / "meetings.csv", ";")
    assert log[0]["kandidaten"] == str(len(termen))
