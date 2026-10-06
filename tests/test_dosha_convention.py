"""Contested doshas must report which convention they applied, and why.

Kaal Sarpa appears in no classical text and is defined differently by different
sources — a reference API we benchmark against reports it present on charts
whose planets are plainly split across both sides of the nodal axis. Rather than
matching that, the engine states its convention and shows its evidence so a
disagreement is diagnosable instead of mysterious.
"""

from __future__ import annotations

import pytest

from vedic_calc import calculate_chart, detect_doshas

CHARTS = {
    # Exactly as in benchmarks/accuracy.py, so the assertions below describe
    # the same charts the benchmark reports on.
    "Varanasi 1988": dict(
        year=1988, month=8, day=15, hour=5, minute=0,
        latitude=25.3176, longitude=83.0068, timezone_offset=5.5,
    ),
    "Jaipur 2005": dict(
        year=2005, month=4, day=10, hour=18, minute=30,
        latitude=26.9124, longitude=75.7873, timezone_offset=5.5,
    ),
}


def _dosha(chart, needle: str):
    """Find a dosha by a substring of its name."""
    return next(d for d in detect_doshas(chart) if needle in d.name.lower())


@pytest.mark.parametrize("label", list(CHARTS))
def test_kalsarpa_reports_convention_and_basis(label: str):
    chart = calculate_chart(**CHARTS[label])
    kalsarpa = _dosha(chart, "kaal")

    assert kalsarpa.convention == "hemmed_strict_or_partial"
    # The basis must state the split, which is what makes the verdict checkable.
    assert any("arc" in b for b in kalsarpa.basis)
    assert any("Rahu in" in b for b in kalsarpa.basis)


def test_kalsarpa_absent_when_planets_straddle_the_axis():
    """Planets on both sides of the axis means no Kaal Sarpa, by any definition.

    Varanasi 1988 is 5-vs-2 across the axis by degree, and still
    4-vs-1 after excluding the two planets conjunct a node by sign. Planets
    remain on both sides under either reading, so no definition of "all planets
    hemmed between Rahu and Ketu" admits it. The verdict must therefore be
    False — even though AstrologyAPI reports it True. This test exists to stop
    anyone "fixing" the engine to match the reference.
    """
    chart = calculate_chart(**CHARTS["Varanasi 1988"])
    kalsarpa = _dosha(chart, "kaal")
    assert kalsarpa.is_present is False
    assert kalsarpa.severity == "none"


def test_shani_dosha_is_labelled_natal_not_transit():
    """Shani Dosha is a natal indicator and must say so.

    Comparing it against a *current* Sade Sati status compares a fixed natal
    fact against a moving transit, which is the category error that produced
    four spurious benchmark failures.
    """
    chart = calculate_chart(**CHARTS["Jaipur 2005"])
    shani = _dosha(chart, "shani")

    assert shani.convention == "natal_saturn_from_moon"
    assert any("Natal Moon in" in b for b in shani.basis)
    if shani.is_present:
        assert "natal indicator only" in shani.description


def test_uncontested_doshas_report_no_convention():
    """``convention`` is for genuine disputes, not decoration."""
    chart = calculate_chart(**CHARTS["Jaipur 2005"])
    manglik = _dosha(chart, "manglik")
    assert manglik.convention is None
