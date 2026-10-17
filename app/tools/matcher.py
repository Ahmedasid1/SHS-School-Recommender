"""Match a candidate's aggregate to eligible schools and programmes."""
import csv
from dataclasses import dataclass
from pathlib import Path

from app.core.calculator import estimated_categories

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "schools.csv"
PROGRAMMES = ("agric", "business", "technical", "home_economics", "visual_arts", "general_arts", "science")
_GENDER_ALIASES = {"male": "boys", "boy": "boys", "boys": "boys",
                   "female": "girls", "girl": "girls", "girls": "girls"}


@dataclass(frozen=True)
class School:
    name: str
    category: str
    region: str
    gender: str
    residency: str
    programmes: tuple[str, ...]


def load_schools(path: Path = DEFAULT_DATA) -> list[School]:
    with open(path, newline="", encoding="utf-8") as f:
        return [
            School(
                name=r["school"].strip(),
                category=r["category"].strip().upper(),
                region=r["region"].strip(),
                gender=r["gender"].strip().lower(),
                residency=r["residency"].strip().lower(),
                programmes=tuple(p for p in PROGRAMMES if r[p].strip().lower() == "yes"),
            )
            for r in csv.DictReader(f)
        ]


def match_schools(
    aggregate: int,
    schools: list[School],
    gender: str | None = None,
    region: str | None = None,
    residency: str | None = None,
    programme: str | None = None,
) -> list[School]:
    """Schools matching the aggregate heuristic and selected filters."""
    estimated = estimated_categories(aggregate)
    wanted_gender = _GENDER_ALIASES.get(gender.lower(), gender.lower()) if gender else None
    result = []
    for s in schools:
        if s.category not in estimated:
            continue
        if wanted_gender and s.gender not in ("mixed", wanted_gender):
            continue
        if region and s.region.lower() != region.lower():
            continue
        if residency and residency.lower() not in s.residency.split("/"):
            continue
        if programme and programme.lower() not in s.programmes:
            continue
        result.append(s)
    return sorted(result, key=lambda s: (s.category, s.name))
