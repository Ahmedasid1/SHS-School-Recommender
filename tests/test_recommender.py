import pytest

from app.core.calculator import compute_aggregate, qualifying_categories
from app.tools.matcher import load_offerings, match_offerings

CORE = {"english": 2, "mathematics": 3, "science": 2, "social_studies": 3}


def test_aggregate_uses_core_and_best_two_electives():
    assert compute_aggregate(CORE, {"rme": 4, "french": 1, "ict": 2, "pre_tech": 9}) == 10 + 1 + 2


def test_missing_core_subject_rejected():
    with pytest.raises(ValueError):
        compute_aggregate({"english": 1}, {"a": 1, "b": 1})


def test_invalid_grade_rejected():
    with pytest.raises(ValueError):
        compute_aggregate({**CORE, "english": 10}, {"a": 1, "b": 1})


def test_too_few_electives_rejected():
    with pytest.raises(ValueError):
        compute_aggregate(CORE, {"a": 1})


def test_categories():
    assert qualifying_categories(8) == ["A", "B", "C", "D"]
    assert qualifying_categories(25) == ["C", "D"]
    assert qualifying_categories(54) == ["D"]


def test_matching_filters_by_cutoff_and_gender():
    offerings = load_offerings()
    names = {o.school for o in match_offerings(9, offerings, gender="male")}
    assert "Sample Boys SHS" in names
    assert "Sample Girls SHS" not in names
    assert all(o.cutoff_aggregate >= 9 for o in match_offerings(9, offerings))


def test_matching_filters_by_region_and_residency():
    offerings = load_offerings()
    assert {o.region for o in match_offerings(20, offerings, region="central")} == {"Central"}
    assert {o.residency for o in match_offerings(20, offerings, residency="day")} == {"day"}
