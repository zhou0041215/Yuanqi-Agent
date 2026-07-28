"""Build canonical Disease documents from Neo4j and index them in Qdrant."""

from __future__ import annotations

import argparse
import asyncio
import logging

from neo4j import GraphDatabase
from qdrant_client import AsyncQdrantClient

from yuanqi_agent.config import get_settings
from yuanqi_agent.retrieval.embedding import build_embedding_provider
from yuanqi_agent.retrieval.medical_documents import (
    MEDICAL_DOCUMENT_QUERY,
    build_disease_document,
)
from yuanqi_agent.retrieval.vector import QdrantKnowledgeStore

# The medical Cypher coalesces camelCase/snake_case property fallbacks; on a graph
# using one naming, Neo4j emits benign "property does not exist" notifications for
# the unused branch. Silence just those notification logs (they are not errors).
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


def load_documents(limit: int | None) -> list[dict]:
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(MEDICAL_DOCUMENT_QUERY)
            records = [record.data() for record in result]
    finally:
        driver.close()
    if limit is not None:
        records = records[:limit]
    return [build_disease_document(record) for record in records]


async def index_documents(tenant_id: int, documents: list[dict], batch_size: int) -> None:
    settings = get_settings()
    client = AsyncQdrantClient(
        url=str(settings.qdrant_url),
        api_key=settings.qdrant_api_key,
        timeout=int(settings.graphrag_timeout_seconds),
        trust_env=False,
    )
    # Use the SAME embedding backend the query side uses (see api.py); index-time
    # and query-time vectors must live in one space or vector recall degrades.
    embedding, embedding_client = build_embedding_provider(
        settings, timeout_seconds=settings.graphrag_timeout_seconds
    )
    store = QdrantKnowledgeStore(
        client,
        settings.qdrant_collection,
        embedding,
        settings.embedding_dimensions,
    )
    try:
        await store.ensure_collection()
        for offset in range(0, len(documents), batch_size):
            batch = documents[offset : offset + batch_size]
            await store.upsert_documents(tenant_id, batch)
            print(f"indexed {min(offset + len(batch), len(documents))}/{len(documents)}")
    finally:
        if embedding_client is not None:
            await embedding_client.aclose()
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()
    if args.tenant_id <= 0:
        parser.error("--tenant-id must be positive")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if not 1 <= args.batch_size <= 256:
        parser.error("--batch-size must be between 1 and 256")

    documents = load_documents(args.limit)
    print(f"built {len(documents)} medical documents")
    asyncio.run(index_documents(args.tenant_id, documents, args.batch_size))


if __name__ == "__main__":
    main()
