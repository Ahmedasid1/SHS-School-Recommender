from functools import lru_cache               # Used to cache the assistant instance for performance
from typing import Literal                    # Used to specify literal types for certain fields in the Grades model

from fastapi import APIRouter, Depends, HTTPException  # FastAPI imports for routing, dependency injection, and error handling
from pydantic import BaseModel, Field                # Pydantic imports for defining request and response models

from app.core.recommender import recommend         # Import the recommend function for school recommendations
from app.llm.client import LLMError                     # Import the LLMError exception for handling assistant errors
from app.services.assistant import Assistant          # Import the Assistant class for handling assistant interactions

router = APIRouter()                                # Create an API router instance for defining routes


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)  # The message to send to the assistant


class AskResponse(BaseModel):
    answer: str                                      # The assistant's answer to the message
    sources: list[dict]                              # The sources referenced by the assistant
    tool_calls: list[dict]                           # The tool calls made by the assistant


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


# Model for the grades input used in school recommendations
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


# Model for the school recommendation response
class RecommendationResponse(BaseModel):
    schools: list[dict]  # The list of recommended schools

# Endpoint for recommending schools based on student grades and preferences
@router.post("/recommend", response_model=RecommendationResponse)
def recommend_schools(body: Grades):
    core = {k: getattr(body, k) for k in ("english", "mathematics", "science", "social_studies")}
    try:
        schools = recommend(core, body.electives, body.gender, body.region, body.residency, body.programme)
        return RecommendationResponse(schools=schools)  
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
