import pytest

from yuanqi_agent.retrieval.graph import GRAPH_SEARCH_QUERY, Neo4jGraphRetriever
from yuanqi_agent.tools import ToolRegistry


def test_default_registry_exposes_medical_tools() -> None:
    registry = ToolRegistry(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        neo4j_driver=object(),
    )

    names = {tool["name"] for tool in registry.describe()}

    assert {
        "list_patients",
        "get_patient",
        "create_patient",
        "create_prescription",
        "list_medical_records",
        "get_medical_record",
        "create_medical_record",
        "list_prescriptions",
        "get_prescription",
        "search_disease",
        "search_symptom",
        "search_drug",
        "search_department",
    } <= names

    schemas = {
        tool["name"]: tool["inputSchema"]
        for tool in registry.describe()
    }
    for tool_name in ("create_prescription", "create_medical_record"):
        assert "patientId" not in schemas[tool_name]["properties"]
        assert "patientId" not in schemas[tool_name].get("required", [])


class EntityResolutionResult:
    async def data(self) -> list[dict[str, str]]:
        return [
            {"name": "diabetes", "entity_label": "Disease"},
            {"name": "metformin", "entity_label": "Drug"},
        ]


class EntityResolutionSession:
    def __init__(self) -> None:
        self.query = ""
        self.parameters: dict[str, object] = {}

    async def __aenter__(self) -> "EntityResolutionSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def run(self, query: str, **parameters: object) -> EntityResolutionResult:
        self.query = query
        self.parameters = parameters
        return EntityResolutionResult()


class EntityResolutionDriver:
    def __init__(self) -> None:
        self.database = ""
        self.session_instance = EntityResolutionSession()

    def session(self, *, database: str) -> EntityResolutionSession:
        self.database = database
        return self.session_instance


@pytest.mark.asyncio
async def test_registry_resolves_catalog_entities_with_configured_priority() -> None:
    driver = EntityResolutionDriver()
    registry = ToolRegistry(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        neo4j_driver=driver,
        neo4j_database="medical",
    )

    entities = await registry.resolve_medical_entities("diabetes with metformin")

    assert entities == {"Disease": ["diabetes"], "Drug": ["metformin"]}
    assert driver.database == "medical"
    assert driver.session_instance.parameters["labels"] == [
        "Disease",
        "Drug",
        "Symptom",
        "Department",
    ]


def test_graph_retrieval_uses_only_canonical_medical_contract() -> None:
    assert set(Neo4jGraphRetriever._ALLOWED_LABELS) == {
        "Disease",
        "Symptom",
        "Drug",
        "Department",
        "Exam",
        # Diet and therapy entities are part of the browsable catalog and must
        # be reachable from Q&A ("这个病忌口什么").
        "Food",
        "Therapy",
    }
    for relation in (
        "HAS_SYMPTOM",
        "TREATED_BY",
        "BELONGS_TO",
        "COMPLICATION",
        "REQUIRES_EXAM",
        "HAS_THERAPY",
        "RECOMMENDED_EAT",
        "AVOID_EAT",
    ):
        assert relation in GRAPH_SEARCH_QUERY
    for legacy_relation in ("has_symptom", "recommand_drug", "belongs_to"):
        assert legacy_relation not in GRAPH_SEARCH_QUERY


def test_graph_retrieval_prioritizes_complete_chinese_terms() -> None:
    terms = Neo4jGraphRetriever._terms("糖尿病 多饮 糖化血红蛋白")

    assert terms[:3] == ["糖尿病", "多饮", "糖化血红蛋白"]
    assert "糖尿" in terms
    assert "多饮" in terms
