import hashlib
import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

import orjson
from pydantic import Field, ValidationError, field_validator

from yuanqi_agent.errors import AgentError
from yuanqi_agent.java_client import JavaApiClient
from yuanqi_agent.medical_taxonomy import canonical_department
from yuanqi_agent.models import PendingTool, StrictModel
from yuanqi_agent.retrieval.hybrid import HybridRetriever
from yuanqi_agent.runtime import RequestRuntime
from yuanqi_agent.sandbox.docker_runner import DockerSandbox

LOGGER = logging.getLogger(__name__)


class ToolAccess(StrEnum):
    READ = "read"
    WRITE = "write"


class AnalyzePrescriptionSnapshotArgs(StrictModel):
    from_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    department_ids: list[int] = Field(default_factory=list, max_length=50)
    maximum_rows: int = Field(default=5_000, ge=1, le=10_000)
    code: str = Field(
        min_length=1,
        max_length=50_000,
        description=(
            "Pandas analysis code. input_data contains only prescription_date, total_amount, "
            "status and department_id. Assign JSON-compatible output to result and optional "
            "ECharts-compatible data to chart."
        ),
    )


class PrescriptionSnapshotRow(StrictModel):
    prescription_date: str
    total_amount: float
    status: str
    department_id: int


class DatasetColumn(StrictModel):
    name: str
    type: str
    nullable: bool
    description: str


class PrescriptionDatasetSchema(StrictModel):
    dataset: str
    schema_version: str
    maximum_rows: int = Field(ge=1, le=10_000)
    columns: list[DatasetColumn]


class PrescriptionAnalysisSnapshot(StrictModel):
    schema_version: str
    row_count: int = Field(ge=0, le=10_000)
    truncated: bool
    rows: list[PrescriptionSnapshotRow] = Field(max_length=10_000)


class SearchKnowledgeArgs(StrictModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int | None = Field(default=None, ge=1, le=20)


# ── 医学知识图谱工具 Args ──────────────────────────────────────────────

class SearchDiseaseArgs(StrictModel):
    name: str = Field(min_length=1, max_length=200, description="Disease name.")


class SearchSymptomArgs(StrictModel):
    symptom: str = Field(min_length=1, max_length=200, description="Symptom name.")


class SearchDrugArgs(StrictModel):
    name: str = Field(min_length=1, max_length=200, description="Drug name.")


class SearchDepartmentArgs(StrictModel):
    name: str | None = Field(default=None, max_length=100, description="Department name.")


class ListPatientsArgs(StrictModel):
    keyword: str | None = Field(
        default=None, max_length=200,
        description="Search by name or patient number.",
    )
    page: int = Field(default=0, ge=0)
    size: int = Field(default=20, ge=1, le=100)


class GetPatientArgs(StrictModel):
    patient_id: int = Field(gt=0)


class CreatePatientArgs(StrictModel):
    name: str = Field(min_length=1, max_length=200, description="Patient name.")
    gender: Literal["MALE", "FEMALE", "UNKNOWN"] = Field(default="UNKNOWN")
    birth_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    phone: str | None = Field(default=None, max_length=32)
    id_card: str | None = Field(default=None, max_length=32)
    blood_type: str | None = Field(default=None, max_length=10)
    allergy_history: str | None = Field(default=None, max_length=2000)
    medical_history: str | None = Field(default=None, max_length=2000)


class CreatePrescriptionArgs(StrictModel):
    patient_id: int = Field(gt=0, description="患者ID")
    record_id: int | None = Field(default=None, gt=0, description="关联病历ID")
    diagnosis: str = Field(min_length=1, max_length=2000, description="诊断结果")
    drugs: str = Field(
        min_length=1,
        max_length=5000,
        description="药品名称、规格、剂量和用法文本",
    )
    total_amount: float = Field(gt=0, description="Total prescription amount.")
    notes: str | None = Field(default=None, max_length=2000)


class ListMedicalRecordsArgs(StrictModel):
    keyword: str | None = Field(default=None, max_length=200)
    page: int = Field(default=0, ge=0)
    size: int = Field(default=20, ge=1, le=100)


class GetMedicalRecordArgs(StrictModel):
    record_id: int = Field(gt=0)


class CreateMedicalRecordArgs(StrictModel):
    patient_id: int = Field(gt=0)
    visit_date: str = Field(description="就诊时间，ISO-8601 格式")
    chief_complaint: str | None = Field(default=None, max_length=10_000)
    diagnosis: str | None = Field(default=None, max_length=10_000)
    treatment_plan: str | None = Field(default=None, max_length=10_000)
    notes: str | None = Field(default=None, max_length=10_000)

    @field_validator("visit_date")
    @classmethod
    def normalize_visit_date(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError("visit_date must be an ISO-8601 local date or date-time") from exc
        if parsed.tzinfo is not None:
            raise ValueError("visit_date must not include a timezone offset")
        return parsed.isoformat(timespec="seconds")


class ListPrescriptionsArgs(StrictModel):
    keyword: str | None = Field(default=None, max_length=200)
    page: int = Field(default=0, ge=0)
    size: int = Field(default=20, ge=1, le=100)


class GetPrescriptionArgs(StrictModel):
    prescription_id: int = Field(gt=0)


ToolExecutor = Callable[[StrictModel, RequestRuntime], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    access: ToolAccess
    risk_level: Literal["low", "medium", "high", "critical"]
    required_permission: str | None
    args_model: type[StrictModel]
    executor: ToolExecutor
    planner_hidden_fields: frozenset[str] = frozenset()


class ToolRegistry:
    def __init__(
        self,
        java_client: JavaApiClient,
        sandbox: DockerSandbox,
        knowledge_retriever: HybridRetriever | None = None,
        knowledge_top_k: int = 8,
        neo4j_driver: Any = None,
        neo4j_database: str = "neo4j",
    ):
        self._java = java_client
        self._sandbox = sandbox
        self._knowledge = knowledge_retriever
        self._knowledge_top_k = knowledge_top_k
        self._neo4j = neo4j_driver
        self._neo4j_db = neo4j_database
        definitions = []
        if knowledge_retriever is not None:
            definitions.append(
                ToolDefinition(
                    "search_knowledge",
                    "Search the medical knowledge graph for diseases, symptoms, drugs, departments, examinations, and their relationships.",
                    ToolAccess.READ,
                    "low",
                    None,
                    SearchKnowledgeArgs,
                    self._search_knowledge,
                )
            )

        # ── 医学知识图谱工具 ──────────────────────────────────────────
        definitions.extend([
            ToolDefinition(
                "list_patients",
                "Medical operation.",
                ToolAccess.READ,
                "low",
                "patient:read",
                ListPatientsArgs,
                self._list_patients,
            ),
            ToolDefinition(
                "get_patient",
                "Medical operation.",
                ToolAccess.READ,
                "low",
                "patient:read",
                GetPatientArgs,
                self._get_patient,
            ),
            ToolDefinition(
                "create_patient",
                "创建患者",
                ToolAccess.WRITE,
                "high",
                "patient:write",
                CreatePatientArgs,
                self._create_patient,
            ),
            ToolDefinition(
                "create_prescription",
                "为当前患者工作台中已验证的患者创建处方；患者身份由系统绑定",
                ToolAccess.WRITE,
                "critical",
                "prescription:write",
                CreatePrescriptionArgs,
                self._create_prescription,
                frozenset({"patientId"}),
            ),
            ToolDefinition(
                "list_medical_records",
                "Medical operation.",
                ToolAccess.READ,
                "low",
                "medical-record:read",
                ListMedicalRecordsArgs,
                self._list_medical_records,
            ),
            ToolDefinition(
                "get_medical_record",
                "Medical operation.",
                ToolAccess.READ,
                "low",
                "medical-record:read",
                GetMedicalRecordArgs,
                self._get_medical_record,
            ),
            ToolDefinition(
                "create_medical_record",
                "为当前患者工作台中已验证的患者创建病历；患者身份由系统绑定",
                ToolAccess.WRITE,
                "high",
                "medical-record:write",
                CreateMedicalRecordArgs,
                self._create_medical_record,
                frozenset({"patientId"}),
            ),
            ToolDefinition(
                "list_prescriptions",
                "Medical operation.",
                ToolAccess.READ,
                "low",
                "prescription:read",
                ListPrescriptionsArgs,
                self._list_prescriptions,
            ),
            ToolDefinition(
                "get_prescription",
                "Medical operation.",
                ToolAccess.READ,
                "low",
                "prescription:read",
                GetPrescriptionArgs,
                self._get_prescription,
            ),
            ToolDefinition(
                "analyze_prescription_snapshot",
                "Analyze a bounded, de-identified Java-authorized prescription snapshot in the no-network sandbox.",
                ToolAccess.READ,
                "medium",
                "prescription:read",
                AnalyzePrescriptionSnapshotArgs,
                self._analyze_prescription_snapshot,
            ),
        ])
        if neo4j_driver is not None:
            definitions.extend([
                ToolDefinition(
                    "search_disease",
                    "Medical operation.",
                    ToolAccess.READ,
                    "low",
                    None,
                    SearchDiseaseArgs,
                    self._search_disease,
                ),
                ToolDefinition(
                    "search_symptom",
                    "Medical operation.",
                    ToolAccess.READ,
                    "low",
                    None,
                    SearchSymptomArgs,
                    self._search_symptom,
                ),
                ToolDefinition(
                    "search_drug",
                    "Medical operation.",
                    ToolAccess.READ,
                    "low",
                    None,
                    SearchDrugArgs,
                    self._search_drug,
                ),
                ToolDefinition(
                    "search_department",
                    "Medical operation.",
                    ToolAccess.READ,
                    "low",
                    None,
                    SearchDepartmentArgs,
                    self._search_department,
                ),
            ])
        self._definitions = {definition.name: definition for definition in definitions}

    def validate(self, name: str, arguments: dict[str, Any]) -> tuple[ToolDefinition, StrictModel]:
        definition = self._definitions.get(name)
        if definition is None:
            raise AgentError("UNKNOWN_TOOL", f"Tool '{name}' is not registered", status_code=422)
        try:
            validated = definition.args_model.model_validate(arguments)
        except ValidationError as exc:
            raise AgentError(
                "INVALID_TOOL_ARGUMENTS",
                f"Arguments for tool '{name}' are invalid",
                status_code=422,
                details=exc.errors(include_url=False),
            ) from exc
        return definition, validated

    async def execute(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
        runtime: RequestRuntime,
    ) -> Any:
        _, validated = self.validate(definition.name, arguments)
        return await definition.executor(validated, runtime)

    async def audit(
        self,
        definition: ToolDefinition,
        runtime: RequestRuntime,
        *,
        phase: str,
        outcome: str,
        fingerprint: str | None = None,
    ) -> None:
        recorder = getattr(self._java, "record_agent_audit", None)
        if recorder is None:
            return
        await recorder(
            runtime=runtime,
            tool_name=definition.name,
            phase=phase,
            outcome=outcome,
            risk_level=definition.risk_level,
            fingerprint=fingerprint,
        )

    def pending_tool(self, definition: ToolDefinition, arguments: StrictModel) -> PendingTool:
        normalized = arguments.model_dump(mode="json", by_alias=False)
        canonical = orjson.dumps(
            {"name": definition.name, "arguments": normalized},
            option=orjson.OPT_SORT_KEYS,
        )
        return PendingTool(
            name=definition.name,
            arguments=normalized,
            action=definition.description,
            risk_level=definition.risk_level,
            fingerprint=hashlib.sha256(canonical).hexdigest(),
        )

    def describe(self, permissions: set[str] | None = None) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "access": definition.access.value,
                "riskLevel": definition.risk_level,
                "requiredPermission": definition.required_permission,
                "inputSchema": self._planner_schema(definition),
            }
            for definition in self._definitions.values()
            if permissions is None
            or definition.required_permission is None
            or definition.required_permission in permissions
        ]

    def _planner_schema(self, definition: ToolDefinition) -> dict[str, Any]:
        schema = deepcopy(definition.args_model.model_json_schema(by_alias=True))
        if not definition.planner_hidden_fields:
            return schema
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for field in definition.planner_hidden_fields:
                properties.pop(field, None)
        required = schema.get("required")
        if isinstance(required, list):
            schema["required"] = [
                field for field in required
                if field not in definition.planner_hidden_fields
            ]
        return schema

    # ── 医学实体识别 ────────────────────────────────────────────────────
    #
    # 早期版本用一份写死的 22 个病�?24 个症状清单做路由，图谱里其余
    # Resolve medical entities directly from the Neo4j catalog.
    _ENTITY_PRIORITY = ("Disease", "Drug", "Symptom", "Department")

    _ENTITY_RESOLUTION_QUERY = """
    UNWIND $labels AS label
    CALL (label) {
      MATCH (node)
      WHERE label IN labels(node)
        AND size(node.name) >= 2
        AND $message CONTAINS node.name
      RETURN node.name AS name, label AS entity_label
      ORDER BY size(node.name) DESC
      LIMIT 5
    }
    RETURN name, entity_label
    ORDER BY size(name) DESC
    LIMIT 20
    """.strip()

    # 同一条消息可能同时命中疾病和症状（“糖尿病会不会引起头晕”）。优�?    # 按实体名长度取最长匹配，长度相同时按这个顺序定夺主题�?    _ENTITY_PRIORITY: ClassVar[tuple[str, ...]] = ("Disease", "Drug", "Symptom", "Department")

    async def resolve_medical_entities(self, message: str) -> dict[str, list[str]]:
        """Find every catalog entity whose name literally appears in the message."""
        normalized = " ".join(str(message or "").split())
        if len(normalized) < 2 or self._neo4j is None:
            return {}
        try:
            async with self._neo4j.session(database=self._neo4j_db) as session:
                result = await session.run(
                    self._ENTITY_RESOLUTION_QUERY,
                    message=normalized,
                    labels=list(self._ENTITY_PRIORITY),
                )
                records = await result.data()
        except Exception:
            LOGGER.exception("Medical entity resolution failed")
            return {}

        matches: dict[str, list[str]] = {}
        for row in records:
            name = str(row.get("name") or "").strip()
            label = str(row.get("entity_label") or "").strip()
            if not name or not label:
                continue
            names = matches.setdefault(label, [])
            if any(name in existing for existing in names):
                continue
            names.append(name)
        return matches

    async def _analyze_prescription_snapshot(
        self, raw: StrictModel, runtime: RequestRuntime
    ) -> Any:
        args = AnalyzePrescriptionSnapshotArgs.model_validate(raw.model_dump())
        schema_raw = await self._java.request(
            "GET",
            "/api/v1/analytics/prescriptions/schema",
            runtime=runtime,
        )
        schema = PrescriptionDatasetSchema.model_validate(schema_raw)
        snapshot_raw = await self._java.request(
            "POST",
            "/api/v1/analytics/prescriptions/snapshot",
            runtime=runtime,
            json={
                "fromDate": args.from_date,
                "toDate": args.to_date,
                "departmentIds": args.department_ids,
                "maximumRows": min(args.maximum_rows, schema.maximum_rows),
            },
        )
        snapshot = PrescriptionAnalysisSnapshot.model_validate(snapshot_raw)
        if snapshot.schema_version != schema.schema_version:
            raise AgentError(
                "ANALYTICS_SCHEMA_MISMATCH",
                "The prescription snapshot does not match the advertised schema",
                status_code=502,
            )
        if snapshot.row_count != len(snapshot.rows):
            raise AgentError(
                "INVALID_ANALYTICS_SNAPSHOT",
                "The prescription snapshot row count is inconsistent",
                status_code=502,
            )
        sandbox_rows = [row.model_dump(mode="json", by_alias=False) for row in snapshot.rows]
        output = await self._sandbox.execute(args.code, sandbox_rows)
        return {
            "result": {
                "analysis": output.result,
                "dataset": {
                    "schemaVersion": schema.schema_version,
                    "rowCount": snapshot.row_count,
                    "truncated": snapshot.truncated,
                    "deIdentified": True,
                },
            },
            "chart": output.chart,
        }

    async def _search_knowledge(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        if self._knowledge is None:
            raise AgentError(
                "KNOWLEDGE_RETRIEVAL_DISABLED",
                "GraphRAG is not enabled",
                status_code=503,
            )
        args = SearchKnowledgeArgs.model_validate(raw.model_dump())
        result = await self._knowledge.search(
            args.query,
            args.top_k or self._knowledge_top_k,
        )
        return result.model_dump(mode="json", by_alias=True)

    # ── 医学业务工具执行�?──────────────────────────────────────────

    async def _list_patients(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = ListPatientsArgs.model_validate(raw.model_dump())
        params: dict[str, Any] = {"page": args.page, "size": args.size}
        if args.keyword:
            params["keyword"] = args.keyword
        return await self._java.request("GET", "/api/v1/patients", runtime=runtime, params=params)

    async def _get_patient(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = GetPatientArgs.model_validate(raw.model_dump())
        return await self._java.request("GET", f"/api/v1/patients/{args.patient_id}", runtime=runtime)

    async def _create_patient(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = CreatePatientArgs.model_validate(raw.model_dump())
        payload: dict[str, Any] = {
            "name": args.name,
            "gender": args.gender,
        }
        if args.birth_date:
            payload["birthDate"] = args.birth_date
        if args.phone:
            payload["phone"] = args.phone
        if args.id_card:
            payload["idCard"] = args.id_card
        if args.blood_type:
            payload["bloodType"] = args.blood_type
        if args.allergy_history:
            payload["allergyHistory"] = args.allergy_history
        if args.medical_history:
            payload["medicalHistory"] = args.medical_history
        return await self._java.request(
            "POST", "/api/v1/patients", runtime=runtime, json=payload, write=True,
        )

    async def _create_prescription(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = CreatePrescriptionArgs.model_validate(raw.model_dump())
        payload: dict[str, Any] = {
            "patientId": args.patient_id,
            "prescriptionDate": datetime.now().isoformat(),
            "diagnosis": args.diagnosis,
            "drugsJson": args.drugs,
            "totalAmount": args.total_amount,
        }
        if args.record_id:
            payload["recordId"] = args.record_id
        if args.notes:
            payload["notes"] = args.notes
        return await self._java.request(
            "POST", "/api/v1/prescriptions", runtime=runtime, json=payload, write=True,
        )

    async def _list_medical_records(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = ListMedicalRecordsArgs.model_validate(raw.model_dump())
        params: dict[str, Any] = {"page": args.page, "size": args.size}
        if args.keyword:
            params["keyword"] = args.keyword
        return await self._java.request(
            "GET", "/api/v1/medical-records", runtime=runtime, params=params,
        )

    async def _get_medical_record(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = GetMedicalRecordArgs.model_validate(raw.model_dump())
        return await self._java.request(
            "GET", f"/api/v1/medical-records/{args.record_id}", runtime=runtime,
        )

    async def _create_medical_record(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = CreateMedicalRecordArgs.model_validate(raw.model_dump())
        payload: dict[str, Any] = {
            "patientId": args.patient_id,
            "visitDate": args.visit_date,
        }
        for key, value in {
            "chiefComplaint": args.chief_complaint,
            "diagnosis": args.diagnosis,
            "treatmentPlan": args.treatment_plan,
            "notes": args.notes,
        }.items():
            if value:
                payload[key] = value
        return await self._java.request(
            "POST", "/api/v1/medical-records", runtime=runtime, json=payload, write=True,
        )

    async def _list_prescriptions(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = ListPrescriptionsArgs.model_validate(raw.model_dump())
        params: dict[str, Any] = {"page": args.page, "size": args.size}
        if args.keyword:
            params["keyword"] = args.keyword
        return await self._java.request(
            "GET", "/api/v1/prescriptions", runtime=runtime, params=params,
        )

    async def _get_prescription(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        args = GetPrescriptionArgs.model_validate(raw.model_dump())
        return await self._java.request(
            "GET", f"/api/v1/prescriptions/{args.prescription_id}", runtime=runtime,
        )

    # ── 医学知识图谱工具执行�?────────────────────────────────────────

    async def _search_disease(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        del runtime
        args = SearchDiseaseArgs.model_validate(raw.model_dump())
        async with self._neo4j.session(database=self._neo4j_db) as session:
            # Canonical medical graph schema uses English labels and uppercase relations.
            result = await session.run(
                "MATCH (d:Disease {name: $name}) RETURN d",
                name=args.name,
            )
            record = await result.single()
            if not record:
                # 模糊匹配
                result = await session.run(
                    "MATCH (d:Disease) WHERE d.name CONTAINS $name RETURN d LIMIT 5",
                    name=args.name,
                )
                records = await result.data()
                if not records:
                    return {"found": False, "message": f"No disease found for {args.name}."}
                return {
                    "found": True,
                    "matchType": "fuzzy",
                    "diseases": [r["d"]["name"] for r in records],
                    "message": f"未精确匹�?{args.name}'，您是否想查：{', '.join(r['d']['name'] for r in records)}",
                }

            disease = dict(record["d"])
            node_status = str(disease.get("reviewStatus") or "").upper()
            knowledge_status = (
                node_status if node_status in {"PUBLISHED", "APPROVED"} else "UNREVIEWED"
            )
            # Full catalog projection is user-facing; the answer layer labels
            # unreviewed content as encyclopedia reference rather than hiding it.
            # Reviewed diseases additionally carry an authoritative source.
            reviewed = knowledge_status in {"PUBLISHED", "APPROVED"}

            def _clip(value: Any, limit: int = 260) -> str:
                text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
                return (text[:limit].rstrip() + "...") if len(text) > limit else text

            safe_disease = {"name": str(disease.get("name") or "")}
            summary_value = (
                disease.get("summary")
                or disease.get("desc")
                or disease.get("catalogSummary")
            )
            if summary_value:
                safe_disease["summary"] = _clip(summary_value)
            for source_key, target_key in (
                ("cause", "病因"),
                ("easy_get", "高发人群"),
                ("prevent", "预防"),
                ("get_way", "传播途径"),
                ("cure_lasttime", "治疗周期"),
                ("cured_prob", "Cure rate"),
            ):
                if disease.get(source_key):
                    safe_disease[target_key] = _clip(disease[source_key])
            if reviewed:
                for source_key, target_key in (
                    ("sourceTitle", "sourceTitle"),
                    ("sourceUri", "sourceUri"),
                    ("knowledgeVersion", "knowledgeVersion"),
                    ("reviewedAt", "reviewedAt"),
                ):
                    if disease.get(source_key) is not None:
                        value = disease[source_key]
                        safe_disease[target_key] = (
                            str(value) if source_key == "reviewedAt" else value
                        )
            # Gate removed: return the full catalog relations. The answer layer
            # labels them as unreviewed encyclopedia reference (see
            # build_disease_answer); reviewed sources are cited when present.
            rel_queries = {
                "症状": (
                    "MATCH (d:Disease {name: $name})-[:HAS_SYMPTOM]->(s:Symptom) "
                    "RETURN DISTINCT s.name AS name ORDER BY name LIMIT 15"
                ),
                "Departments": (
                    "MATCH (d:Disease {name: $name})-[:BELONGS_TO]->(k:Department) "
                    "RETURN DISTINCT k.name AS name ORDER BY name LIMIT 5"
                ),
                "Complications": (
                    "MATCH (d:Disease {name: $name})-[:COMPLICATION]->(c:Disease) "
                    "RETURN DISTINCT c.name AS name ORDER BY name LIMIT 15"
                ),
                "Examinations": (
                    "MATCH (d:Disease {name: $name})-[:REQUIRES_EXAM]->(e:Exam) "
                    "RETURN DISTINCT e.name AS name ORDER BY name LIMIT 15"
                ),
                "治疗方式": (
                    "MATCH (d:Disease {name: $name})-[:HAS_THERAPY]->(t:Therapy) "
                    "RETURN DISTINCT t.name AS name ORDER BY name LIMIT 10"
                ),
                "宜吃": (
                    "MATCH (d:Disease {name: $name})-[:RECOMMENDED_EAT]->(f:Food) "
                    "RETURN DISTINCT f.name AS name ORDER BY name LIMIT 10"
                ),
                "忌吃": (
                    "MATCH (d:Disease {name: $name})-[:AVOID_EAT]->(f:Food) "
                    "RETURN DISTINCT f.name AS name ORDER BY name LIMIT 10"
                ),
            }
            relations: dict[str, list[str]] = {}
            for label, cypher in rel_queries.items():
                rel_result = await session.run(cypher, name=args.name)
                records = await rel_result.data()
                if records:
                    relations[label] = [r["name"] for r in records]

            routing_result = await session.run(
                """
                MATCH (d:Disease {name: $name})-[route:ROUTED_TO]->(k:Department)
                WHERE k.standard = true
                  AND route.evidenceLevel = 'REFERENCE_ONLY'
                RETURN DISTINCT k.name AS name
                ORDER BY name
                LIMIT 5
                """,
                name=args.name,
            )
            routing_departments = [
                row["name"] for row in await routing_result.data() if row.get("name")
            ]
            return {
                "found": True,
                "disease": safe_disease,
                "relations": relations,
                "relationsReviewed": reviewed,
                "reviewTier": "REVIEWED" if reviewed else "CATALOG",
                "knowledgeStatus": knowledge_status,
                "routingDepartments": routing_departments,
                "routingEvidence": (
                    "REFERENCE_ONLY" if routing_departments else "INSUFFICIENT"
                ),
            }

    async def _search_symptom(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        del runtime
        args = SearchSymptomArgs.model_validate(raw.model_dump())
        # Colloquial �?vocabulary normalization: the disease-kb symptom
        # vocabulary prefers e.g. 头痛 over 头疼. Try both spellings exactly
        # before degrading to substring suggestions.
        candidates = [args.symptom]
        async with self._neo4j.session(database=self._neo4j_db) as session:
            result = await session.run(
                """
                MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom)
                WHERE s.name IN $candidates
                RETURN DISTINCT d.name AS disease,
                       coalesce(d.summary, d.desc, d.catalogSummary, '') AS desc,
                       coalesce(d.sourceUri, '') AS sourceUri
                ORDER BY disease
                LIMIT 12
                """,
                candidates=candidates,
            )
            records = await result.data()
            if not records:
                # 模糊匹配
                result = await session.run(
                    "MATCH (s:Symptom) WHERE s.name CONTAINS $symptom RETURN s.name AS name LIMIT 10",
                    symptom=args.symptom,
                )
                suggestions = await result.data()
                if not suggestions:
                    return {
                        "found": False,
                        "message": f"知识库中暂时没有与“{args.symptom}”直接关联的疾病记录",
                    }
                return {
                    "found": False,
                    "suggestions": [s["name"] for s in suggestions],
                    "message": (
                        f"No directly related disease found for {args.symptom}."
                        f"知识库中存在名称相近的症状：{', '.join(s['name'] for s in suggestions)}"
                    ),
                }
            diseases = [
                {
                    "name": r["disease"],
                    "summary": str(r["desc"] or "").replace("\n", " ").strip()[:60],
                    "sourceUri": r["sourceUri"],
                }
                for r in records
            ]
            return {
                "found": True,
                "symptom": args.symptom,
                "possibleDiseases": diseases,
                "relationsReviewed": False,
            }

    async def _search_drug(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        del runtime
        args = SearchDrugArgs.model_validate(raw.model_dump())
        async with self._neo4j.session(database=self._neo4j_db) as session:
            result = await session.run(
                "MATCH (r:Drug {name: $name}) RETURN r",
                name=args.name,
            )
            record = await result.single()
            if not record:
                result = await session.run(
                    "MATCH (r:Drug) WHERE r.name CONTAINS $name RETURN r LIMIT 5",
                    name=args.name,
                )
                records = await result.data()
                if not records:
                    return {"found": False, "message": f"No drug found for {args.name}."}
                return {
                    "found": True,
                    "matchType": "fuzzy",
                    "query": args.name,
                    "drugs": [r["r"]["name"] for r in records],
                    "message": f"未精确匹�?{args.name}'，您是否想查：{', '.join(r['r']['name'] for r in records)}",
                }

            drug = dict(record["r"])
            node_status = str(drug.get("reviewStatus") or "").upper()
            knowledge_status = (
                node_status if node_status in {"PUBLISHED", "APPROVED"} else "UNREVIEWED"
            )
            safe_drug = {"name": str(drug.get("name") or "")}
            if knowledge_status in {"PUBLISHED", "APPROVED"}:
                for key in (
                    "category",
                    "summary",
                    "adverseReactions",
                    "contraindications",
                    "warnings",
                    "sourceTitle",
                    "sourceUri",
                    "knowledgeVersion",
                    "reviewedAt",
                ):
                    if drug.get(key) is not None:
                        value = drug[key]
                        safe_drug[key] = str(value) if key == "reviewedAt" else value
            # Reviewed indications stay separate from catalog associations. The
            # answer layer cites the first as label facts and renders the second
            # as "在哪些疾病条目下出现�? reference �?never as a usage recommendation.
            result = await session.run(
                """
                MATCH (d:Disease)-[rel:TREATED_BY]->(r:Drug {name: $name})
                WHERE toUpper(coalesce(d.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                  AND toUpper(coalesce(r.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                  AND coalesce(d.sourceUri, '') STARTS WITH 'https://'
                  AND coalesce(r.sourceUri, '') STARTS WITH 'https://'
                  AND coalesce(rel.sourceUri, '') STARTS WITH 'https://'
                  AND (coalesce(rel.reviewed, false) = true
                    OR toUpper(coalesce(rel.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED'])
                RETURN DISTINCT d.name AS disease
                ORDER BY disease
                LIMIT 8
                """,
                name=args.name,
            )
            treats = [r["disease"] for r in await result.data()]
            catalog_result = await session.run(
                """
                MATCH (d:Disease)-[:TREATED_BY]->(r:Drug {name: $name})
                RETURN DISTINCT d.name AS disease
                ORDER BY disease
                LIMIT 12
                """,
                name=args.name,
            )
            catalog_diseases = [
                row["disease"]
                for row in await catalog_result.data()
                if row.get("disease") and row["disease"] not in treats
            ]
            return {
                "found": True,
                "drug": safe_drug,
                "treatsDiseases": treats,
                "catalogRelatedDiseases": catalog_diseases,
                "relationsReviewed": True,
                "knowledgeStatus": knowledge_status,
            }

    async def _search_department(self, raw: StrictModel, runtime: RequestRuntime) -> Any:
        del runtime
        args = SearchDepartmentArgs.model_validate(raw.model_dump())
        async with self._neo4j.session(database=self._neo4j_db) as session:
            if args.name:
                department_name = canonical_department(args.name) or args.name
                result = await session.run(
                    """
                    MATCH (d:Disease)-[rel:BELONGS_TO]->(k:Department {name: $name})
                    WHERE toUpper(coalesce(d.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                      AND toUpper(coalesce(k.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED']
                      AND coalesce(d.sourceUri, '') STARTS WITH 'https://'
                      AND coalesce(k.sourceUri, '') STARTS WITH 'https://'
                      AND coalesce(rel.sourceUri, '') STARTS WITH 'https://'
                      AND (coalesce(rel.reviewed, false) = true
                        OR toUpper(coalesce(rel.reviewStatus, '')) IN ['PUBLISHED', 'APPROVED'])
                    RETURN DISTINCT d.name AS disease
                    ORDER BY disease
                    LIMIT 20
                    """,
                    name=department_name,
                )
                records = await result.data()
                reviewed_diseases = [r["disease"] for r in records]
                # Catalog tier: standardized ROUTED_TO edges plus the raw
                # BELONGS_TO catalog, so a department lookup returns the whole
                # encyclopedia rather than only the reviewed subset.
                catalog_result = await session.run(
                    """
                    MATCH (d:Disease)-[route:ROUTED_TO]->(
                      k:Department {name: $name, standard: true}
                    )
                    WHERE d.catalogStatus = 'CATALOGED'
                      AND route.evidenceLevel = 'REFERENCE_ONLY'
                    RETURN DISTINCT d.name AS disease
                    UNION
                    MATCH (d:Disease)-[:BELONGS_TO]->(k:Department {name: $name})
                    RETURN DISTINCT d.name AS disease
                    """,
                    name=department_name,
                )
                # UNION drops ORDER BY/LIMIT, so bound the result set here.
                catalog_diseases = sorted(
                    {
                        r["disease"]
                        for r in await catalog_result.data()
                        if r.get("disease") and r["disease"] not in reviewed_diseases
                    }
                )[:50]
                if not reviewed_diseases and not catalog_diseases:
                    return {
                        "found": False,
                        "message": f"当前没有科室“{department_name}”对应的疾病目录",
                    }
                return {
                    "found": True,
                    "department": department_name,
                    "diseases": reviewed_diseases,
                    "catalogDiseases": catalog_diseases,
                    "relationsReviewed": True,
                }
            else:
                result = await session.run(
                    """
                    MATCH (k:Department)
                    WHERE k.standard = true
                      AND k.catalogStatus = 'STANDARDIZED'
                      AND coalesce(k.sourceUri, '') STARTS WITH 'https://'
                    RETURN DISTINCT k.name AS name ORDER BY name LIMIT 100
                    """
                )
                records = await result.data()
                return {"found": True, "departments": [r["name"] for r in records]}
