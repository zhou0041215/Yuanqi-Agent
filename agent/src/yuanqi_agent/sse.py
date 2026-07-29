from typing import Any

import orjson

from yuanqi_agent.medical_response import build_disease_answer
from yuanqi_agent.trusted_medical_knowledge import get_trusted_drug


def encode_sse(event: str, payload: dict) -> bytes:
    data = orjson.dumps(payload).decode("utf-8")
    return f"event: {event}\ndata: {data}\n\n".encode()


def is_confirmed_write_result(tool_name: str, payload: Any) -> bool:
    """Require the Java trust root to return the identity of a completed write."""
    if not isinstance(payload, dict):
        return False
    if tool_name == "create_patient":
        return (
            isinstance(payload.get("id"), int)
            and bool(str(payload.get("name") or "").strip())
            and bool(str(payload.get("patientNo") or "").strip())
        )
    if tool_name == "create_prescription":
        return (
            isinstance(payload.get("id"), int)
            and bool(str(payload.get("prescriptionNo") or "").strip())
        )
    if tool_name == "create_medical_record":
        return (
            isinstance(payload.get("id"), int)
            and bool(str(payload.get("recordNo") or "").strip())
        )
    return True


def format_result(
    tool_name: str,
    payload: Any,
    *,
    user_message: str = "",
) -> str:
    """Format tool result into a human-readable message."""
    if payload is None:
        return ""
    if tool_name == "search_knowledge" and isinstance(payload, dict):
        items = payload.get("items", [])
        context = str(payload.get("context") or "").strip()
        if not items:
            return "知识库中暂时没有找到相关内容，换个疾病名、症状或检查名称再试试。"
        lines = [f"### 相关医学百科条目（共 {len(items)} 条）\n"]
        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            metadata = item.get("metadata") or {}
            citation_id = item.get("citation_id", f"K{i}")
            source_uri = str(metadata.get("source_uri") or "")
            # Only genuinely authoritative (WHO) sources get a badge; the rest
            # are plain encyclopedia entries.
            source_label = (
                f" · [WHO 权威来源]({source_uri})"
                if source_uri.startswith("https://www.who.int")
                else ""
            )
            lines.append(f"**[{citation_id}] {title}**{source_label}")
        if context:
            lines.append(f"\n**详细信息：**\n{context}")
        lines.append(
            "\n> 以上内容来自内部医学百科（disease-kb 开源目录），未经逐条人工审核，"
            "仅供参考、不作诊断或用药依据；完整关系可在“医学知识图谱”页查看，具体请咨询医生。"
        )
        return "\n".join(lines)
    # ── 医学工具格式化 ──────────────────────────────────────────────
    if tool_name == "search_disease" and isinstance(payload, dict):
        disease = payload.get("disease", {})
        disease_name = disease.get("name", "") if isinstance(disease, dict) else ""
        return build_disease_answer(user_message or str(disease_name), payload)
    if tool_name == "search_symptom" and isinstance(payload, dict):
        if not payload.get("found"):
            msg = payload.get("message", "未找到相关症状")
            suggestions = payload.get("suggestions", [])
            if suggestions:
                msg += f"\n\n相关症状：{', '.join(suggestions)}"
            return msg
        diseases = payload.get("possibleDiseases", [])
        symptom = payload.get("symptom", "")
        lines = [f"### 可能与“{symptom}”相关的疾病（医学百科参考）\n"]
        for i, d in enumerate(diseases, 1):
            desc = d.get("summary", "")
            lines.append(f"{i}. **{d['name']}**" + (f" — {desc}" if desc else ""))
        lines.append(
            "\n> 以上关联来自内部医学百科（disease-kb 开源目录），未经逐条人工审核，"
            "仅供参考。同一症状可由多种情况引起，不能用于自行诊断；"
            "需结合持续时间、严重程度、伴随症状和检查结果，并由医生判断。"
        )
        return "\n".join(lines)
    if tool_name == "search_drug" and isinstance(payload, dict):
        if not payload.get("found"):
            return payload.get("message", "未找到相关药物信息")
        if payload.get("matchType") == "fuzzy":
            drugs = [
                str(item).strip()
                for item in payload.get("drugs", [])
                if str(item).strip()
            ]
            lines = [
                "### 找到以下相关药物",
                "",
                (
                    f"“{payload.get('query') or '该名称'}”未匹配到唯一药品。"
                    "以下只是名称候选，不代表它们具有相同适应证、剂量或禁忌："
                ),
                "",
            ]
            lines.extend(f"- {item}" for item in drugs)
            lines.extend(
                [
                    "",
                    "请提供药盒上的完整名称，或说明你想了解的是用途、副作用、禁忌还是与其他药物能否同用。",
                    "",
                    "> 抗菌药物应在医生或药师指导下使用，不建议仅凭症状自行选择。",
                ]
            )
            return "\n".join(lines)
        drug = payload.get("drug", {})
        treats = payload.get("treatsDiseases", [])
        relations_reviewed = payload.get("relationsReviewed") is True
        name = drug.get("name", "")
        lines = [f"### 药物信息：{name}", ""]
        detail_count = 0
        shown_labels: set[str] = set()
        shown_source_uris: set[str] = set()
        knowledge_status = payload.get("knowledgeStatus")
        if knowledge_status in {"PUBLISHED", "APPROVED"}:
            published_fields = (
                ("类别", ("category", "类别")),
                ("基本用途", ("summary", "适应症")),
                ("常见不良反应", ("adverseReactions", "副作用")),
                ("禁忌", ("contraindications", "禁忌")),
            )
            for label, keys in published_fields:
                value = next((drug.get(key) for key in keys if drug.get(key)), None)
                if value:
                    lines.append(f"- **{label}：** {value}")
                    shown_labels.add(label)
                    detail_count += 1
            source_uri = str(drug.get("sourceUri") or "")
            source_title = str(drug.get("sourceTitle") or "查看药品来源")
            if source_uri.startswith("https://"):
                lines.extend(["", f"[{source_title}]({source_uri})"])
                shown_source_uris.add(source_uri)
        # The versioned trusted record is the authored source for both Neo4j
        # publication and the runtime fallback. This keeps safety warnings
        # available while a newly published knowledge version is rolling out.
        trusted_drug = get_trusted_drug(name)
        if trusted_drug:
            for label, key in (("类别", "category"), ("基本用途", "summary")):
                if label not in shown_labels:
                    lines.append(f"- **{label}：** {getattr(trusted_drug, key)}")
                    shown_labels.add(label)
                    detail_count += 1
        raw_graph_warnings = (
            drug.get("warnings", [])
            if knowledge_status in {"PUBLISHED", "APPROVED"}
            else []
        )
        graph_warnings = (
            raw_graph_warnings
            if isinstance(raw_graph_warnings, list)
            else [raw_graph_warnings]
        )
        trusted_warnings = trusted_drug.warnings if trusted_drug else []
        warnings = list(
            dict.fromkeys(
                str(item).strip()
                for item in [*graph_warnings, *trusted_warnings]
                if str(item).strip()
            )
        )
        if warnings:
            lines.extend(["", "**重要提醒**"])
            lines.extend(f"- {warning}" for warning in warnings)
            detail_count += 1
        if trusted_drug:
            trusted_source_uri = str(trusted_drug.source_uri)
            if trusted_source_uri not in shown_source_uris:
                lines.extend(
                    [
                        "",
                        f"[{trusted_drug.source_title}]({trusted_source_uri})",
                    ]
                )
        if treats and relations_reviewed:
            lines.append(f"- **已审核适应证线索：** {', '.join(treats[:8])}")
            detail_count += 1
        # Catalog co-occurrence is shown as "which disease entries mention this
        # drug" — deliberately not phrased as an indication, since these edges
        # carry no label review.
        catalog_related = [
            str(item).strip()
            for item in payload.get("catalogRelatedDiseases", [])
            if str(item).strip()
        ]
        if catalog_related:
            shown = catalog_related[:10]
            suffix = (
                f"…（等共 {len(catalog_related)} 项）"
                if len(catalog_related) > len(shown)
                else ""
            )
            lines.append(
                f"- **在以下疾病条目中出现过（医学百科参考，非适应证）：** "
                f"{', '.join(shown)}{suffix}"
            )
            detail_count += 1
        if detail_count == 0:
            lines.extend(
                [
                    "当前知识库仅确认了这个药品名称，还没有可展示的说明书字段或疾病关联。",
                    "",
                    "你可以继续提供药盒说明书，或明确询问副作用、禁忌、过敏风险等；"
                    "正式用药信息应以药品说明书及医生、药师意见为准。",
                ]
            )
        lines.extend(
            [
                "",
                "> 以上为药物知识信息，不构成处方；具体使用需结合完整药名、过敏史、感染部位及医生评估。",
            ]
        )
        return "\n".join(lines)
    if tool_name == "search_department" and isinstance(payload, dict):
        if not payload.get("found"):
            return payload.get("message", "未找到科室信息")
        dept = payload.get("department", "")
        diseases = payload.get("diseases", [])
        catalog_diseases = payload.get("catalogDiseases", [])
        depts = payload.get("departments", [])
        if dept:
            lines = [f"## {dept}"]
            if diseases:
                lines.append(f"\n**已审核疾病关系：** {', '.join(diseases)}")
            if catalog_diseases:
                shown = catalog_diseases[:15]
                suffix = (
                    f"…（等共 {len(catalog_diseases)} 项）"
                    if len(catalog_diseases) > len(shown)
                    else ""
                )
                lines.extend(
                    [
                        f"\n**目录分流参考：** {', '.join(shown)}{suffix}",
                        "",
                        "> 目录分流仅帮助选择初诊科室，不代表诊断或该科室一定收治；"
                        "完整列表可在“医学知识图谱”页查看，"
                        "并以具体医院挂号目录和分诊意见为准。",
                    ]
                )
            return "\n".join(lines)
        if depts:
            return f"## 可用科室\n\n{', '.join(depts)}"
        return "暂无科室信息"
    if tool_name == "list_patients" and isinstance(payload, dict):
        items = payload.get("content", [])
        total = payload.get("totalElements", len(items))
        if not items:
            return "当前没有患者数据。"
        lines = [f"找到 **{total}** 位患者：\n"]
        for i, p in enumerate(items, 1):
            name = p.get("name", "未知")
            no = p.get("patientNo", "")
            gender = p.get("gender", "")
            lines.append(f"**{i}. {name}**（{no}，{gender}）")
        return "\n".join(lines)
    if tool_name == "get_patient" and isinstance(payload, dict):
        name = payload.get("name", "未知")
        no = payload.get("patientNo", "")
        gender = payload.get("gender", "")
        phone = payload.get("phone", "无")
        blood = payload.get("bloodType", "未知")
        allergy = payload.get("allergyHistory", "无")
        return f"**患者 {name}**（{no}）\n- 性别：{gender}\n- 电话：{phone}\n- 血型：{blood}\n- 过敏史：{allergy}"
    if tool_name == "create_patient" and isinstance(payload, dict):
        name = payload.get("name", "未知")
        no = payload.get("patientNo", "")
        if not is_confirmed_write_result(tool_name, payload):
            return "患者写入结果缺少必要标识，无法确认本次写入。"
        return f"✅ 患者创建成功：**{name}**（{no}）"
    if tool_name == "create_prescription" and isinstance(payload, dict):
        no = payload.get("prescriptionNo", "")
        if not is_confirmed_write_result(tool_name, payload):
            return "处方写入结果缺少必要标识，无法确认本次写入。"
        return f"✅ 处方开具成功：**{no}**"
    if tool_name == "create_medical_record" and isinstance(payload, dict):
        no = payload.get("recordNo", "")
        if not is_confirmed_write_result(tool_name, payload):
            return "病历写入结果缺少必要标识，无法确认本次写入。"
        return f"✅ 病历创建成功：**{no}**"
    # Fallback: pretty JSON
    return orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode("utf-8")
