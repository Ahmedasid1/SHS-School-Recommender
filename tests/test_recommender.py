import pytest

from app.core.calculator import compute_aggregate, qualifying_categories
from app.tools.matcher import load_schools, match_schools

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
    assert qualifying_categories(8) == ["A", "B", "C"]
    assert qualifying_categories(25) == ["C"]
    assert qualifying_categories(54) == ["C"]


def test_real_data_loaded():
    schools = load_schools()
    assert len(schools) > 500
    assert {s.category for s in schools} == {"A", "B", "C"}


def test_category_eligibility_and_gender():
    schools = load_schools()
    assert any(s.category == "A" for s in match_schools(8, schools))
    assert all(s.category == "C" for s in match_schools(30, schools))
    girls_view = match_schools(8, schools, gender="male")
    assert girls_view and all(s.gender != "girls" for s in girls_view)


def test_region_residency_programme_filters():
    schools = load_schools()
    r = match_schools(30, schools, region="ashanti", residency="day", programme="science")
    assert r and all(s.region == "Ashanti" and "day" in s.residency.split("/")
                     and "science" in s.programmes for s in r)
