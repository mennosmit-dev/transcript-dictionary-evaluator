import pytest

import vergelijk as v
from conftest import EXAMPLES


def teksten(meeting):
    hs = v.schoon(v.lees_md(EXAMPLES / f"{meeting}.md"))
    teams = v.schoon(v.lees_docx(EXAMPLES / f"{meeting}.docx"))
    return hs, teams


# ---------- inlezen en opschonen ----------

def test_md_zonder_tijden_en_sprekers():
    hs, _ = teksten("meeting1")
    assert "Speaker" not in hs
    assert "00:00" not in hs
    assert "**" not in hs
    assert hs.splitlines()[1].startswith("Goedemorgen allemaal")


def test_docx_zonder_sprekerregels():
    _, teams = teksten("meeting1")
    assert "Jan de Vries" not in teams
    assert "0:03" not in teams
    assert "Orbit Lee" in teams


def test_tokens_houden_streepjes_en_apostrof():
    assert v.tokens("de KPI-radar en de KPI's, I'll check") == ["de", "KPI-radar", "en", "de", "KPI's", "I'll", "check"]


def test_plat_negeert_spatie_en_streepje():
    assert v.plat(["KPI-radar"]) == v.plat(["KPI", "radar"]) == "kpiradar"


# ---------- vergelijken ----------

def paren(hs, teams, max_len=5):
    return {(a, b, soort) for a, b, _, soort in v.vergelijk(hs.split(), teams.split(), max_len)[0]}


def test_ander_woord():
    assert paren("data uit Orbitly aan", "data uit Orbit Lee aan") == {("Orbitly", "Orbit Lee", "ander woord")}


def test_spatie_of_streepje():
    assert paren("het Fluxgrid dashboard", "het flux grid dashboard") == {("Fluxgrid", "flux grid", "spatie/streepje")}


def test_ontbreekt_in_teams():
    assert paren("check SnelSync tomorrow", "check tomorrow") == {("SnelSync", "", "ontbreekt in Teams")}


def test_alleen_stopwoorden_is_ruis():
    # 'dus' -> 'dan' en een losse 'eh' extra in Teams: geen kandidaten
    assert paren("en dus kijken we naar", "en dan kijken we eh naar") == set()


def test_alleen_getallen_is_ruis():
    assert paren("precision is 82 here", "precision is 28 here") == set()


def test_hoofdletters_alleen_bij_eigennamen():
    gevonden = paren("Yes SnelSync supports that Yes", "yes snelsync supports that Yes")
    assert ("SnelSync", "snelsync", "hoofdletters") in gevonden
    assert not any(a == "Yes" for a, _, _ in gevonden)


def test_te_lange_verschillen_overslaan():
    hs = "begin een twee drie vier vijf zes eind"
    teams = "begin aap noot mies wim zus jet eind"
    assert paren(hs, teams, max_len=5) == set()
    assert len(paren(hs, teams, max_len=6)) == 1


def test_eigennaam():
    klein = {"dashboard"}
    assert v.is_eigennaam(["NWL"], klein)
    assert v.is_eigennaam(["DataVlinder"], klein)
    assert v.is_eigennaam(["&Co"], klein)
    assert v.is_eigennaam(["M365"], klein)
    assert not v.is_eigennaam(["dashboard"], klein)
    assert not v.is_eigennaam(["De"], {"de"})  # stopwoord aan het begin van een zin


def test_meeting1_vindt_het_jargon():
    hs, teams = teksten("meeting1")
    gevonden = {a: b for a, b, _, _ in v.vergelijk(v.tokens(hs), v.tokens(teams), 5)[0]}
    assert gevonden["Orbitly"] == "Orbit Lee"
    assert gevonden["SnelSync"] == "snel sink"
    assert gevonden["NWL"] == "NWO"
    assert gevonden["churnmodel"] == "turn model"


# ---------- woordenlijst ----------

def test_lees_lijst():
    termen, varianten = v.lees_lijst(EXAMPLES / "woordenlijst.csv")
    assert termen == ["northwindlabs", "fluxgrid", "kpiradar"]
    assert "fluxgrid" in varianten and "fluxgrit" in varianten


def test_kapotte_csv_stopt(tmp_path):
    pad = tmp_path / "lijst.csv"
    pad.write_text("Term,Sounds like,Long,Def\nA,b,c,d,e\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        v.lees_lijst(pad)
