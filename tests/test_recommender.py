import pytest

from app.core.calculator import compute_aggregate, estimated_categories
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


@pytest.mark.parametrize(
    ("aggregate", "expected"),
    [(10, ["A", "B", "C"]), (11, ["B", "C"]), (20, ["B", "C"]),
     (21, ["C"]), (54, ["C"]), (55, [])],
)
def test_unofficial_category_cutoff_estimates(aggregate, expected):
    assert estimated_categories(aggregate) == expected


def test_real_data_loaded():
    schools = load_schools()
    assert len(schools) > 500
    assert {s.category for s in schools} == {"A", "B", "C"}


def test_categories_are_school_groups_and_gender_filter():
    schools = load_schools()
    assert {s.category for s in match_schools(8, schools)} == {"A", "B", "C"}
    assert {s.category for s in match_schools(16, schools)} == {"B", "C"}
    assert {s.category for s in match_schools(30, schools)} == {"C"}
    boys_view = match_schools(8, schools, gender="male")
    assert boys_view and all(s.gender != "girls" for s in boys_view)
    girls_view = match_schools(8, schools, gender="female")
    assert girls_view and all(s.gender != "boys" for s in girls_view)


def test_region_residency_programme_filters():
    schools = load_schools()
    r = match_schools(30, schools, region="ashanti", residency="day", programme="science")
    assert r and all(s.region == "Ashanti" and "day" in s.residency.split("/")
                     and "science" in s.programmes for s in r)
