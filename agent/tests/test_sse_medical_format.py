from yuanqi_agent.sse import format_result


def test_knowledge_result_formats_governed_retrieval_payload() -> None:
    result = format_result(
        "search_knowledge",
        {
            "items": [
                {
                    "citation_id": "K1",
                    "title": "腹泻",
                    "content": "腹泻相关资料",
                },
            ],
            "context": "[K1] 腹泻\n腹泻相关资料",
        },
    )

    assert "腹泻" in result
    assert "腹泻相关资料" in result


def test_fuzzy_drug_result_has_one_clean_heading_and_bullets() -> None:
    result = format_result(
        "search_drug",
        {
            "found": True,
            "matchType": "fuzzy",
            "drugs": ["头孢丙烯分散片", "头孢克肟分散片"],
        },
    )

    assert result.count("### ") == 1
    assert "💊" not in result
    assert "## 💊" not in result
    assert "- 头孢丙烯分散片" in result
    assert "完整名称" in result


def test_exact_drug_result_uses_consistent_markdown() -> None:
    result = format_result(
        "search_drug",
        {
            "found": True,
            "knowledgeStatus": "PUBLISHED",
            "drug": {
                "name": "头孢克肟",
                "类别": "头孢菌素类",
                "副作用": "恶心、腹泻等",
            },
            "treatsDiseases": ["细菌感染"],
        },
    )

    assert result.startswith("### 药物信息：头孢克肟")
    assert "- **类别：** 头孢菌素类" in result
    assert "不构成处方" in result


def test_unreviewed_demo_drug_dosage_is_never_exposed() -> None:
    result = format_result(
        "search_drug",
        {
            "found": True,
            "knowledgeStatus": "UNREVIEWED",
            "drug": {
                "name": "阿莫西林",
                "用法": "未经审核的固定剂量",
            },
            "treatsDiseases": [],
            "relationsReviewed": True,
        },
    )

    assert "未经审核的固定剂量" not in result
    assert "青霉素类抗菌药物" in result
    assert "DailyMed" in result


def test_graph_drug_facts_never_suppress_label_safety_warnings() -> None:
    """A generic drug-class fact must not hide the allergy warning."""
    result = format_result(
        "search_drug",
        {
            "found": True,
            "knowledgeStatus": "PUBLISHED",
            "drug": {
                "name": "阿莫西林",
                "category": "青霉素类抗生素",
                "summary": "属于青霉素类抗生素，收录于世界卫生组织基本药物示范目录。",
                "sourceTitle": "WHO Model List of Essential Medicines",
                "sourceUri": "https://www.who.int/groups/x",
            },
            "treatsDiseases": [],
            "relationsReviewed": True,
        },
    )

    # The graph's published fields still show…
    assert "- **类别：** 青霉素类抗生素" in result
    # …and the label-sourced warning is merged in rather than dropped.
    assert "重要提醒" in result
    assert "青霉素" in result and "过敏" in result
    assert "DailyMed" in result
    # The graph value wins for a field both sources provide — no duplicate line.
    assert result.count("- **类别：**") == 1


def test_unreviewed_drug_disease_relations_are_not_displayed() -> None:
    result = format_result(
        "search_drug",
        {
            "found": True,
            "drug": {"name": "头孢丙烯分散片"},
            "treatsDiseases": ["病毒性上呼吸道感染", "千足虫灼伤"],
            "relationsReviewed": False,
        },
    )

    assert "病毒性上呼吸道感染" not in result
    assert "千足虫灼伤" not in result
    assert "DailyMed" in result


def test_reviewed_drug_relations_are_capped() -> None:
    diseases = [f"已审核适应证{i}" for i in range(12)]
    result = format_result(
        "search_drug",
        {
            "found": True,
            "drug": {"name": "示例药物"},
            "treatsDiseases": diseases,
            "relationsReviewed": True,
        },
    )

    assert "已审核适应证7" in result
    assert "已审核适应证8" not in result


def test_unreviewed_disease_node_exposes_catalog_content_with_label() -> None:
    """Encyclopedia mode: catalog properties reach the user, always labeled."""
    result = format_result(
        "search_disease",
        {
            "found": True,
            "knowledgeStatus": "UNREVIEWED",
            "disease": {
                "name": "示例疾病",
                "summary": "目录简介",
            },
            "relations": {"并发症": ["目录并发症"]},
        },
        user_message="示例疾病有哪些并发症",
    )

    assert "示例疾病" in result
    assert "目录简介" in result
    assert "目录并发症" in result
    assert "未经逐条人工审核" in result


def test_reviewed_symptom_relations_are_framed_as_associations() -> None:
    result = format_result(
        "search_symptom",
        {
            "found": True,
            "symptom": "头痛",
            "possibleDiseases": [{"name": "示例疾病", "summary": "目录摘要"}],
            "relationsReviewed": True,
        },
    )

    assert "目录摘要" in result
    assert "医学百科参考" in result
    assert "不能用于自行诊断" in result
