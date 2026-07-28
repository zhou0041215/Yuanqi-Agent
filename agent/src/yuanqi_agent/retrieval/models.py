from typing import Any, Literal

from pydantic import Field

from yuanqi_agent.models import StrictModel


class RetrievalCandidate(StrictModel):
    document_id: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=20_000)
    source: Literal["graph", "vector"]
    raw_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class FusedKnowledge(StrictModel):
    citation_id: str = Field(pattern=r"^K[1-9][0-9]*$")
    document_id: str
    title: str
    content: str
    rrf_score: float
    sources: list[Literal["graph", "vector"]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResult(StrictModel):
    query: str
    items: list[FusedKnowledge]
    context: str
    degraded_sources: list[Literal["graph", "vector"]] = Field(default_factory=list)
