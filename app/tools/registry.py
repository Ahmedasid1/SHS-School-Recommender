# This module defines the argument models and tool specifications for the LLM to interact with the system.
"""Tools the LLM may call. Each wraps deterministic code or retrieval, validates its
arguments, and returns plain JSON-able data. Errors are returned (not raised) so the
model can correct itself."""
import ast 
import json
import logging
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.calculator import compute_aggregate, estimated_categories
from app.rag.retriever import RetrievalError, Retriever
from app.llm.client import LLMError
from app.tools.matcher import PROGRAMMES, load_schools, match_schools

logger = logging.getLogger(__name__)

MAX_SCHOOLS_RETURNED = 10


class AggregateArgs(BaseModel):
    english: int
    mathematics: int
    science: int
    social_studies: int
    electives: dict[str, int] = Field(description="Elective subject name to grade")


class _Filters(BaseModel):
    gender: Literal["male", "female"] | None = None
    region: str | None = None
    residency: Literal["day", "boarding"] | None = None
    programme: str | None = None

    @field_validator("gender", "residency", mode="before")
    @classmethod
    def _normalise(cls, value):
        if isinstance(value, str):
            value = value.strip().lower()
            return {"girls": "female", "girl": "female", "boys": "male", "boy": "male"}.get(value, value)
        return value


class FindSchoolsArgs(_Filters):
    aggregate: int = Field(ge=6, le=54)


class RecommendArgs(AggregateArgs, _Filters):
    pass


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)


TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "compute_aggregate",
        "description": "Compute a BECE aggregate from grades (1-9): 4 core subjects plus best 2 electives. "
                       "Also returns the unofficial estimated school categories.",
        "parameters": {"type": "object", "properties": {
            "english": {"type": "integer"}, "mathematics": {"type": "integer"},
            "science": {"type": "integer"}, "social_studies": {"type": "integer"},
            "electives": {"type": "object", "description": "elective subject name -> grade (1-9)",
                          "additionalProperties": {"type": "integer"}},
        }, "required": ["english", "mathematics", "science", "social_studies", "electives"]}}},
    {"type": "function", "function": {
        "name": "find_schools",
        "description": "List schools a candidate with a given aggregate may consider, with optional filters. "
                       "Results use an unofficial category estimate.",
        "parameters": {"type": "object", "properties": {
            "aggregate": {"type": "integer", "description": "BECE aggregate, 6-54"},
            "gender": {"type": "string", "enum": ["male", "female"]},
            "region": {"type": "string", "description": "Ghana region, e.g. Ashanti"},
            "residency": {"type": "string", "enum": ["day", "boarding"]},
            "programme": {"type": "string", "enum": list(PROGRAMMES)},
        }, "required": ["aggregate"]}}},
    {"type": "function", "function": {
        "name": "recommend_schools",
        "description": "ONE-STEP tool: given a candidate's grades and optional filters, compute the aggregate AND "
                       "list matching schools. Use this whenever the user gives grades and wants schools.",
        "parameters": {"type": "object", "properties": {
            "english": {"type": "integer"}, "mathematics": {"type": "integer"},
            "science": {"type": "integer"}, "social_studies": {"type": "integer"},
            "electives": {"type": "object", "description": "elective subject name -> grade (1-9)",
                          "additionalProperties": {"type": "integer"}},
            "gender": {"type": "string", "enum": ["male", "female"]},
            "region": {"type": "string", "description": "Ghana region, e.g. Ashanti"},
            "residency": {"type": "string", "enum": ["day", "boarding"]},
            "programme": {"type": "string", "enum": list(PROGRAMMES)},
        }, "required": ["english", "mathematics", "science", "social_studies", "electives"]}}},
    {"type": "function", "function": {
        "name": "search_knowledge",
        "description": "Search the knowledge base for how the system works: methodology, unofficial cutoffs, "
                       "CSSPS placement, data source and limits. Use for any question about the system or process.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look up"},
        }, "required": ["query"]}}},
]


TOOL_NAMES = ("compute_aggregate", "find_schools", "recommend_schools", "search_knowledge")


def parse_text_tool_call(content: str) -> dict | None:
    """Recover a tool call a small model wrote as plain text instead of issuing it properly.

    Returns {"name", "arguments"} or None. Only a JSON object plus a known tool name is accepted."""
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(content[start:end + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("name") if obj.get("name") in TOOL_NAMES else next((t for t in TOOL_NAMES if t in content), None)
    if not name:
        return None
    arguments = obj.get("parameters") or obj.get("arguments") or (obj if "name" not in obj else {})
    return {"name": name, "arguments": arguments if isinstance(arguments, dict) else {}}


def _coerce(arguments: dict) -> dict:
    """Small models often stringify nested values; decode them before validation."""
    fixed = {}
    for key, value in (arguments or {}).items():
        if isinstance(value, str) and value.strip()[:1] in ("{", "["):
            try:
                value = json.loads(value)
            except ValueError:
                try:
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    pass
        fixed[key] = value
    return fixed


class Toolbox:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever
        self._schools = None
        self.sources: list[dict] = []

    @property
    def schools(self):
        if self._schools is None:
            self._schools = load_schools()
        return self._schools

    def _add_source(self, source: str, detail: str | None = None) -> None:
        entry = {"source": source, **({"detail": detail} if detail else {})}
        if entry not in self.sources:
            self.sources.append(entry)

    def execute(self, name: str, arguments: dict) -> dict:
        handlers = {
            "compute_aggregate": (AggregateArgs, self._compute_aggregate),
            "find_schools": (FindSchoolsArgs, self._find_schools),
            "recommend_schools": (RecommendArgs, self._recommend_schools),
            "search_knowledge": (SearchKnowledgeArgs, self._search_knowledge),
        }
        if name not in handlers:
            return {"error": f"Unknown tool '{name}'. Available: {', '.join(handlers)}"}
        model, handler = handlers[name]
        try:
            args = model(**_coerce(arguments))
            return handler(args)
        except ValidationError as exc:
            return {"error": "Invalid arguments: " + "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())}
        except ValueError as exc:
            return {"error": str(exc)}
        except (RetrievalError, LLMError) as exc:
            logger.warning("tool %s failed: %s", name, exc)
            return {"error": f"Knowledge search is unavailable: {exc}"}
        except TypeError as exc:
            return {"error": f"Bad arguments: {exc}"}

    def _compute_aggregate(self, a: AggregateArgs) -> dict:
        core = {k: getattr(a, k) for k in ("english", "mathematics", "science", "social_studies")}
        aggregate = compute_aggregate(core, a.electives)
        self._add_source("Computed by the aggregate calculator")
        return {"aggregate": aggregate, "estimated_categories": estimated_categories(aggregate),
                "note": "Category estimate uses unofficial cutoffs; CSSPS decides actual placement."}

    def _find_schools(self, a: FindSchoolsArgs) -> dict:
        matches = match_schools(a.aggregate, self.schools, a.gender, a.region, a.residency, a.programme)
        self._add_source("GES 2019 SHS list (data/schools.csv)")
        return {
            "total_matches": len(matches),
            "by_category": dict(Counter(s.category for s in matches)),
            "showing": min(len(matches), MAX_SCHOOLS_RETURNED),
            "schools": [{"name": s.name, "category": s.category, "region": s.region, "gender": s.gender,
                         "residency": s.residency, "programmes": list(s.programmes)}
                        for s in matches[:MAX_SCHOOLS_RETURNED]],
            "note": "Categories are an unofficial estimate; CSSPS decides actual placement.",
        }

    def _recommend_schools(self, a: RecommendArgs) -> dict:
        agg = self._compute_aggregate(a)
        found = self._find_schools(FindSchoolsArgs(
            aggregate=agg["aggregate"], gender=a.gender, region=a.region,
            residency=a.residency, programme=a.programme))
        return {"aggregate": agg["aggregate"], "estimated_categories": agg["estimated_categories"], **found}

    def _search_knowledge(self, a: SearchKnowledgeArgs) -> dict:
        hits = self.retriever.retrieve(a.query)
        if not hits:
            return {"passages": [], "message": "No relevant passages found in the knowledge base."}
        for h in hits:
            self._add_source(h.chunk.metadata.get("source", "unknown"), h.chunk.id)
        return {"passages": [{"source": h.chunk.metadata.get("source"), "text": h.chunk.text,
                              "score": round(h.score, 3)} for h in hits]}
