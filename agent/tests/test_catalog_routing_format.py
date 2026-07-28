from yuanqi_agent.sse import format_result


def test_unreviewed_disease_renders_catalog_content_as_reference() -> None:
    """Encyclopedia mode: catalog entries are shown, but labeled unreviewed."""
    payload = {
        "found": True,
        "disease": {
            "name": "胃炎",
            "summary": "胃黏膜炎症。",
            "病因": "幽门螺杆菌感染等。",
        },
        "relations": {"症状": ["上腹痛", "反酸"], "忌吃": ["辛辣食物"]},
        "knowledgeStatus": "UNREVIEWED",
        "routingDepartments": ["消化内科"],
        "routingEvidence": "REFERENCE_ONLY",
    }
    overview = format_result(
        "search_disease",
        payload,
        user_message="胃炎",
    )
    diet = format_result(
        "search_disease",
        payload,
        user_message="胃炎忌口",
    )
    routing = format_result(
        "search_disease",
        payload,
        user_message="胃炎应该挂什么科",
    )

    # Catalog facts and relations must reach the user instead of being hidden.
    assert "胃黏膜炎症" in overview
    assert "幽门螺杆菌感染" in overview
    assert "上腹痛" in overview
    assert "辛辣食物" in diet
    assert "消化内科" in routing
    assert "标准化疾病目录" in routing
    # …but never without the reference-only label.
    assert "未经逐条人工审核" in overview


def test_reviewed_disease_still_keeps_catalog_relation_boundary() -> None:
    result = format_result(
        "search_disease",
        {
            "found": True,
            "disease": {"name": "糖尿病", "summary": "慢性代谢疾病。"},
            "relations": {"症状": ["口渴"]},
            "knowledgeStatus": "PUBLISHED",
            "routingDepartments": [],
        },
        user_message="糖尿病有哪些症状",
    )

    assert "口渴" in result
    assert "未经逐条人工审核" in result


def test_department_separates_reviewed_and_reference_entries() -> None:
    result = format_result(
        "search_department",
        {
            "found": True,
            "department": "消化内科",
            "diseases": ["已审核疾病"],
            "catalogDiseases": ["目录疾病"],
            "relationsReviewed": True,
        },
    )

    assert "已审核疾病关系" in result
    assert "目录分流参考" in result
    assert "不代表诊断" in result
