# This module defines the shared request contract for BECE results.
# Manual entry, file upload, and chat all produce a Grades object.
"""Shared request contract for BECE results (manual entry, file upload and chat all produce a Grades)."""
from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.calculator import BEST_ELECTIVES, MAX_GRADE, MIN_GRADE


def _normalise(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


class Grades(BaseModel):
    english: int
    mathematics: int
    science: int
    social_studies: int
    electives: dict[str, int]
    gender: Literal["male", "female"] | None = None
    region: str | None = None
    residency: Literal["day", "boarding"] | None = None
    programme: str | None = None

    @field_validator("english", "mathematics", "science", "social_studies")
    @classmethod
    def _core_in_range(cls, v: int) -> int:
        if not MIN_GRADE <= v <= MAX_GRADE:
            raise ValueError(f"Grade must be {MIN_GRADE}-{MAX_GRADE}")
        return v

    @field_validator("electives")
    @classmethod
    def _electives_valid(cls, v: dict[str, int]) -> dict[str, int]:
        electives = {_normalise(k): g for k, g in v.items()}
        if len(electives) < BEST_ELECTIVES:
            raise ValueError(f"At least {BEST_ELECTIVES} elective subjects are required")
        if any(not MIN_GRADE <= g <= MAX_GRADE for g in electives.values()):
            raise ValueError(f"Elective grades must be {MIN_GRADE}-{MAX_GRADE}")
        return electives
