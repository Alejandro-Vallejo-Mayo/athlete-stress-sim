"""Unit tests for sport classification."""

from __future__ import annotations

from athlete_stress_sim.core.etl.sports import (
    SportKind,
    classify_sport,
    is_elliptical,
    is_running,
    is_strength,
)


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


def test_running_classification() -> None:
    assert is_running("running", "street")
    assert is_running("running", "treadmill")
    assert classify_sport("running", "generic") is SportKind.RUNNING


def test_elliptical_by_sport() -> None:
    assert is_elliptical("elliptical", "")
    assert is_elliptical("cross_trainer", "")
    assert classify_sport("elliptical", "") is SportKind.ELLIPTICAL


def test_elliptical_by_sub_sport() -> None:
    assert is_elliptical("fitness_equipment", "elliptical")
    assert is_elliptical("training", "elliptical_trainer")
    assert classify_sport("training", "indoor-elliptical") is SportKind.ELLIPTICAL


def test_elliptical_takes_precedence_over_generic_training() -> None:
    assert classify_sport("training", "elliptical") is SportKind.ELLIPTICAL


def test_polar_cardio_training_is_elliptical() -> None:
    assert is_elliptical("training", "cardio_training")
    assert not is_strength("training", "cardio_training")
    assert classify_sport("training", "cardio_training") is SportKind.ELLIPTICAL


def test_unknown_sport_is_other() -> None:
    assert classify_sport("cycling", "road") is SportKind.OTHER
    assert classify_sport("", "") is SportKind.OTHER
