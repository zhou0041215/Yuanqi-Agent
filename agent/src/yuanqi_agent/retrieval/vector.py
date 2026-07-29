from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient, models

from yuanqi_agent.retrieval.embedding import EmbeddingProvider
from yuanqi_agent.retrieval.models import RetrievalCandidate
from yuanqi_agent.trusted_medical_knowledge import get_knowledge_governance_policy

# Reviewed corpus and open medical catalog. The tier travels with each point so
# the answer layer can cite the first and label the second as reference-only.
_INDEXABLE_STATUSES = frozenset({"PUBLISHED", "LEGACY_UNREVIEWED"})


class QdrantVectorRetriever:
    def __init__(
        self,
        client: AsyncQdrantClient,
        collection: str,
        embedding: EmbeddingProvider,
    ):
        self._client = client
        self._collection = collection
        self._embedding = embedding

    async def search(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        vector = await self._embedding.embed_query(query)
        excluded_entity_keys = [
            item.entity_key
            for item in get_knowledge_governance_policy().excluded_entities
        ]
        response = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            # Encyclopedia mode: both trust tiers are searchable. The tier rides
            # along in the payload so the answer layer labels each result.
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="governance_status",
                        match=models.MatchAny(any=sorted(_INDEXABLE_STATUSES)),
                    ),
                ],
                must_not=[
                    models.FieldCondition(
                        key="entity_key",
                        match=models.MatchAny(any=excluded_entity_keys),
                    )
                ],
            ),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        candidates: list[RetrievalCandidate] = []
        for point in response.points:
            payload = dict(point.payload or {})
            document_id = str(payload.get("entity_key") or payload.get("document_id") or point.id)
            title = str(payload.get("title") or "Knowledge document").strip()
            content = str(payload.get("content") or "").strip()
            if not content:
                continue
            candidates.append(
                RetrievalCandidate(
                    document_id=document_id,
                    title=title,
                    content=content,
                    source="vector",
                    raw_score=float(point.score),
                    metadata=self._safe_metadata(payload),
                )
            )
        return candidates

    @staticmethod
    def _safe_metadata(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if key != "content" and isinstance(value, str | int | float | bool)
        }


class QdrantKnowledgeStore:
    def __init__(
        self,
        client: AsyncQdrantClient,
        collection: str,
        embedding: EmbeddingProvider,
        dimensions: int,
    ):
        self._client = client
        self._collection = collection
        self._embedding = embedding
        self._dimensions = dimensions

    async def ensure_collection(self) -> None:
        if not await self._client.collection_exists(self._collection):
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=self._dimensions,
                    distance=models.Distance.COSINE,
                ),
            )
        info = await self._client.get_collection(self._collection)
        payload_schema = dict(info.payload_schema or {})
        if "governance_status" not in payload_schema:
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="governance_status",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        if "entity_key" not in payload_schema:
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="entity_key",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    async def upsert_documents(self, documents: list[dict[str, Any]]) -> None:
        texts = [self._document_text(document) for document in documents]
        vectors = await self._embedding.embed_documents(texts)
        points: list[models.PointStruct] = []
        for document, content, vector in zip(documents, texts, vectors, strict=True):
            document_id = str(document["document_id"])
            metadata = {
                key: value
                for key, value in dict(document.get("metadata") or {}).items()
                if isinstance(value, str | int | float | bool)
            }
            # Encyclopedia mode: the catalog is indexed alongside reviewed
            # documents, distinguished by governance_status so the answer layer
            # can label each tier. Both tiers still require a real HTTPS source
            # (the catalog carries its upstream dataset URL).
            status = metadata.get("governance_status")
            if status not in _INDEXABLE_STATUSES:
                raise ValueError(
                    "knowledge documents must be PUBLISHED or LEGACY_UNREVIEWED to be indexed"
                )
            source_uri = str(document.get("source_uri") or "").strip()
            if not source_uri.startswith("https://"):
                raise ValueError("knowledge documents require an HTTPS source")
            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"yuanqi:{document_id}")),
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "entity_key": document.get("entity_key", document_id),
                        "title": str(document.get("title") or "Knowledge document"),
                        "content": content,
                        "source_uri": source_uri,
                        **metadata,
                    },
                )
            )
        if points:
            await self._client.upsert(
                collection_name=self._collection,
                points=points,
                wait=True,
            )

    async def replace_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """Replace the single institution's active corpus after validating it.

        Validation and embedding happen before deletion, so malformed published
        documents cannot erase the currently active corpus.
        """
        for document in documents:
            self._document_text(document)
            metadata = dict(document.get("metadata") or {})
            if metadata.get("governance_status") not in _INDEXABLE_STATUSES:
                raise ValueError(
                    "knowledge documents must be PUBLISHED or LEGACY_UNREVIEWED to be indexed"
                )
            if not str(document.get("source_uri") or "").startswith("https://"):
                raise ValueError("knowledge documents require an HTTPS source")

        # Precompute embeddings before changing active state.
        texts = [self._document_text(document) for document in documents]
        vectors = await self._embedding.embed_documents(texts) if texts else []
        points: list[models.PointStruct] = []
        for document, content, vector in zip(documents, texts, vectors, strict=True):
            document_id = str(document["document_id"])
            metadata = {
                key: value
                for key, value in dict(document.get("metadata") or {}).items()
                if isinstance(value, str | int | float | bool)
            }
            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"yuanqi:{document_id}")),
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "entity_key": document.get("entity_key", document_id),
                        "title": str(document.get("title") or "Knowledge document"),
                        "content": content,
                        "source_uri": str(document["source_uri"]),
                        **metadata,
                    },
                )
            )

        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[])
            ),
            wait=True,
        )
        if points:
            await self._client.upsert(
                collection_name=self._collection,
                points=points,
                wait=True,
            )

    @staticmethod
    def _document_text(document: dict[str, Any]) -> str:
        content = str(document.get("content") or "").strip()
        if not content:
            raise ValueError("each document requires non-blank content")
        if len(content) > 20_000:
            raise ValueError("document content exceeds 20,000 characters")
        return content
