from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.recommender import recommend
from app.llm.client import LLMError
from app.services.assistant import Assistant

router = APIRouter()


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    tool_calls: list[dict]


@lru_cache
def get_assistant() -> Assistant:
    return Assistant()


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, assistant: Assistant = Depends(get_assistant)):
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message must not be blank.")
    try:
        result = assistant.ask(body.message)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"The assistant is unavailable: {exc}")
    return AskResponse(answer=result.answer, sources=result.sources, tool_calls=result.tool_calls)


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
