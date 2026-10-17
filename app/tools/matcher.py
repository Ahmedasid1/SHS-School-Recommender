"""Match a candidate's aggregate to eligible schools and programmes."""
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "schools.csv"


@dataclass(frozen=True)
class Offering:
    school: str
    category: str
    region: str
    gender: str
    residency: str
    programme: str
    cutoff_aggregate: int


def load_offerings(path: Path = DEFAULT_DATA) -> list[Offering]:
    with open(path, newline="", encoding="utf-8") as f:
        return [
            Offering(
                school=r["school"].strip(),
                category=r["category"].strip().upper(),
                region=r["region"].strip(),
                gender=r["gender"].strip().lower(),
                residency=r["residency"].strip().lower(),
                programme=r["programme"].strip(),
                cutoff_aggregate=int(r["cutoff_aggregate"]),
            )
            for r in csv.DictReader(f)
        ]


def match_offerings(
    aggregate: int,
    offerings: list[Offering],
    gender: str | None = None,
    region: str | None = None,
    residency: str | None = None,
) -> list[Offering]:
    """Offerings the candidate can apply to, best (most competitive) schools first."""
    result = []
    for o in offerings:
        if aggregate > o.cutoff_aggregate:
            continue
        if gender and o.gender not in ("mixed", gender.lower()):
            continue
        if region and o.region.lower() != region.lower():
            continue
        if residency and o.residency != residency.lower():
            continue
        result.append(o)
    return sorted(result, key=lambda o: (o.category, o.cutoff_aggregate, o.school, o.programme))
