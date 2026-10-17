"""BECE aggregate calculation and category qualification."""

CORE_SUBJECTS = ("english", "mathematics", "science", "social_studies")
BEST_ELECTIVES = 2
MIN_GRADE, MAX_GRADE = 1, 9


# Unofficial aggregate heuristic; not a CSSPS placement rule.
CATEGORY_MAX_AGGREGATE = {"A": 10, "B": 20, "C": 54}


def _validate(subject: str, grade: int) -> None:
    if not isinstance(grade, int) or not MIN_GRADE <= grade <= MAX_GRADE:
        raise ValueError(f"Grade for '{subject}' must be an integer {MIN_GRADE}-{MAX_GRADE}, got {grade!r}")


def compute_aggregate(core: dict[str, int], electives: dict[str, int]) -> int:
    """Sum of the 4 core subject grades and the best 2 elective grades (lower is better)."""
    missing = [s for s in CORE_SUBJECTS if s not in core]
    if missing:
        raise ValueError(f"Missing core subjects: {', '.join(missing)}")
    if len(electives) < BEST_ELECTIVES:
        raise ValueError(f"At least {BEST_ELECTIVES} elective subjects are required")

    for subject in CORE_SUBJECTS:
        _validate(subject, core[subject])
    for subject, grade in electives.items():
        _validate(subject, grade)

    best = sorted(electives.values())[:BEST_ELECTIVES]
    return sum(core[s] for s in CORE_SUBJECTS) + sum(best)


def estimated_categories(aggregate: int) -> list[str]:
    """Estimate categories using the project's unofficial aggregate cutoffs."""
    return [category for category, limit in CATEGORY_MAX_AGGREGATE.items() if aggregate <= limit]
