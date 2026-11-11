import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import register  # noqa: E402

EXAMPLES = ROOT / "examples"


@pytest.fixture
def map_tmp(tmp_path, monkeypatch):
    """Laat register.py in een lege tijdelijke map werken in plaats van naast de code."""
    monkeypatch.setattr(register, "MAP", tmp_path)
    monkeypatch.setattr(register, "REGISTER", tmp_path / "register.csv")
    monkeypatch.setattr(register, "MEETINGLOG", tmp_path / "meetings.csv")
    monkeypatch.setattr(register, "WOORDENLIJST", tmp_path / "woordenlijst.csv")
    monkeypatch.setattr(register, "VERSIE", tmp_path / "versie.txt")
    monkeypatch.setattr(register, "NOTITIE", tmp_path / "stand.md")
    return tmp_path
