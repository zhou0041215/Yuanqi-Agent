from collections import defaultdict

from yuanqi_agent.retrieval.models import FusedKnowledge, RetrievalCandidate


def _trust_score(candidate: RetrievalCandidate, sources: set[str]) -> int:
    """Return an auditable evidence score, not a model probability."""
    metadata = candidate.metadata
    score = 0
    source_uri = str(metadata.get("source_uri") or "")
    if source_uri.startswith("https://"):
        score += 35
    if str(metadata.get("governance_status") or "").upper() == "PUBLISHED":
        score += 25
    if metadata.get("reviewed_at") or metadata.get("published_at"):
        score += 10
    if int(metadata.get("knowledge_version") or 0) > 0:
        score += 5
    if metadata.get("entity_type") or metadata.get("labels"):
        score += 10
    if len(sources) > 1:
        score += 10
    if metadata.get("source_published_at"):
        score += 5
    return min(score, 100)


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalCandidate]],
    *,
    rrf_k: int,
    top_k: int,
) -> list[FusedKnowledge]:
    if rrf_k <= 0 or top_k <= 0:
        raise ValueError("rrf_k and top_k must be positive")

    scores: defaultdict[str, float] = defaultdict(float)
    best: dict[str, RetrievalCandidate] = {}
    sources: defaultdict[str, set[str]] = defaultdict(set)
    source_ranks: defaultdict[str, dict[str, int]] = defaultdict(dict)

    for ranked in ranked_lists:
        seen: set[str] = set()
        for rank, candidate in enumerate(ranked, start=1):
            key = candidate.document_id
            if key in seen:
                continue
            seen.add(key)
            scores[key] += 1.0 / (rrf_k + rank)
            sources[key].add(candidate.source)
            source_ranks[key][candidate.source] = rank
            current = best.get(key)
            candidate_quality = (
                _trust_score(candidate, {candidate.source}),
                len(candidate.content),
                candidate.raw_score,
            )
            current_quality = (
                _trust_score(current, {current.source}),
                len(current.content),
                current.raw_score,
            ) if current is not None else (-1, -1, -1.0)
            if current is None or candidate_quality > current_quality:
                best[key] = candidate

    ordered_keys = sorted(scores, key=lambda key: (-scores[key], key))[:top_k]
    return [
        FusedKnowledge(
            citation_id=f"K{position}",
            document_id=key,
            title=best[key].title,
            content=best[key].content,
            rrf_score=scores[key],
            sources=sorted(sources[key]),
            metadata={
                **best[key].metadata,
                "sourceRanks": source_ranks[key],
                "bestRawScore": best[key].raw_score,
                "trustScore": _trust_score(best[key], sources[key]),
                "evidenceLevel": (
                    "HIGH"
                    if _trust_score(best[key], sources[key]) >= 80
                    else "SUPPORTED"
                    if _trust_score(best[key], sources[key]) >= 60
                    else "INSUFFICIENT"
                ),
            },
        )
        for position, key in enumerate(ordered_keys, start=1)
    ]
