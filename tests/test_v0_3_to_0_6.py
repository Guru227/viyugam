"""Tests for v0.3–v0.6 features."""
from datetime import date, timedelta
import pytest

# ── v0.4: Energy pattern ─────────────────────────────────────────────────────

def test_energy_cache_miss_returns_empty_without_journals(tmp_path):
    from viyugam.agents.energy import get_energy_pattern
    journal_dir = tmp_path / "journals"
    journal_dir.mkdir()
    cache = tmp_path / "energy.json"
    result = get_energy_pattern(journal_dir, cache)
    assert result == {}

def test_energy_cache_hit_returns_cached(tmp_path):
    import json
    from viyugam.agents.energy import get_energy_pattern
    journal_dir = tmp_path / "journals"
    journal_dir.mkdir()
    cache = tmp_path / "energy.json"
    today = date.today().isoformat()
    cached = {
        "peak_hours": "9-11am",
        "low_energy": "2-3pm",
        "pattern_summary": "Morning person",
        "_analyzed_on": today,
    }
    cache.write_text(json.dumps(cached))
    result = get_energy_pattern(journal_dir, cache)
    assert result["peak_hours"] == "9-11am"
    assert "_analyzed_on" not in result  # private keys stripped

def test_energy_cache_stale_if_old(tmp_path):
    import json
    from viyugam.agents.energy import get_energy_pattern
    journal_dir = tmp_path / "journals"
    journal_dir.mkdir()
    cache = tmp_path / "energy.json"
    old_date = (date.today() - timedelta(days=5)).isoformat()
    cached = {"peak_hours": "old", "_analyzed_on": old_date}
    cache.write_text(json.dumps(cached))
    # No journal files → returns empty even though cache stale
    result = get_energy_pattern(journal_dir, cache)
    assert result == {}

# ── v0.5: OKR model ──────────────────────────────────────────────────────────

def test_okr_model_created():
    from viyugam.models import OKR, KeyResult, Dimension
    kr = KeyResult(text="Ship 3 features", target="3 shipped")
    okr = OKR(
        quarter="2026-Q1",
        objective="Deliver the product",
        dimension=Dimension.CAREER,
        key_results=[kr],
    )
    assert okr.quarter == "2026-Q1"
    assert len(okr.key_results) == 1
    assert okr.key_results[0].text == "Ship 3 features"

def test_okr_storage_roundtrip(tmp_path, monkeypatch):
    import viyugam.storage as storage
    monkeypatch.setattr(storage, "OKRS_FILE", tmp_path / "okrs.json")
    (tmp_path / "okrs.json").write_text("[]")
    from viyugam.models import OKR, KeyResult
    kr = KeyResult(text="Run 50km total", target="50km")
    okr = OKR(quarter="2026-Q2", objective="Get fit", key_results=[kr])
    storage.save_okr(okr)
    loaded = storage.get_okrs(active_only=False)
    assert len(loaded) == 1
    assert loaded[0].objective == "Get fit"
    assert loaded[0].key_results[0].target == "50km"

def test_get_current_quarter():
    from viyugam.storage import get_current_quarter
    q = get_current_quarter()
    assert "-Q" in q
    year, quarter = q.split("-Q")
    assert 2024 <= int(year) <= 2030
    assert int(quarter) in (1, 2, 3, 4)

def test_get_next_quarter_wraps():
    from viyugam.storage import get_next_quarter, get_current_quarter
    nq = get_next_quarter()
    assert "-Q" in nq

def test_okr_active_filter(tmp_path, monkeypatch):
    import viyugam.storage as storage
    monkeypatch.setattr(storage, "OKRS_FILE", tmp_path / "okrs.json")
    (tmp_path / "okrs.json").write_text("[]")
    from viyugam.models import OKR
    active = OKR(quarter="2026-Q1", objective="Active one", is_active=True)
    inactive = OKR(quarter="2025-Q4", objective="Old one", is_active=False)
    storage.save_okr(active)
    storage.save_okr(inactive)
    assert len(storage.get_okrs(active_only=True)) == 1
    assert len(storage.get_okrs(active_only=False)) == 2

# ── v0.6: Semantic find corpus building ──────────────────────────────────────

def test_get_recent_journals_empty(tmp_path, monkeypatch):
    import viyugam.storage as storage
    monkeypatch.setattr(storage, "JOURNALS_DIR", tmp_path / "journals")
    (tmp_path / "journals").mkdir()
    result = storage.get_recent_journals(days=7)
    assert result == []

def test_get_recent_journals_finds_files(tmp_path, monkeypatch):
    import viyugam.storage as storage
    jdir = tmp_path / "journals"
    jdir.mkdir()
    monkeypatch.setattr(storage, "JOURNALS_DIR", jdir)
    today = date.today().isoformat()
    (jdir / f"{today}.md").write_text("# Journal\n\nHad a great day.")
    result = storage.get_recent_journals(days=7)
    assert len(result) == 1
    assert result[0][0] == today
    assert "great day" in result[0][1]
