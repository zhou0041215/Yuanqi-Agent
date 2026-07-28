import pytest

from yuanqi_agent.medical_response import build_disease_answer
from yuanqi_agent.retrieval.hybrid import HybridRetriever
from yuanqi_agent.retrieval.models import RetrievalCandidate
from yuanqi_agent.service import (
    _contextualize_message,
    _is_medication_advice,
    _medication_safety_response,
    _route_medical_tool,
    _sanitize_disease_payload,
)


class StaticRetriever:
    def __init__(self, items):
        self.items = items

    async def search(self, query: str, tenant_id: int, top_k: int):
        del query, tenant_id, top_k
        return self.items


def candidate(title: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id=f"Disease:{title}",
        title=title,
        content=f"{title}的医学知识",
        source="vector",
        raw_score=score,
        metadata={
            "source_uri": "https://example.org/published-evidence",
            "governance_status": "PUBLISHED",
            "knowledge_version": 1,
            "entity_type": "Disease",
        },
    )


def test_short_medication_follow_up_inherits_previous_disease_subject() -> None:
    history = [
        {"role": "user", "content": "高血压应该挂什么科？"},
        {"role": "assistant", "content": "建议心血管内科。"},
    ]

    resolved = _contextualize_message("建议吃啥药", history)

    assert resolved == "高血压：建议吃啥药"
    assert _is_medication_advice(resolved)
    routed = _route_medical_tool(
        resolved,
        [{"name": "search_disease"}, {"name": "search_knowledge"}],
    )
    assert routed == {"name": "search_disease", "arguments": {"name": "高血压"}}


def test_medication_response_never_names_or_doses_a_drug() -> None:
    response = _medication_safety_response("高血压：建议吃啥药")

    assert "高血压" in response
    assert "具体药名或剂量" in response
    assert "自行" in response
    assert "180/120" in response
    assert "华法林" not in response
    assert "肝素" not in response


def test_diabetes_medication_response_does_not_include_hypertension_emergency_rule() -> None:
    response = _medication_safety_response("糖尿病：吃什么药能够治疗")

    assert "糖尿病" in response
    assert "180/120" not in response


def test_lower_blood_pressure_follow_up_resolves_to_hypertension() -> None:
    resolved = _contextualize_message(
        "吃那些药能够降血压",
        [{"role": "user", "content": "糖尿病有哪些并发症？"}],
    )

    assert resolved == "高血压：吃那些药能够降血压"
    assert _is_medication_advice(resolved)


def test_drug_router_preserves_complete_product_name() -> None:
    tools = [{"name": "search_drug"}]

    assert _route_medical_tool("头孢", tools) == {
        "name": "search_drug",
        "arguments": {"name": "头孢"},
    }
    assert _route_medical_tool("头孢丙烯分散片", tools) == {
        "name": "search_drug",
        "arguments": {"name": "头孢丙烯分散片"},
    }
    assert _route_medical_tool("头孢丙烯分散片的副作用是什么？", tools) == {
        "name": "search_drug",
        "arguments": {"name": "头孢丙烯分散片"},
    }


def test_common_disease_aliases_route_to_canonical_graph_names() -> None:
    tools = [{"name": "search_disease"}]

    assert _route_medical_tool("乙肝有哪些症状", tools) == {
        "name": "search_disease",
        "arguments": {"name": "乙型病毒性肝炎"},
    }
    assert _route_medical_tool("慢阻肺应该挂什么科", tools) == {
        "name": "search_disease",
        "arguments": {"name": "慢性阻塞性肺疾病"},
    }


def test_curated_non_diabetes_disease_has_source_backed_sections() -> None:
    answer = build_disease_answer(
        "哮喘有哪些症状",
        {
            "found": True,
            "knowledgeStatus": "PUBLISHED",
            "disease": {"name": "哮喘"},
            "relations": {},
        },
    )

    assert "喘鸣" in answer
    assert "气短" in answer
    assert "WHO" in answer


def test_department_answer_hides_unrelated_and_dirty_relationships() -> None:
    payload = {
        "found": True,
        "disease": {"name": "高血压"},
        "relations": {
            "所属科室": ["心血管内科", "心血管内科"],
            "治疗药品": ["氨氯地平", "Ⅰ", "x" * 100],
            "症状": ["头痛"],
        },
    }

    cleaned = _sanitize_disease_payload(payload, "高血压应该挂什么科？")

    assert cleaned["relations"] == {"所属科室": ["心血管内科"]}


def test_upstream_truncated_symptom_names_are_dropped() -> None:
    """The open catalog cuts symptom names at 10 chars; fragments are not shown."""
    payload = {
        "found": True,
        "disease": {"name": "示例疾病"},
        "relations": {
            "症状": [
                "呼吸困难",
                "一侧乳头萎缩，...",
                "Korsako...",
                "“三怕”(水声…",
                "胸痛",
            ],
        },
    }

    cleaned = _sanitize_disease_payload(payload, "示例疾病有什么症状")

    assert cleaned["relations"]["症状"] == ["呼吸困难", "胸痛"]


def test_complication_question_only_keeps_complications() -> None:
    payload = {
        "found": True,
        "disease": {"name": "糖尿病"},
        "relations": {
            "症状": ["多饮"],
            "治疗药品": ["二甲双胍"],
            "并发症": ["糖尿病肾病", "糖尿病视网膜病变"],
            "检查项目": ["糖化血红蛋白"],
        },
    }

    cleaned = _sanitize_disease_payload(payload, "糖尿病有哪些并发症？")

    assert cleaned["relations"] == {
        "并发症": ["糖尿病肾病", "糖尿病视网膜病变"],
    }


def test_bare_disease_name_returns_overview_not_diagnostic_interview() -> None:
    answer = build_disease_answer(
        "糖尿病",
        {
            "found": True,
            "knowledgeStatus": "UNREVIEWED",
            "disease": {"name": "糖尿病"},
            "relations": {},
        },
    )

    assert "简要认识" in answer
    assert "你可以继续问" in answer
    assert "症状何时开始" not in answer
    assert "WHO" in answer


@pytest.mark.asyncio
async def test_zero_relevance_vector_results_are_rejected() -> None:
    hybrid = HybridRetriever(
        StaticRetriever([]),
        StaticRetriever([
            candidate("下肢深静脉血栓形成", 0.0),
            candidate("宫颈白斑", 0.0),
        ]),
    )

    result = await hybrid.search("高血压建议吃什么药", tenant_id=1, top_k=8)

    assert result.items == []
    assert result.context == ""


@pytest.mark.asyncio
async def test_relevant_hypertension_result_survives_filter() -> None:
    hybrid = HybridRetriever(
        StaticRetriever([]),
        StaticRetriever([candidate("高血压", 0.72)]),
    )

    result = await hybrid.search("高血压建议吃什么药", tenant_id=1, top_k=8)

    assert [item.title for item in result.items] == ["高血压"]
    assert result.items[0].metadata["bestRawScore"] == 0.72
