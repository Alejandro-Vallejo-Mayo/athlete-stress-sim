"""Unit tests for sport classification."""

from __future__ import annotations

from athlete_stress_sim.core.etl.sports import is_strength


def test_strength_by_sport() -> None:
    assert is_strength("training", "")
    assert is_strength("strength_training", "")


def test_strength_by_sub_sport() -> None:
    assert is_strength("training", "strength_training")
    assert is_strength("training", "muscle_toning")


def test_running_is_not_strength() -> None:
    assert not is_strength("running", "")
    assert not is_strength("running", "street")


def test_normalizes_case_and_separators() -> None:
    assert is_strength("Strength Training", "")
    assert is_strength("TRAINING", "Strength-Training")


def test_empty_is_not_strength() -> None:
    assert not is_strength("", "")
