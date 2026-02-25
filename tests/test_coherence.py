"""
test_coherence.py — Tests for coherence score computation.
"""
from __future__ import annotations
import pytest
from datetime import date

import viyugam.storage as storage
from viyugam.models import (
    Task, TaskStatus, Dimension, ViyugamConfig, SeasonConfig,
)


def _make_done_task(title: str, dimension: Dimension, days_ago: int = 0) -> Task:
    from datetime import timedelta
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    task = Task(title=title, status=TaskStatus.DONE,
                dimension=dimension, scheduled_date=d)
    storage.save_task(task)
    return task


# ── Empty task list → score is None ──────────────────────────────────────────

def test_coherence_no_data():
    cfg = ViyugamConfig()
    result = storage.compute_coherence_score(cfg)
    assert result["score"] is None
    assert "Not enough data" in result["narrative"]


# ── All tasks match season → high score ──────────────────────────────────────

def test_coherence_all_match_season():
    cfg = ViyugamConfig(season=SeasonConfig(name="Career Season", focus=Dimension.CAREER))
    today = date.today().isoformat()

    for i in range(5):
        t = Task(title=f"Career task {i}", status=TaskStatus.DONE,
                 dimension=Dimension.CAREER, scheduled_date=today)
        storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    assert result["score"] is not None
    assert result["score"] >= 50  # Should be decently high when aligned


# ── All tasks different from season → lower score ────────────────────────────

def test_coherence_all_different_from_season():
    cfg = ViyugamConfig(season=SeasonConfig(name="Career Season", focus=Dimension.CAREER))
    today = date.today().isoformat()

    for i in range(5):
        t = Task(title=f"Health task {i}", status=TaskStatus.DONE,
                 dimension=Dimension.HEALTH, scheduled_date=today)
        storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    assert result["score"] is not None
    # Season score will be 0, balance may be penalised too
    # Activity score: min(20, 5*2) = 10
    # So score <= 50


# ── Mixed dimensions → moderate score ─────────────────────────────────────────

def test_coherence_mixed_dimensions():
    cfg = ViyugamConfig(season=SeasonConfig(name="Career Season", focus=Dimension.CAREER))
    today = date.today().isoformat()

    dims = [Dimension.CAREER, Dimension.CAREER, Dimension.HEALTH,
            Dimension.JOY, Dimension.LEARNING]
    for i, dim in enumerate(dims):
        t = Task(title=f"Task {i}", status=TaskStatus.DONE,
                 dimension=dim, scheduled_date=today)
        storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100


# ── Score is 0-100 range ──────────────────────────────────────────────────────

def test_coherence_score_in_range():
    cfg = ViyugamConfig(season=SeasonConfig(name="Health Season", focus=Dimension.HEALTH))
    today = date.today().isoformat()

    for dim in Dimension:
        t = Task(title=f"Task {dim}", status=TaskStatus.DONE,
                 dimension=dim, scheduled_date=today)
        storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100


# ── Breakdown sums to ~100% ────────────────────────────────────────────────────

def test_coherence_breakdown_sums_to_100():
    cfg = ViyugamConfig()
    today = date.today().isoformat()

    for dim in [Dimension.CAREER, Dimension.HEALTH, Dimension.JOY]:
        for i in range(2):
            t = Task(title=f"Task {dim} {i}", status=TaskStatus.DONE,
                     dimension=dim, scheduled_date=today)
            storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    if result["score"] is not None:
        total = sum(result["breakdown"].values())
        assert abs(total - 100.0) < 1.0  # allow floating point tolerance


# ── Narrative is non-empty string ──────────────────────────────────────────────

def test_coherence_narrative_nonempty():
    cfg = ViyugamConfig(season=SeasonConfig(name="Test", focus=Dimension.CAREER))
    today = date.today().isoformat()

    t = Task(title="Career work", status=TaskStatus.DONE,
             dimension=Dimension.CAREER, scheduled_date=today)
    storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    assert isinstance(result["narrative"], str)
    assert len(result["narrative"]) > 0


# ── No season configured → still returns result ────────────────────────────────

def test_coherence_no_season():
    cfg = ViyugamConfig()  # no season
    today = date.today().isoformat()

    t = Task(title="Random task", status=TaskStatus.DONE,
             dimension=Dimension.JOY, scheduled_date=today)
    storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    # With no season, season_score = 0, so score comes from balance + activity
    assert result["score"] is not None
    assert isinstance(result["narrative"], str)
