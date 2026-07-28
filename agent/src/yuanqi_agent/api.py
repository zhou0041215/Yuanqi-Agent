import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, File, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

from yuanqi_agent.config import Settings, get_settings
from yuanqi_agent.errors import AgentError
from yuanqi_agent.graph import build_agent_graph
from yuanqi_agent.java_client import JavaApiClient
from yuanqi_agent.models import (
    AgentRunRequest,
    ApprovalDecision,
    KnowledgeGraphOverviewLink,
    KnowledgeGraphOverviewNode,
    KnowledgeGraphOverviewResponse,
)
from yuanqi_agent.planner import HttpIntentPlanner, OllamaIntentPlanner
from yuanqi_agent.report_analysis import MAX_REPORT_BYTES, ReportAnalysis, analyze_report
from yuanqi_agent.retrieval.embedding import build_embedding_provider
from yuanqi_agent.retrieval.graph import Neo4jGraphRetriever
from yuanqi_agent.retrieval.hybrid import HybridRetriever
from yuanqi_agent.retrieval.vector import QdrantKnowledgeStore, QdrantVectorRetriever
from yuanqi_agent.runtime import RequestRuntime
from yuanqi_agent.sandbox.docker_runner import DockerSandbox
from yuanqi_agent.service import AgentService
from yuanqi_agent.tools import ToolRegistry

# Medical Cypher coalesces camelCase/snake_case property fallbacks; on a graph
# using one naming, Neo4j emits benign "property does not exist" notifications for
# the unused branch. Silence just those notification logs (they are not errors).
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


def create_app(settings: Settings | None = None, service: AgentService | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if service is not None:
            app.state.agent_service = service
            yield
            return

        checkpoint_path = resolved_settings.checkpoint_db_path.resolve()
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        async with (
            AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer,
            httpx.AsyncClient(
                base_url=str(resolved_settings.java_base_url).rstrip("/"),
                timeout=resolved_settings.request_timeout_seconds,
                trust_env=False,
            ) as client,
        ):
            java_client = JavaApiClient(client, resolved_settings.java_max_response_bytes)
            sandbox = DockerSandbox(resolved_settings)
            graph_driver = None
            qdrant_client = None
            embedding_client = None
            planner_client = None
            planner = None
            knowledge = None
            try:
                if resolved_settings.planner_api_url is not None:
                    planner_client = httpx.AsyncClient(
                        timeout=resolved_settings.planner_timeout_seconds,
                        trust_env=False,
                    )
                    planner_key = (
                        resolved_settings.planner_api_key.get_secret_value()
                        if resolved_settings.planner_api_key
                        else None
                    )
                    planner = HttpIntentPlanner(
                        planner_client,
                        str(resolved_settings.planner_api_url),
                        planner_key,
                        resolved_settings.planner_max_response_bytes,
                    )
                elif resolved_settings.planner_ollama_url is not None:
                    planner_client = httpx.AsyncClient(
                        timeout=resolved_settings.planner_timeout_seconds,
                        trust_env=False,
                    )
                    planner = OllamaIntentPlanner(
                        planner_client,
                        str(resolved_settings.planner_ollama_url),
                        resolved_settings.planner_ollama_model,
                        resolved_settings.planner_max_response_bytes,
                    )
                # Always create Neo4j driver for medical knowledge tools
                graph_driver = AsyncGraphDatabase.driver(
                    resolved_settings.neo4j_uri,
                    auth=(
                        resolved_settings.neo4j_username,
                        resolved_settings.neo4j_password,
                    ),
                )
                with suppress(Exception):
                    await graph_driver.verify_connectivity()
                if resolved_settings.graphrag_enabled:
                    qdrant_client = create_qdrant_client(resolved_settings)
                    # Shared factory keeps index-time and query-time embeddings
                    # in the same vector space (see index_medical_knowledge.py).
                    embedding, embedding_client = build_embedding_provider(
                        resolved_settings,
                        timeout_seconds=resolved_settings.graphrag_timeout_seconds,
                    )
                    store = QdrantKnowledgeStore(
                        qdrant_client,
                        resolved_settings.qdrant_collection,
                        embedding,
                        resolved_settings.embedding_dimensions,
                    )
                    await graph_driver.verify_connectivity()
                    await store.ensure_collection()
                    knowledge = HybridRetriever(
                        Neo4jGraphRetriever(graph_driver, resolved_settings.neo4j_database),
                        QdrantVectorRetriever(
                            qdrant_client,
                            resolved_settings.qdrant_collection,
                            embedding,
                        ),
                        rrf_k=resolved_settings.graphrag_rrf_k,
                        timeout_seconds=resolved_settings.graphrag_timeout_seconds,
                    )
                    app.state.knowledge_store = store
                registry = ToolRegistry(
                    java_client,
                    sandbox,
                    knowledge,
                    knowledge_top_k=resolved_settings.graphrag_top_k,
                    neo4j_driver=graph_driver,
                    neo4j_database=resolved_settings.neo4j_database,
                )
                graph = build_agent_graph(registry, checkpointer)
                app.state.tool_registry = registry
                app.state.neo4j_driver = graph_driver
                app.state.java_client = java_client
                app.state.agent_service = AgentService(
                    graph,
                    java_client,
                    planner=planner,
                    tool_registry=registry,
                )
                yield
            finally:
                if planner_client is not None:
                    await planner_client.aclose()
                if embedding_client is not None:
                    await embedding_client.aclose()
                if qdrant_client is not None:
                    await qdrant_client.close()
                if graph_driver is not None:
                    await graph_driver.close()

    app = FastAPI(
        title="YuanQi Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
        expose_headers=["X-Trace-Id"],
    )

    @app.exception_handler(AgentError)
    async def handle_agent_error(request: Request, exc: AgentError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "UP"}

    # ── Knowledge Graph API ─────────────────────────────────────────

    @app.get("/api/v1/kg/search")
    async def kg_search(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
        q: str = "",
        limit: int = 10,
    ) -> dict:
        """模糊搜索知识图谱实体"""
        await verify_java_user(request, authorization, trace_id)
        driver = getattr(request.app.state, "neo4j_driver", None)
        if driver is None:
            graph_driver = getattr(request.app.state, "_graph_driver", None)
            if graph_driver is not None:
                driver = graph_driver
        if driver is None:
            return {"results": []}
        async with driver.session(database=resolved_settings.neo4j_database) as session:
            result = await session.run(
                """
                MATCH (n)
                WHERE any(label IN labels(n) WHERE label IN
                  ['Disease','Symptom','Drug','Department','Exam','Food','Therapy'])
                AND (
                  (
                    toUpper(coalesce(n.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                    AND coalesce(n.sourceUri, '') STARTS WITH 'https://'
                  )
                  OR (
                    any(label IN labels(n) WHERE label IN
                      ['Disease','Symptom','Drug','Exam','Food','Therapy'])
                    AND n.catalogStatus = 'CATALOGED'
                  )
                  OR ('Department' IN labels(n) AND n.standard = true
                    AND n.catalogStatus = 'STANDARDIZED')
                )
                AND n.name CONTAINS $q
                RETURN labels(n)[0] AS type, n.name AS name,
                       CASE
                         WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED']
                           THEN COALESCE(n.summary, '')
                         ELSE COALESCE(n.catalogSummary, '')
                       END AS desc,
                       CASE
                         WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED'] THEN n.sourceUri
                         ELSE COALESCE(n.catalogSourceUri, n.sourceUri, '')
                       END AS sourceUri,
                       CASE
                         WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED'] THEN 'PUBLISHED'
                         WHEN 'Department' IN labels(n) THEN 'STANDARDIZED'
                         ELSE 'CATALOG_ONLY'
                       END AS knowledgeStatus
                ORDER BY CASE WHEN n.name = $q THEN 0 ELSE 1 END,
                         CASE WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED'] THEN 0 ELSE 1 END,
                         size(n.name),
                         n.name
                LIMIT $limit
                """,
                q=q, limit=limit,
            )
            records = await result.data()
        # Sanitize desc fields
        for r in records:
            if r.get("desc"):
                r["desc"] = r["desc"].replace("\n", " ").replace("\r", "").replace("\x00", "")[:500]
        return {"results": records}

    @app.get("/api/v1/kg/departments")
    async def kg_departments(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ) -> dict:
        """返回知识图谱内全部可浏览科室。"""
        await verify_java_user(request, authorization, trace_id)
        driver = getattr(request.app.state, "neo4j_driver", None)
        if driver is None:
            graph_driver = getattr(request.app.state, "_graph_driver", None)
            if graph_driver is not None:
                driver = graph_driver
        if driver is None:
            return {"departments": []}
        async with driver.session(database=resolved_settings.neo4j_database) as session:
            result = await session.run(
                """
                MATCH (department:Department)
                WHERE department.name IS NOT NULL AND department.name <> ''
                  AND department.standard = true
                  AND department.catalogStatus = 'STANDARDIZED'
                  AND coalesce(department.sourceUri, '') STARTS WITH 'https://'
                RETURN DISTINCT department.name AS name
                ORDER BY name
                LIMIT 100
                """
            )
            records = await result.data()
        return {"departments": [record["name"] for record in records]}

    @app.get("/api/v1/kg/overview", response_model=KnowledgeGraphOverviewResponse)
    async def kg_overview(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ) -> KnowledgeGraphOverviewResponse:
        """Return a bounded department-level scene for the knowledge graph overview."""
        await verify_java_user(request, authorization, trace_id)
        driver = getattr(request.app.state, "neo4j_driver", None)
        if driver is None:
            driver = getattr(request.app.state, "_graph_driver", None)
        if driver is None:
            return KnowledgeGraphOverviewResponse(nodes=[], links=[])

        async with driver.session(database=resolved_settings.neo4j_database) as session:
            result = await session.run(
                """
                MATCH (department:Department)
                WHERE department.name IS NOT NULL AND department.name <> ''
                  AND department.standard = true
                  AND department.catalogStatus = 'STANDARDIZED'
                  AND coalesce(department.sourceUri, '') STARTS WITH 'https://'
                OPTIONAL MATCH (d:Disease)-[rel:BELONGS_TO|ROUTED_TO]->(department)
                WHERE (
                    type(rel) = 'ROUTED_TO'
                    AND rel.evidenceLevel = 'REFERENCE_ONLY'
                    AND d.catalogStatus = 'CATALOGED'
                ) OR (
                    type(rel) = 'BELONGS_TO'
                    AND toUpper(coalesce(d.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                    AND coalesce(d.sourceUri, '') STARTS WITH 'https://'
                    AND coalesce(rel.sourceUri, '') STARTS WITH 'https://'
                    AND (coalesce(rel.reviewed, false) = true
                      OR toUpper(coalesce(rel.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED'])
                )
                WITH department,
                     count(DISTINCT d) AS disease_count,
                     count(DISTINCT CASE WHEN type(rel) = 'BELONGS_TO' THEN d END)
                       AS published_disease_count,
                     count(DISTINCT CASE WHEN type(rel) = 'ROUTED_TO' THEN d END)
                       AS reference_disease_count
                RETURN department.name AS name,
                       disease_count,
                       published_disease_count,
                       reference_disease_count
                ORDER BY disease_count DESC, name ASC
                LIMIT 48
                """
            )
            records = await result.data()

        department_nodes = [
            KnowledgeGraphOverviewNode(
                type="Department",
                name=record["name"],
                desc=f"覆盖 {record['disease_count']} 个已审核疾病",
                knowledge_status="STANDARDIZED",
                disease_count=record["disease_count"],
                published_disease_count=record["published_disease_count"],
                reference_disease_count=record["reference_disease_count"],
            )
            for record in records
        ]
        total_diseases = sum(node.disease_count for node in department_nodes)
        nodes = [
            KnowledgeGraphOverviewNode(
                type="KnowledgeHub",
                name="医学知识库",
                desc="按标准化科室聚合的受控知识总览。选择科室后再查看疾病与临床关系。",
                knowledge_status="PUBLISHED",
                disease_count=total_diseases,
            ),
            *department_nodes,
        ]
        links = [
            KnowledgeGraphOverviewLink(
                source="医学知识库",
                target=node.name,
                rel_type="HAS_DEPARTMENT",
                evidence="PUBLISHED",
            )
            for node in department_nodes
        ]
        return KnowledgeGraphOverviewResponse(nodes=nodes, links=links)

    @app.get("/api/v1/kg/graph")
    async def kg_graph(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
        name: str = "",
        depth: int = 1,
    ) -> dict:
        """查询实体的关系图谱"""
        await verify_java_user(request, authorization, trace_id)
        driver = getattr(request.app.state, "neo4j_driver", None)
        if driver is None:
            graph_driver = getattr(request.app.state, "_graph_driver", None)
            if graph_driver is not None:
                driver = graph_driver
        if driver is None:
            return {"nodes": [], "links": []}
        depth = min(max(depth, 1), 2)
        async with driver.session(database=resolved_settings.neo4j_database) as session:
            result = await session.run(
                f"""
                MATCH path = (start {{name: $name}})
                  -[:HAS_SYMPTOM|TREATED_BY|BELONGS_TO|COMPLICATION|REQUIRES_EXAM|ROUTED_TO
                    |HAS_THERAPY|RECOMMENDED_EAT|AVOID_EAT|RECOMMENDED_RECIPE*1..{depth}]-
                  (related)
                WHERE any(label IN labels(related) WHERE label IN
                  ['Disease','Symptom','Drug','Department','Exam','Food','Therapy'])
                  AND all(n IN nodes(path) WHERE
                    (
                      toUpper(coalesce(n.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                      AND coalesce(n.sourceUri, '') STARTS WITH 'https://'
                    )
                    OR (
                      any(label IN labels(n) WHERE label IN
                        ['Disease','Symptom','Drug','Exam','Food','Therapy'])
                      AND n.catalogStatus = 'CATALOGED'
                    )
                    OR ('Department' IN labels(n) AND n.standard = true))
                  AND all(r IN relationships(path) WHERE
                    (
                      (
                        type(r) = 'ROUTED_TO'
                        OR type(r) IN [
                          'HAS_SYMPTOM','TREATED_BY','REQUIRES_EXAM','COMPLICATION',
                          'HAS_THERAPY','RECOMMENDED_EAT','AVOID_EAT','RECOMMENDED_RECIPE'
                        ]
                      )
                      AND r.evidenceLevel = 'REFERENCE_ONLY'
                    )
                    OR (
                      (coalesce(r.reviewed, false) = true
                        OR toUpper(coalesce(r.reviewStatus, ''))
                          IN ['PUBLISHED', 'APPROVED'])
                      AND coalesce(r.sourceUri, '') STARTS WITH 'https://'
                    ))
                WITH start, nodes(path) AS ns, length(path) AS path_distance
                UNWIND ns AS n
                WITH start, n, min(path_distance) AS path_distance
                WITH n,
                     CASE WHEN n = start THEN 0 ELSE path_distance END AS distance,
                     labels(n)[0] AS label
                ORDER BY distance ASC,
                         CASE label
                           WHEN 'Symptom' THEN 0
                           WHEN 'Drug' THEN 1
                           WHEN 'Exam' THEN 2
                           WHEN 'Department' THEN 3
                           WHEN 'Disease' THEN 4
                           ELSE 5
                         END,
                         n.name ASC
                RETURN label AS type, n.name AS name,
                       CASE
                         WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED']
                           THEN COALESCE(n.summary, '')
                         ELSE COALESCE(n.catalogSummary, '')
                       END AS desc,
                       CASE
                         WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED'] THEN n.sourceUri
                         ELSE COALESCE(n.catalogSourceUri, n.sourceUri, '')
                       END AS sourceUri,
                       CASE
                         WHEN toUpper(coalesce(n.reviewStatus, ''))
                           IN ['PUBLISHED', 'APPROVED'] THEN 'PUBLISHED'
                         WHEN 'Department' IN labels(n) THEN 'STANDARDIZED'
                         ELSE 'CATALOG_ONLY'
                       END AS knowledgeStatus
                LIMIT 200
                """,
                name=name,
            )
            node_records = await result.data()
            node_names = [record["name"] for record in node_records if record.get("name")]

            result = await session.run(
                """
                MATCH (source_node)-[rel]->(target_node)
                WHERE source_node.name IN $node_names
                  AND target_node.name IN $node_names
                  AND type(rel) IN [
                    'HAS_SYMPTOM','TREATED_BY','BELONGS_TO',
                    'COMPLICATION','REQUIRES_EXAM','ROUTED_TO',
                    'HAS_THERAPY','RECOMMENDED_EAT','AVOID_EAT','RECOMMENDED_RECIPE'
                  ]
                  AND (
                    (
                      (
                        type(rel) = 'ROUTED_TO'
                        OR type(rel) IN [
                          'HAS_SYMPTOM','TREATED_BY','REQUIRES_EXAM','COMPLICATION',
                          'HAS_THERAPY','RECOMMENDED_EAT','AVOID_EAT','RECOMMENDED_RECIPE'
                        ]
                      )
                      AND rel.evidenceLevel = 'REFERENCE_ONLY'
                    )
                    OR (
                      toUpper(coalesce(source_node.reviewStatus, ''))
                        IN ['PUBLISHED', 'APPROVED']
                      AND toUpper(coalesce(target_node.reviewStatus, ''))
                        IN ['PUBLISHED', 'APPROVED']
                      AND coalesce(source_node.sourceUri, '') STARTS WITH 'https://'
                      AND coalesce(target_node.sourceUri, '') STARTS WITH 'https://'
                      AND coalesce(rel.sourceUri, '') STARTS WITH 'https://'
                      AND (coalesce(rel.reviewed, false) = true
                        OR toUpper(coalesce(rel.reviewStatus, ''))
                          IN ['PUBLISHED', 'APPROVED'])
                    )
                  )
                WITH DISTINCT source_node.name AS source,
                     target_node.name AS target,
                     type(rel) AS rel_type,
                     CASE
                       WHEN rel.evidenceLevel = 'REFERENCE_ONLY'
                         THEN 'REFERENCE_ONLY'
                       ELSE 'PUBLISHED'
                     END AS evidence
                ORDER BY CASE WHEN source = $name OR target = $name THEN 0 ELSE 1 END,
                         rel_type,
                         source,
                         target
                RETURN source, target, rel_type, evidence
                LIMIT 500
                """,
                node_names=node_names,
                name=name,
            )
            link_records = await result.data()

        # Sanitize desc fields
        for r in node_records:
            if r.get("desc"):
                r["desc"] = r["desc"].replace("\n", " ").replace("\r", "").replace("\x00", "")[:300]

        return {"nodes": node_records, "links": link_records}

    @app.get("/api/v1/kg/department")
    async def kg_department(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
        name: str = "",
        limit: int = 200,
    ) -> dict:
        """加载某个科室下的所有疾病及其直接关联"""
        await verify_java_user(request, authorization, trace_id)
        driver = getattr(request.app.state, "neo4j_driver", None)
        if driver is None:
            return {"nodes": [], "links": []}
        node_limit = min(max(limit, 50), 400)
        async with driver.session(database=resolved_settings.neo4j_database) as session:
            result = await session.run(
                """
                MATCH (d:Disease)-[department_rel:BELONGS_TO|ROUTED_TO]->
                  (k:Department {name: $name})
                WHERE (
                    type(department_rel) = 'ROUTED_TO'
                    AND department_rel.evidenceLevel = 'REFERENCE_ONLY'
                    AND d.catalogStatus = 'CATALOGED'
                    AND k.standard = true
                  )
                  OR (
                    type(department_rel) = 'BELONGS_TO'
                    AND toUpper(coalesce(d.reviewStatus, ''))
                      IN ['PUBLISHED', 'APPROVED']
                    AND toUpper(coalesce(k.reviewStatus, ''))
                      IN ['PUBLISHED', 'APPROVED']
                    AND coalesce(d.sourceUri, '') STARTS WITH 'https://'
                    AND coalesce(k.sourceUri, '') STARTS WITH 'https://'
                    AND coalesce(department_rel.sourceUri, '') STARTS WITH 'https://'
                    AND (coalesce(department_rel.reviewed, false) = true
                      OR toUpper(coalesce(department_rel.reviewStatus, ''))
                        IN ['PUBLISHED', 'APPROVED'])
                  )
                RETURN DISTINCT d.name AS name,
                  COALESCE(d.summary, '') AS desc,
                  CASE WHEN type(department_rel) = 'BELONGS_TO'
                    THEN 'PUBLISHED' ELSE 'REFERENCE_ONLY' END AS evidence
                ORDER BY CASE WHEN evidence = 'PUBLISHED' THEN 0 ELSE 1 END,
                         name
                LIMIT $limit
                """,
                name=name, limit=node_limit,
            )
            records = await result.data()

        nodes_map: dict[str, dict] = {
            name: {
                "type": "Department",
                "name": name,
                "desc": "标准化就诊科室",
                "knowledgeStatus": "STANDARDIZED",
            }
        }
        links: list[dict] = []
        for r in records:
            disease_name = r.get("name")
            if disease_name and disease_name not in nodes_map and len(nodes_map) < node_limit:
                nodes_map[disease_name] = {
                    "type": "Disease",
                    "name": disease_name,
                    "desc": (r.get("desc") or "")[:300],
                    "knowledgeStatus": r.get("evidence", "REFERENCE_ONLY"),
                }
            if disease_name in nodes_map:
                links.append(
                    {
                        "source": disease_name,
                        "target": name,
                        "rel_type": (
                            "BELONGS_TO"
                            if r.get("evidence") == "PUBLISHED"
                            else "ROUTED_TO"
                        ),
                        "evidence": r.get("evidence", "REFERENCE_ONLY"),
                    }
                )

        # Deduplicate links
        seen = set()
        unique_links = []
        for link in links:
            if len(unique_links) >= node_limit * 3:
                break
            key = f"{link['source']}|||{link['target']}|||{link['rel_type']}"
            if key not in seen:
                seen.add(key)
                unique_links.append(link)

        return {"nodes": list(nodes_map.values()), "links": unique_links}

    @app.get("/api/v1/agent/tools")
    async def tools(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ):
        registry = getattr(request.app.state, "tool_registry", None)
        java_client = getattr(request.app.state, "java_client", None)
        if registry is None or java_client is None:
            return []
        user = await java_client.get_user_context(authorization, trace_id)
        return registry.describe(set(user.permissions))

    @app.post("/api/v1/kg/index/rebuild")
    async def rebuild_knowledge_index(
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ):
        java_client = getattr(request.app.state, "java_client", None)
        store = getattr(request.app.state, "knowledge_store", None)
        if java_client is None or store is None:
            raise AgentError(
                "KNOWLEDGE_INDEX_UNAVAILABLE",
                "GraphRAG indexing is not enabled",
                status_code=503,
            )
        user = await java_client.get_user_context(authorization, trace_id)
        if "knowledge:index" not in user.permissions:
            raise AgentError("FORBIDDEN", "Knowledge indexing permission is required", 403)
        runtime = RequestRuntime(
            authorization=authorization,
            trace_id=trace_id,
            thread_id=uuid.uuid4(),
        )
        version_name = uuid.uuid4().hex[:12]
        index_record = await java_client.request(
            "POST",
            "/api/v1/knowledge-index-versions",
            runtime=runtime,
            json={
                "versionName": version_name,
                "collectionName": resolved_settings.qdrant_collection,
            },
            write=True,
            idempotency_key=f"knowledge-index-{version_name}",
        )
        try:
            published = await java_client.request(
                "GET",
                "/api/v1/knowledge-documents/published",
                runtime=runtime,
            )
            documents = [
                {
                    "document_id": item["documentKey"],
                    # Match Neo4j's canonical entity key so RRF merges graph
                    # and vector evidence for the same medical entity.
                    "entity_key": f"{item['entityType']}:{item['title']}",
                    "title": item["title"],
                    "content": item["content"],
                    "source_uri": item.get("sourceUri") or "",
                    "metadata": {
                        "entity_type": item["entityType"],
                        "knowledge_version": item["knowledgeVersion"],
                        "governance_status": item["status"],
                        "published_at": item.get("publishedAt") or "",
                    },
                }
                for item in published
            ]
            # Replace the tenant corpus instead of appending to it. This removes
            # retired and legacy-unreviewed points from the active search surface.
            await store.replace_documents(user.tenant_id, documents)
            await java_client.request(
                "PATCH",
                f"/api/v1/knowledge-index-versions/{index_record['id']}/complete",
                runtime=runtime,
                params={"documentCount": len(documents)},
                write=True,
                idempotency_key=f"knowledge-index-complete-{version_name}",
            )
        except Exception:
            await java_client.request(
                "PATCH",
                f"/api/v1/knowledge-index-versions/{index_record['id']}/fail",
                runtime=runtime,
                params={"error": "Published corpus validation or indexing failed"},
                write=True,
                idempotency_key=f"knowledge-index-fail-{version_name}",
            )
            raise
        return {
            "version": version_name,
            "documentCount": len(documents),
            "status": "ACTIVE",
        }

    @app.post("/api/v1/medical-reports/analyze", response_model=ReportAnalysis)
    async def analyze_medical_report(
        request: Request,
        file: Annotated[UploadFile, File(description="PDF、TXT、CSV、JPG 或 PNG 检查报告")],
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ) -> ReportAnalysis:
        """Extract report facts without persisting the uploaded medical document."""
        await verify_java_user(request, authorization, trace_id)
        content = await file.read(MAX_REPORT_BYTES + 1)
        try:
            return analyze_report(
                file.filename or "medical-report",
                file.content_type or "application/octet-stream",
                content,
            )
        finally:
            await file.close()

    @app.post("/api/v1/agent/stream")
    async def start_stream(
        body: AgentRunRequest,
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ) -> StreamingResponse:
        service = get_service(request)
        iterator = service.run_loop(body, authorization, trace_id)
        return sse_response(iterator)

    @app.post("/api/v1/agent/threads/{thread_id}/resume/stream")
    async def resume_stream(
        thread_id: UUID,
        body: ApprovalDecision,
        request: Request,
        authorization: Annotated[str, Depends(require_bearer)],
        trace_id: Annotated[str, Depends(require_trace_id)],
    ) -> StreamingResponse:
        service = get_service(request)
        iterator = service.resume_loop(thread_id, body, authorization, trace_id)
        return sse_response(iterator)

    return app


def create_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    """Create the internal vector client without inheriting host proxy settings."""
    return AsyncQdrantClient(
        url=str(settings.qdrant_url),
        api_key=settings.qdrant_api_key,
        timeout=int(settings.graphrag_timeout_seconds),
        trust_env=False,
    )


def get_service(request: Request) -> AgentService:
    return request.app.state.agent_service


async def verify_java_user(
    request: Request,
    authorization: str,
    trace_id: str,
) -> None:
    """Treat Java as the trust root for every browser-facing graph request."""
    java_client = getattr(request.app.state, "java_client", None)
    if java_client is None:
        raise AgentError(
            "AUTH_SERVICE_UNAVAILABLE",
            "Java authentication service is unavailable",
            status_code=503,
        )
    await java_client.get_user_context(authorization, trace_id)


def require_bearer(authorization: Annotated[str | None, Header()] = None) -> str:
    if (
        authorization is None
        or len(authorization) > 8_192
        or not authorization.startswith("Bearer ")
        or not authorization[7:].strip()
    ):
        raise AgentError("UNAUTHORIZED", "A bearer token is required", status_code=401)
    return authorization


def require_trace_id(x_trace_id: Annotated[str | None, Header()] = None) -> str:
    if x_trace_id and re.fullmatch(r"[A-Za-z0-9-]{8,64}", x_trace_id):
        return x_trace_id
    return uuid.uuid4().hex


def sse_response(iterator: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        iterator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
