from typing import Any
from uuid import uuid4

import httpx
import pytest
from qdrant_client import AsyncQdrantClient

from yuanqi_agent.errors import AgentError
from yuanqi_agent.retrieval.embedding import DeterministicHashEmbedding, HttpEmbeddingProvider
from yuanqi_agent.retrieval.fusion import reciprocal_rank_fusion
from yuanqi_agent.retrieval.graph import GRAPH_SEARCH_QUERY, Neo4jGraphRetriever
from yuanqi_agent.retrieval.hybrid import HybridRetriever
from yuanqi_agent.retrieval.medical_documents import build_disease_document
from yuanqi_agent.retrieval.models import RetrievalCandidate
from yuanqi_agent.retrieval.vector import QdrantKnowledgeStore, QdrantVectorRetriever
from yuanqi_agent.runtime import RequestRuntime
from yuanqi_agent.tools import ToolRegistry


def candidate(
    document_id: str,
    source: str,
    score: float,
    *,
    title: str | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id=document_id,
        title=title or document_id,
        content=f"content for {document_id}",
        source=source,
        raw_score=score,
        metadata={
            "source_uri": "https://example.org/published-evidence",
            "governance_status": "PUBLISHED",
            "knowledge_version": 1,
            "entity_type": "Disease",
        },
    )


def test_rrf_rewards_documents_returned_by_both_retrievers() -> None:
    graph = [candidate("Customer:1", "graph", 1.0), candidate("Risk:2", "graph", 0.5)]
    vector = [candidate("Risk:2", "vector", 0.99), candidate("Contract:3", "vector", 0.8)]

    fused = reciprocal_rank_fusion([graph, vector], rrf_k=60, top_k=3)

    assert fused[0].document_id == "Risk:2"
    assert fused[0].sources == ["graph", "vector"]
    assert fused[0].citation_id == "K1"
    assert fused[0].metadata["sourceRanks"] == {"graph": 2, "vector": 1}


def test_offline_embedding_tokenizes_cjk_characters_and_bigrams() -> None:
    tokens = DeterministicHashEmbedding._tokens("糖尿病常见症状")

    assert "糖尿" in tokens
    assert "尿病" in tokens
    assert "症状" in tokens


def test_medical_document_matches_graph_entity_key_and_canonical_relations() -> None:
    document = build_disease_document(
        {
            "properties": {
                "name": "糖尿病",
                "summary": "代谢性疾病",
                "病因": "胰岛素异常",
                "reviewStatus": "PUBLISHED",
                "sourceUri": "https://www.who.int/news-room/fact-sheets/detail/diabetes",
            },
            "symptoms": ["多饮", "多尿"],
            "drugs": ["二甲双胍"],
            "departments": ["内分泌科"],
            "complications": ["糖尿病肾病"],
            "exams": ["糖化血红蛋白"],
        }
    )

    assert document["document_id"] == "Disease:糖尿病"
    assert document["entity_key"] == "Disease:糖尿病"
    assert "常见症状线索：多尿、多饮" in document["content"]
    assert "相关药物线索：二甲双胍" in document["content"]
    assert document["metadata"]["entity_type"] == "Disease"
    assert document["metadata"]["governance_status"] == "PUBLISHED"


def test_medical_document_caps_high_degree_relationships() -> None:
    document = build_disease_document(
        {
            "properties": {
                "name": "高连接疾病",
                "reviewStatus": "PUBLISHED",
                "sourceUri": "https://example.org/governed-medical-source",
            },
            "symptoms": [f"症状-{index:03d}" for index in range(250)],
        }
    )

    assert "仅展示前 20 项，共 250 项" in document["content"]
    assert len(document["content"]) <= 20_000


def test_medical_document_indexes_catalog_data_as_legacy_unreviewed() -> None:
    """Encyclopedia mode: the whole catalog is indexed, tagged by trust tier."""
    catalog = build_disease_document(
        {
            "properties": {"name": "未审核疾病", "desc": "目录简介"},
            "symptoms": ["目录症状"],
        }
    )

    assert catalog["metadata"]["governance_status"] == "LEGACY_UNREVIEWED"
    assert "目录简介" in catalog["content"]
    assert "常见症状线索：目录症状" in catalog["content"]

    # A PUBLISHED claim without an HTTPS source is not trusted as reviewed.
    unsourced = build_disease_document(
        {"properties": {"name": "无来源疾病", "reviewStatus": "PUBLISHED"}}
    )
    assert unsourced["metadata"]["governance_status"] == "LEGACY_UNREVIEWED"


def test_medical_document_requires_a_name() -> None:
    with pytest.raises(ValueError, match="name"):
        build_disease_document({"properties": {"desc": "无名条目"}})


@pytest.mark.asyncio
async def test_http_embedding_provider_validates_and_reorders_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer internal-secret"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.2] * 64},
                    {"index": 0, "embedding": [0.1] * 64},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = HttpEmbeddingProvider(
            client,
            "http://embedding.internal/v1/embeddings",
            "enterprise-embedding",
            64,
            "internal-secret",
        )
        vectors = await provider.embed_documents(["first", "second"])

    assert vectors[0][0] == 0.1
    assert vectors[1][0] == 0.2


class FakeRecord(dict):
    def data(self) -> dict[str, Any]:
        return dict(self)


class CapturingDriver:
    def __init__(self) -> None:
        self.query = ""
        self.kwargs: dict[str, Any] = {}

    async def execute_query(self, query: str, **kwargs: Any):
        self.query = query
        self.kwargs = kwargs
        return (
            [
                FakeRecord(
                    entity_key="Customer:7",
                    title="华东客户 A",
                    content="存在合同履约风险",
                    labels=["Customer"],
                    entity_id=7,
                    match_priority=0,
                    hops=1,
                    path_labels=["华东客户 A", "风险 R1"],
                )
            ],
            None,
            None,
        )


@pytest.mark.asyncio
async def test_graph_retrieval_uses_fixed_cypher_and_tenant_parameter() -> None:
    driver = CapturingDriver()
    retriever = Neo4jGraphRetriever(driver, "neo4j")  # type: ignore[arg-type]
    malicious = "华东') MATCH (n) DETACH DELETE n //"

    result = await retriever.search(malicious, tenant_id=42, top_k=5)

    assert driver.query == GRAPH_SEARCH_QUERY
    assert malicious not in driver.query
    assert driver.kwargs["parameters_"]["tenant_id"] == 42
    assert driver.kwargs["parameters_"]["limit"] == 5
    assert result[0].document_id == "Customer:7"


@pytest.mark.asyncio
async def test_qdrant_search_is_tenant_isolated() -> None:
    client = AsyncQdrantClient(":memory:")
    embedding = DeterministicHashEmbedding(64)
    store = QdrantKnowledgeStore(client, "knowledge", embedding, 64)
    retriever = QdrantVectorRetriever(client, "knowledge", embedding)
    try:
        await store.ensure_collection()
        await store.upsert_documents(
            1,
            [
                {
                    "document_id": "tenant-1-chunk",
                    "entity_key": "Risk:1",
                    "title": "租户一风险",
                    "content": "供应商延期交付风险",
                    "source_uri": "https://example.org/tenant-1",
                    "metadata": {"governance_status": "PUBLISHED"},
                }
            ],
        )
        await store.upsert_documents(
            2,
            [
                {
                    "document_id": "tenant-2-chunk",
                    "entity_key": "Risk:2",
                    "title": "租户二风险",
                    "content": "供应商延期交付风险",
                    "source_uri": "https://example.org/tenant-2",
                    "metadata": {"governance_status": "PUBLISHED"},
                }
            ],
        )

        results = await retriever.search("供应商延期交付风险", tenant_id=1, top_k=10)

        assert [item.document_id for item in results] == ["Risk:1"]
        assert all("租户二" not in item.title for item in results)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_qdrant_search_returns_catalog_tier_with_its_label() -> None:
    """Catalog documents are searchable; the tier travels with each result."""
    client = AsyncQdrantClient(":memory:")
    embedding = DeterministicHashEmbedding(64)
    store = QdrantKnowledgeStore(client, "knowledge", embedding, 64)
    retriever = QdrantVectorRetriever(client, "knowledge", embedding)
    try:
        await store.ensure_collection()
        await store.upsert_documents(
            1,
            [
                {
                    "document_id": "Disease:目录疾病",
                    "entity_key": "Disease:目录疾病",
                    "title": "目录疾病",
                    "content": "疾病名称：目录疾病\n常见症状线索：目录症状",
                    "source_uri": "https://github.com/nuolade/disease-kb",
                    "metadata": {"governance_status": "LEGACY_UNREVIEWED"},
                }
            ],
        )

        results = await retriever.search("目录疾病 目录症状", tenant_id=1, top_k=10)

        assert [item.document_id for item in results] == ["Disease:目录疾病"]
        assert results[0].metadata["governance_status"] == "LEGACY_UNREVIEWED"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_qdrant_search_excludes_governed_legacy_entities() -> None:
    client = AsyncQdrantClient(":memory:")
    embedding = DeterministicHashEmbedding(64)
    store = QdrantKnowledgeStore(client, "knowledge", embedding, 64)
    retriever = QdrantVectorRetriever(client, "knowledge", embedding)
    try:
        await store.ensure_collection()
        await store.upsert_documents(
            1,
            [
                {
                    "document_id": "Disease:口腔干燥综合征",
                    "entity_key": "Disease:口腔干燥综合征",
                    "title": "口腔干燥综合征",
                    "content": "疾病名称：口腔干燥综合征",
                    "source_uri": "https://github.com/nuolade/disease-kb",
                    "metadata": {"governance_status": "LEGACY_UNREVIEWED"},
                }
            ],
        )

        results = await retriever.search(
            "口腔干燥综合征",
            tenant_id=1,
            top_k=10,
        )

        assert results == []
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_qdrant_store_rejects_unpublished_documents() -> None:
    client = AsyncQdrantClient(":memory:")
    store = QdrantKnowledgeStore(
        client, "knowledge", DeterministicHashEmbedding(64), 64
    )
    try:
        await store.ensure_collection()
        with pytest.raises(ValueError, match="PUBLISHED"):
            await store.upsert_documents(
                1,
                [
                    {
                        "document_id": "legacy",
                        "title": "未审核知识",
                        "content": "不得进入面向用户的医学索引",
                        "source_uri": "https://example.org/legacy",
                        "metadata": {"governance_status": "UNREVIEWED"},
                    }
                ],
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_qdrant_store_indexes_catalog_tier_and_keeps_its_label() -> None:
    """Encyclopedia mode: the catalog is indexed, tagged by trust tier."""
    client = AsyncQdrantClient(":memory:")
    store = QdrantKnowledgeStore(
        client, "knowledge", DeterministicHashEmbedding(64), 64
    )
    try:
        await store.ensure_collection()
        await store.upsert_documents(
            1,
            [
                {
                    "document_id": "Disease:目录疾病",
                    "title": "目录疾病",
                    "content": "疾病名称：目录疾病\n常见症状线索：目录症状",
                    "source_uri": "https://github.com/nuolade/disease-kb",
                    "metadata": {"governance_status": "LEGACY_UNREVIEWED"},
                }
            ],
        )
        points, _ = await client.scroll("knowledge", limit=10, with_payload=True)
        assert len(points) == 1
        assert points[0].payload["governance_status"] == "LEGACY_UNREVIEWED"

        # An HTTPS source is still mandatory for every tier.
        with pytest.raises(ValueError, match="HTTPS"):
            await store.upsert_documents(
                1,
                [
                    {
                        "document_id": "Disease:无来源",
                        "title": "无来源",
                        "content": "疾病名称：无来源",
                        "source_uri": "",
                        "metadata": {"governance_status": "LEGACY_UNREVIEWED"},
                    }
                ],
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_replace_documents_removes_retired_tenant_points() -> None:
    client = AsyncQdrantClient(":memory:")
    embedding = DeterministicHashEmbedding(64)
    store = QdrantKnowledgeStore(client, "knowledge", embedding, 64)
    retriever = QdrantVectorRetriever(client, "knowledge", embedding)
    published = {
        "source_uri": "https://example.org/source",
        "metadata": {"governance_status": "PUBLISHED"},
    }
    try:
        await store.ensure_collection()
        await store.replace_documents(
            1,
            [
                {
                    **published,
                    "document_id": "old",
                    "title": "旧知识",
                    "content": "旧版糖尿病知识",
                }
            ],
        )
        await store.replace_documents(
            1,
            [
                {
                    **published,
                    "document_id": "new",
                    "title": "新知识",
                    "content": "新版糖尿病知识",
                }
            ],
        )

        results = await retriever.search("糖尿病知识", tenant_id=1, top_k=10)

        assert [result.document_id for result in results] == ["new"]
    finally:
        await client.close()


class StaticRetriever:
    def __init__(self, result: list[RetrievalCandidate] | Exception):
        self.result = result

    async def search(self, query: str, tenant_id: int, top_k: int):
        del query, tenant_id, top_k
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.asyncio
async def test_hybrid_retrieval_applies_versioned_governance_exclusions() -> None:
    hybrid = HybridRetriever(
        StaticRetriever(
            [
                candidate(
                    "Disease:口腔干燥综合征",
                    "graph",
                    1.0,
                    title="口腔干燥综合征",
                ),
                candidate("Disease:腹泻", "graph", 1.0, title="腹泻"),
            ]
        ),
        StaticRetriever([]),
    )

    result = await hybrid.search(
        "腹泻和口腔干燥综合征",
        tenant_id=1,
        top_k=5,
    )

    assert [item.document_id for item in result.items] == ["Disease:腹泻"]
    assert "口腔干燥综合征" not in result.context


@pytest.mark.asyncio
async def test_hybrid_retrieval_degrades_when_one_source_fails() -> None:
    hybrid = HybridRetriever(
        StaticRetriever(RuntimeError("neo4j down")),
        StaticRetriever([candidate("Risk:1", "vector", 0.9)]),
    )

    result = await hybrid.search("delivery risk", tenant_id=1, top_k=5)

    assert result.degraded_sources == ["graph"]
    assert result.items[0].citation_id == "K1"
    assert "[K1]" in result.context


@pytest.mark.asyncio
async def test_hybrid_retrieval_fails_closed_without_any_source() -> None:
    hybrid = HybridRetriever(
        StaticRetriever(RuntimeError("neo4j down")),
        StaticRetriever(RuntimeError("qdrant down")),
    )

    with pytest.raises(AgentError, match="Both graph and vector") as captured:
        await hybrid.search("delivery risk", tenant_id=1, top_k=5)

    assert captured.value.status_code == 503


class CapturingKnowledgeRetriever:
    def __init__(self) -> None:
        self.tenant_id: int | None = None

    async def search(self, query: str, tenant_id: int, top_k: int):
        self.tenant_id = tenant_id
        return await HybridRetriever(
            StaticRetriever([candidate("Customer:1", "graph", 1.0)]),
            StaticRetriever([]),
        ).search(query, tenant_id, top_k)


@pytest.mark.asyncio
async def test_knowledge_tool_takes_tenant_only_from_verified_runtime() -> None:
    knowledge = CapturingKnowledgeRetriever()
    registry = ToolRegistry(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        knowledge,  # type: ignore[arg-type]
    )
    definition, arguments = registry.validate(
        "search_knowledge", {"query": "customer risk", "top_k": 3}
    )
    runtime = RequestRuntime(
        "Bearer secret",
        "trace-knowledge-001",
        uuid4(),
        user_id=1001,
        tenant_id=77,
    )

    result = await registry.execute(
        definition,
        arguments.model_dump(mode="json", by_alias=False),
        runtime,
    )

    assert knowledge.tenant_id == 77
    assert result["items"][0]["documentId"] == "Customer:1"
