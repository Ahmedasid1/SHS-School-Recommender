import csv

import pytest

from app.core.calculator import compute_aggregate, estimated_categories
from app.tools.matcher import DEFAULT_DATA, PROGRAMMES, load_schools, match_schools

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


def test_school_csv_has_complete_unique_records_and_valid_values():
    expected_fields = ["school", "category", "region", "gender", "residency", *PROGRAMMES]
    with DEFAULT_DATA.open(newline="", encoding="utf-8") as school_file:
        reader = csv.DictReader(school_file)
        assert reader.fieldnames == expected_fields
        rows = list(reader)

    assert rows
    assert all(all(row[field].strip() for field in expected_fields) for row in rows)
    assert {row["category"].strip().upper() for row in rows} == {"A", "B", "C"}
    assert all(row["gender"].strip().lower() in {"boys", "girls", "mixed"} for row in rows)
    assert all(
        row["residency"].strip().lower() in {"day", "boarding", "day/boarding"}
        for row in rows
    )
    assert all(
        row[programme].strip().lower() in {"yes", "no"}
        for row in rows
        for programme in PROGRAMMES
    )

    school_names = [row["school"].strip().casefold() for row in rows]
    assert len(school_names) == len(set(school_names))


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
