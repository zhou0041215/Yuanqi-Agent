import re
from typing import Any, ClassVar

from neo4j import AsyncDriver, RoutingControl

from yuanqi_agent.retrieval.models import RetrievalCandidate

# Encyclopedia mode: returns the full medical catalog (labeled as unreviewed
# reference in the answer layer). Reviewed entities additionally carry an
# authoritative source that the answer layer can cite.
GRAPH_SEARCH_QUERY = """
MATCH (start)
WHERE any(label IN labels(start) WHERE label IN $allowed_labels)
  AND coalesce(start.retrievalStatus, '') <> 'EXCLUDED'
  AND any(term IN $terms WHERE
    toLower(coalesce(start.name, '')) CONTAINS term OR
    toLower(coalesce(start.title, '')) CONTAINS term OR
    toLower(coalesce(start.code, '')) CONTAINS term OR
    toLower(coalesce(start.summary, '')) CONTAINS term OR
    toLower(coalesce(start.desc, '')) CONTAINS term OR
    toLower(coalesce(start.catalogSummary, '')) CONTAINS term OR
    toLower(coalesce(start.别名, '')) CONTAINS term
  )
WITH start,
     toLower(coalesce(start.name, '')) AS lower_name,
     size([term IN $terms
           WHERE toLower(coalesce(start.name, '')) CONTAINS term]) AS term_hits
WITH start, term_hits,
     CASE
       // Exact entity name typed by the user.
       WHEN lower_name IN $terms THEN 0
       // The whole entity name occurs in the question ("干燥综合征忌口什么").
       WHEN size(lower_name) >= 2 AND $query CONTAINS lower_name THEN 1
       // Loose bigram overlap only — ranked below real name matches.
       ELSE 2
     END AS match_priority
// Tie-break on how much of the question the name actually covers, so
// "干燥综合征" outranks "A-V综合征" instead of losing on alphabetical order.
ORDER BY match_priority ASC, term_hits DESC, size(start.name) ASC, start.name ASC
LIMIT $seed_limit
OPTIONAL MATCH (start)-[rel:
  HAS_SYMPTOM|TREATED_BY|BELONGS_TO|COMPLICATION|REQUIRES_EXAM
  |HAS_THERAPY|RECOMMENDED_EAT|AVOID_EAT|RECOMMENDED_RECIPE
]-(neighbor)
WHERE any(label IN labels(neighbor) WHERE label IN $allowed_labels)
  AND coalesce(neighbor.retrievalStatus, '') <> 'EXCLUDED'
WITH start, match_priority, term_hits,
     collect(DISTINCT neighbor)[0..$neighbor_limit] AS neighbors
UNWIND [start] + neighbors AS related
WITH related,
     min(CASE WHEN related = start THEN 0 ELSE 1 END) AS hops,
     min(match_priority) AS match_priority,
     max(term_hits) AS term_hits,
     collect(DISTINCT [
       coalesce(start.name, start.title, start.code, toString(start.id)),
       coalesce(related.name, related.title, related.code, toString(related.id))
     ])[0] AS path_labels
RETURN coalesce(
         related.entityKey,
         labels(related)[0] + ':' + coalesce(related.name, toString(related.id))
       ) AS entity_key,
       coalesce(related.name, related.title, related.code, '未知实体') AS title,
       coalesce(
         related.summary, related.description, related.desc,
         related.catalogSummary, related.简介,
         related.name, related.title, related.code, '暂无描述'
       ) AS content,
       labels(related) AS labels,
       related.id AS entity_id,
       coalesce(related.sourceUri, related.source_uri,
                related.catalogSourceUri, '') AS source_uri,
       coalesce(related.sourceTitle, related.source_title,
                related.catalogSourceTitle, '') AS source_title,
       coalesce(related.knowledgeVersion, related.version, 1) AS knowledge_version,
       toUpper(coalesce(related.reviewStatus, related.governanceStatus, ''))
         AS review_status,
       match_priority,
       term_hits,
       hops,
       path_labels
ORDER BY match_priority ASC, hops ASC, term_hits DESC, title ASC
LIMIT $limit
""".strip()


class Neo4jGraphRetriever:
    _ALLOWED_LABELS: ClassVar[tuple[str, ...]] = (
        "Disease",
        "Symptom",
        "Drug",
        "Department",
        "Exam",
        # Diet and therapy entities were imported but previously unreachable
        # from Q&A, so "这个病忌口什么" could never be answered from the graph.
        "Food",
        "Therapy",
    )

    def __init__(self, driver: AsyncDriver, database: str):
        self._driver = driver
        self._database = database

    async def search(self, query: str, tenant_id: int, top_k: int) -> list[RetrievalCandidate]:
        terms = self._terms(query)
        records, _, _ = await self._driver.execute_query(
            GRAPH_SEARCH_QUERY,
            parameters_={
                # Reserved for a future tenant-scoped graph. It is deliberately
                # supplied from verified runtime context and never from the user.
                "tenant_id": tenant_id,
                "allowed_labels": list(self._ALLOWED_LABELS),
                "terms": terms,
                # Used to detect entity names that occur verbatim in the question.
                "query": query.strip().lower(),
                "seed_limit": min(max(top_k, 5), 20),
                "neighbor_limit": 12,
                "limit": top_k,
            },
            database_=self._database,
            routing_=RoutingControl.READ,
        )
        candidates: list[RetrievalCandidate] = []
        for record in records:
            data = self._record_data(record)
            document_id = str(data.get("entity_key") or "").strip()
            title = str(data.get("title") or "").strip()
            content = str(data.get("content") or "").strip()
            if not document_id or not title or not content:
                continue
            hops = max(0, int(data.get("hops") or 0))
            match_priority = max(0, int(data.get("match_priority") or 0))
            # Report the node's real tier. Claiming PUBLISHED for every node
            # would let unreviewed catalog content be cited as reviewed.
            source_uri = str(data.get("source_uri") or "")
            reviewed = (
                str(data.get("review_status") or "") in {"PUBLISHED", "APPROVED"}
                and source_uri.startswith("https://")
            )
            candidates.append(
                RetrievalCandidate(
                    document_id=document_id,
                    title=title,
                    content=content,
                    source="graph",
                    raw_score=(
                        1.0 / (1.0 + hops)
                        if match_priority == 0
                        else (0.7 if match_priority == 1 else 0.4) / (1.0 + hops)
                    ),
                    metadata={
                        "labels": list(data.get("labels") or []),
                        "entityId": data.get("entity_id"),
                        "hops": hops,
                        "matchPriority": match_priority,
                        "path": list(data.get("path_labels") or []),
                        "source_uri": source_uri,
                        "source_title": str(data.get("source_title") or ""),
                        "knowledge_version": int(data.get("knowledge_version") or 1),
                        "governance_status": (
                            "PUBLISHED" if reviewed else "LEGACY_UNREVIEWED"
                        ),
                    },
                )
            )
        return candidates

    @staticmethod
    def _terms(query: str) -> list[str]:
        normalized = query.strip().lower()
        if not normalized:
            raise ValueError("query must not be blank")
        tokens = re.findall(r"[a-z0-9]+", normalized)
        cjk_runs = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", normalized)
        tokens.extend(cjk_runs)
        for run in cjk_runs:
            tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
        return list(dict.fromkeys(tokens))[:12]

    @staticmethod
    def _record_data(record: Any) -> dict[str, Any]:
        if hasattr(record, "data"):
            return dict(record.data())
        return dict(record)
