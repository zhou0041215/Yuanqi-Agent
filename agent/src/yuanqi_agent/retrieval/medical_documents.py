from typing import Any

MAX_RELATION_VALUES = 20
MAX_DOCUMENT_CHARACTERS = 19_500
PUBLISHED_STATUSES = {"PUBLISHED", "APPROVED"}

CATALOG_SOURCE_TITLE = "内部医学百科目录（disease-kb 开源数据）"
CATALOG_SOURCE_URI = "https://github.com/nuolade/disease-kb"


# Encyclopedia mode: index the whole catalog. Reviewed diseases keep their
# authoritative source and PUBLISHED status; the rest are indexed as
# LEGACY_UNREVIEWED so the answer layer can label them as reference-only
# instead of the retrieval layer pretending they do not exist.
MEDICAL_DOCUMENT_QUERY = """
MATCH (d:Disease)
WHERE coalesce(d.name, '') <> ''
  AND coalesce(d.retrievalStatus, '') <> 'EXCLUDED'
CALL (d) {
  OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(node:Symptom)
  RETURN collect(DISTINCT node.name) AS symptoms
}
CALL (d) {
  OPTIONAL MATCH (d)-[:TREATED_BY]->(node:Drug)
  RETURN collect(DISTINCT node.name) AS drugs
}
CALL (d) {
  OPTIONAL MATCH (d)-[:BELONGS_TO]->(node:Department)
  RETURN collect(DISTINCT node.name) AS departments
}
CALL (d) {
  OPTIONAL MATCH (d)-[:COMPLICATION]->(node:Disease)
  RETURN collect(DISTINCT node.name) AS complications
}
CALL (d) {
  OPTIONAL MATCH (d)-[:REQUIRES_EXAM]->(node:Exam)
  RETURN collect(DISTINCT node.name) AS exams
}
CALL (d) {
  OPTIONAL MATCH (d)-[:HAS_THERAPY]->(node:Therapy)
  RETURN collect(DISTINCT node.name) AS therapies
}
CALL (d) {
  OPTIONAL MATCH (d)-[:RECOMMENDED_EAT]->(node:Food)
  RETURN collect(DISTINCT node.name) AS recommended_foods
}
CALL (d) {
  OPTIONAL MATCH (d)-[:AVOID_EAT]->(node:Food)
  RETURN collect(DISTINCT node.name) AS avoided_foods
}
RETURN properties(d) AS properties,
       symptoms, drugs, departments, complications, exams,
       therapies, recommended_foods, avoided_foods
ORDER BY d.name
""".strip()


def build_disease_document(record: dict[str, Any]) -> dict[str, Any]:
    """Build a vector document from a graph record.

    Published records carry their reviewed source. Catalog records are indexed
    too, tagged LEGACY_UNREVIEWED so the answer layer renders them as
    encyclopedia reference rather than as reviewed clinical guidance.
    """
    properties = dict(record.get("properties") or {})
    name = str(properties.get("name") or "").strip()
    if not name:
        raise ValueError("Disease record requires a name")

    status = str(
        properties.get("reviewStatus") or properties.get("governanceStatus") or ""
    ).upper()
    source_uri = str(
        properties.get("sourceUri") or properties.get("source_uri") or ""
    ).strip()
    published = status in PUBLISHED_STATUSES and source_uri.startswith("https://")
    if not published:
        source_uri = CATALOG_SOURCE_URI

    sections = [f"疾病名称：{name}"]
    scalar_fields = (
        ("别名", ("别名", "alias", "aliases")),
        ("简介", ("summary", "简介", "description", "desc", "catalogSummary")),
        ("病因", ("病因", "cause")),
        ("高发人群", ("高发人群", "easy_get")),
        ("预防", ("预防", "prevent")),
        ("传播途径", ("get_way",)),
        ("治疗周期", ("cure_lasttime",)),
        ("治愈率", ("cured_prob",)),
    )
    for label, keys in scalar_fields:
        value = next((properties.get(key) for key in keys if properties.get(key)), None)
        if value:
            sections.append(f"{label}：{str(value).strip()}")

    # Deliberately cautious user-facing labels. Graph associations are not
    # diagnoses, mandatory tests, or personalized prescriptions.
    relation_fields = (
        ("常见症状线索", "symptoms"),
        ("相关药物线索", "drugs"),
        ("通常就诊科室", "departments"),
        ("可能并发症", "complications"),
        ("医生可能结合使用的检查", "exams"),
        ("常见治疗方式", "therapies"),
        ("饮食参考｜宜吃", "recommended_foods"),
        ("饮食参考｜忌吃", "avoided_foods"),
    )
    for label, key in relation_fields:
        values = sorted(
            {
                str(value).strip()
                for value in record.get(key, [])
                if value is not None and str(value).strip()
            }
        )
        if values:
            displayed = values[:MAX_RELATION_VALUES]
            suffix = (
                f"（仅展示前 {MAX_RELATION_VALUES} 项，共 {len(values)} 项）"
                if len(values) > MAX_RELATION_VALUES
                else ""
            )
            sections.append(f"{label}：{'、'.join(displayed)}{suffix}")

    entity_key = str(properties.get("entityKey") or f"Disease:{name}")
    content = "\n".join(sections)
    if len(content) > MAX_DOCUMENT_CHARACTERS:
        content = content[:MAX_DOCUMENT_CHARACTERS].rstrip() + "\n（内容已按安全上限截断）"
    return {
        "document_id": entity_key,
        "entity_key": entity_key,
        "title": name,
        "content": content,
        "source_uri": source_uri,
        "metadata": {
            "entity_type": "Disease",
            "knowledge_scope": "medical",
            "governance_status": "PUBLISHED" if published else "LEGACY_UNREVIEWED",
            "source_title": str(
                properties.get("sourceTitle") or ""
            ) if published else CATALOG_SOURCE_TITLE,
            "knowledge_version": int(
                properties.get("knowledgeVersion") or properties.get("version") or 1
            ),
        },
    }
