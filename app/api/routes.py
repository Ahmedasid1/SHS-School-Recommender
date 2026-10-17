from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.recommender import recommend

router = APIRouter()


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


@router.post("/recommend")
def recommend_schools(body: Grades):
    core = {k: getattr(body, k) for k in ("english", "mathematics", "science", "social_studies")}
    try:
        return recommend(core, body.electives, body.gender, body.region, body.residency, body.programme)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
