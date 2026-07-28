import asyncio
import re
from typing import Protocol

from yuanqi_agent.errors import AgentError
from yuanqi_agent.retrieval.fusion import reciprocal_rank_fusion
from yuanqi_agent.retrieval.models import KnowledgeSearchResult, RetrievalCandidate
from yuanqi_agent.trusted_medical_knowledge import get_knowledge_governance_policy


class CandidateRetriever(Protocol):
    async def search(self, query: str, tenant_id: int, top_k: int) -> list[RetrievalCandidate]: ...


class HybridRetriever:
    def __init__(
        self,
        graph: CandidateRetriever,
        vector: CandidateRetriever,
        *,
        rrf_k: int = 60,
        timeout_seconds: float = 8.0,
    ):
        self._graph = graph
        self._vector = vector
        self._rrf_k = rrf_k
        self._timeout = timeout_seconds

    async def search(self, query: str, tenant_id: int, top_k: int) -> KnowledgeSearchResult:
        if tenant_id <= 0:
            raise AgentError("TENANT_CONTEXT_REQUIRED", "A verified tenant is required", 403)
        normalized = query.strip()
        if not normalized:
            raise AgentError("INVALID_RETRIEVAL_QUERY", "Query must not be blank", 422)

        governance = get_knowledge_governance_policy()
        retrieval_limit = top_k + len(governance.excluded_entities)
        graph_result, vector_result = await asyncio.gather(
            self._one(self._graph, normalized, tenant_id, retrieval_limit),
            self._one(self._vector, normalized, tenant_id, retrieval_limit),
        )
        degraded: list[str] = []
        ranked_lists: list[list[RetrievalCandidate]] = []
        for source, result in (("graph", graph_result), ("vector", vector_result)):
            if isinstance(result, Exception):
                degraded.append(source)
            else:
                ranked_lists.append(self._relevant(normalized, result))
        if not ranked_lists:
            raise AgentError(
                "KNOWLEDGE_RETRIEVAL_UNAVAILABLE",
                "Both graph and vector retrieval are unavailable",
                status_code=503,
            )

        fused = reciprocal_rank_fusion(ranked_lists, rrf_k=self._rrf_k, top_k=top_k)
        # Encyclopedia mode: return all relevant catalog matches ranked by
        # relevance. The answer layer labels them as unreviewed reference and
        # cites an authoritative source when one is present, rather than hiding
        # everything below a trust threshold.
        items = list(fused)
        return KnowledgeSearchResult(
            query=normalized,
            items=items,
            context=self._context(items),
            degraded_sources=degraded,
        )

    @classmethod
    def _relevant(
        cls, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]:
        query_terms = cls._terms(query)
        if not query_terms:
            return []
        accepted: list[RetrievalCandidate] = []
        governance = get_knowledge_governance_policy()
        for candidate in candidates:
            raw_path_values = candidate.metadata.get("path", [])
            path_values = raw_path_values if isinstance(raw_path_values, list) else []
            if governance.excludes(
                candidate.document_id,
                candidate.title,
                path_values,
            ):
                continue
            path = " ".join(str(value) for value in path_values)
            searchable = f"{candidate.title} {candidate.content} {path}".lower()
            lexical_match = any(term in searchable for term in query_terms)
            strong_vector_match = candidate.source == "vector" and candidate.raw_score >= 0.35
            exact_graph_seed = candidate.source == "graph" and candidate.raw_score >= 1.0
            if lexical_match or strong_vector_match or exact_graph_seed:
                accepted.append(candidate)
        return accepted

    @staticmethod
    def _terms(value: str) -> set[str]:
        normalized = value.lower()
        terms = set(re.findall(r"[a-z0-9]{3,}", normalized))
        generic = {
            "建议", "什么", "怎么", "如何", "可以", "应该", "需要", "吃药",
            "用药", "药物", "治疗", "疾病", "相关", "知识", "一下", "哪个",
            "慢性", "急性", "炎症", "情况", "问题",
        }
        for run in re.findall(r"[一-鿿㐀-䶿]+", normalized):
            terms.update(run[index : index + 2] for index in range(len(run) - 1))
        return {term for term in terms if term not in generic and len(term) >= 2}

    async def _one(
        self,
        retriever: CandidateRetriever,
        query: str,
        tenant_id: int,
        top_k: int,
    ) -> list[RetrievalCandidate] | Exception:
        try:
            return await asyncio.wait_for(
                retriever.search(query, tenant_id, top_k), timeout=self._timeout
            )
        except Exception as exc:
            return exc

    @staticmethod
    def _context(items: list) -> str:
        blocks: list[str] = []
        used = 0
        for item in items:
            block = f"[{item.citation_id}] {item.title}\n{item.content.strip()}"
            if used + len(block) > 12_000:
                break
            blocks.append(block)
            used += len(block)
        return "\n\n".join(blocks)
