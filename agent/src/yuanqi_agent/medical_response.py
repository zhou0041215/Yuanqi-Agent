from __future__ import annotations

import re
from typing import Any

_OFFICIAL_SOURCES = {
    "糖尿病": (
        "WHO：糖尿病事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/diabetes",
    ),
    "高血压": (
        "WHO：高血压事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/hypertension",
    ),
    "抑郁症": (
        "WHO：抑郁症事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/depression",
    ),
    "哮喘": (
        "WHO：哮喘事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/asthma",
    ),
    "乙型病毒性肝炎": (
        "WHO：乙型肝炎事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-b",
    ),
    "丙型病毒性肝炎": (
        "WHO：丙型肝炎事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-c",
    ),
    "慢性阻塞性肺疾病": (
        "WHO：慢性阻塞性肺疾病事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/chronic-obstructive-pulmonary-disease-(copd)",
    ),
    "癌症": (
        "WHO：癌症事实清单",
        "https://www.who.int/news-room/fact-sheets/detail/cancer",
    ),
}

_OFFICIAL_DISEASE_CARDS = {
    "糖尿病": {
        "summary": (
            "糖尿病是一类与胰岛素分泌不足或机体不能有效利用胰岛素有关的慢性疾病，"
            "主要表现为血糖持续升高。"
        ),
        "facts": [
            "常见表现包括明显口渴、排尿增多、视物模糊、疲劳和非主动体重下降；2 型糖尿病也可能长期症状不明显。",
            "长期血糖控制不佳可能损伤心脑血管、眼、肾、神经和足部。",
            "是否患有糖尿病需要依据规范血糖检查和临床评估，不能仅凭症状判断。",
        ],
        "topics": ["常见症状", "诊断检查", "并发症筛查", "日常管理", "应该挂什么科"],
        "sections": {
            "症状": ["明显口渴", "排尿增多", "视物模糊", "疲劳", "非主动体重下降"],
            "并发症": ["心脑血管损伤", "肾脏损伤", "视网膜损伤", "神经损伤", "足部溃疡"],
            "检查项目": ["规范血糖检查"],
            "所属科室": ["内分泌科"],
        },
    },
    "高血压": {
        "summary": "高血压是血管内压力持续偏高的慢性状况，多数患者没有明显症状。",
        "facts": [
            "测量血压是发现高血压的重要方式，不能凭头晕或头痛判断。",
            "长期控制不佳会增加心脏病、脑卒中和肾脏疾病风险。",
            "极高血压并伴胸痛、呼吸困难、意识异常或神经系统症状时需要立即就医。",
        ],
        "topics": ["如何规范测量", "生活方式管理", "并发症风险", "应该挂什么科"],
        "sections": {
            "症状": ["多数人没有明显症状；血压非常高时可能出现严重头痛、胸痛、头晕、呼吸困难或视力变化"],
            "并发症": ["心脏病", "脑卒中", "肾脏疾病"],
            "检查项目": ["规范、重复的血压测量"],
            "所属科室": ["心血管内科"],
        },
    },
    "抑郁症": {
        "summary": "抑郁症是以持续情绪低落或失去兴趣、愉悦感为核心表现的常见精神障碍。",
        "facts": [
            "抑郁发作不同于日常短暂情绪变化，通常持续影响学习、工作、家庭或社交功能。",
            "可能伴随注意力下降、睡眠或食欲改变、疲劳、过度内疚和绝望感。",
            "抑郁症有有效治疗方法；出现自伤或自杀想法时应立即寻求紧急帮助。",
        ],
        "topics": ["常见表现", "何时就医", "心理治疗", "自伤风险"],
        "sections": {
            "症状": ["持续情绪低落", "兴趣或愉悦感减退", "注意力下降", "睡眠改变", "食欲或体重改变", "明显疲劳"],
            "所属科室": ["精神科", "心理科"],
        },
    },
    "哮喘": {
        "summary": "哮喘是与气道炎症及气道周围肌肉收紧有关的慢性肺部疾病。",
        "facts": [
            "症状可以时轻时重，并可能在夜间、运动或接触诱因后加重。",
            "类似症状也可能由其他疾病引起，需要专业人员评估。",
            "规范治疗能够帮助控制症状并降低严重发作风险。",
        ],
        "topics": ["常见症状", "常见诱因", "何时急诊", "应该挂什么科"],
        "sections": {
            "症状": ["咳嗽", "喘鸣", "气短", "胸闷"],
            "所属科室": ["呼吸内科"],
        },
    },
    "乙型病毒性肝炎": {
        "summary": "乙型肝炎是乙型肝炎病毒引起的肝脏感染，可以表现为急性或慢性感染。",
        "facts": [
            "许多新近感染者没有症状，不能依靠症状排除感染。",
            "慢性感染可能进展为肝硬化或肝细胞癌。",
            "是否感染和是否需要治疗必须结合规范血液检查及专业评估。",
        ],
        "topics": ["传播方式", "检查项目", "疫苗预防", "长期随访"],
        "sections": {
            "症状": ["黄疸", "尿色深", "明显疲劳", "恶心", "呕吐", "腹痛"],
            "并发症": ["肝硬化", "肝细胞癌"],
            "检查项目": ["乙肝血清学检查"],
            "所属科室": ["感染科", "肝病科"],
        },
    },
    "丙型病毒性肝炎": {
        "summary": "丙型肝炎是丙型肝炎病毒引起、主要经受感染血液传播的肝脏感染。",
        "facts": [
            "不少感染者早期没有明显症状。",
            "慢性感染可能导致肝硬化或肝癌。",
            "丙肝抗体阳性后还需要核酸检测确认当前是否存在感染。",
        ],
        "topics": ["传播方式", "抗体与核酸检查", "能否治愈", "应该挂什么科"],
        "sections": {
            "症状": ["疲劳", "食欲下降", "恶心", "腹痛", "尿色深", "黄疸"],
            "并发症": ["肝硬化", "肝细胞癌"],
            "检查项目": ["丙肝抗体检查", "丙肝病毒核酸检查"],
            "所属科室": ["感染科", "肝病科"],
        },
    },
    "慢性阻塞性肺疾病": {
        "summary": "慢性阻塞性肺疾病会造成持续气流受限和长期呼吸问题。",
        "facts": [
            "常见表现是气短、慢性咳嗽和咳痰。",
            "吸烟及长期接触空气污染、粉尘或烟雾是重要风险因素。",
            "诊断需要结合症状、暴露史和肺功能等资料，不能只凭咳嗽判断。",
        ],
        "topics": ["常见症状", "肺功能检查", "戒烟", "急性加重"],
        "sections": {
            "症状": ["气短", "慢性咳嗽", "咳痰"],
            "检查项目": ["肺功能检查"],
            "所属科室": ["呼吸内科"],
        },
    },
    "癌症": {
        "summary": "癌症是异常细胞失去正常控制、侵入邻近组织并可能转移的一大类疾病。",
        "facts": [
            "癌症不是单一疾病，不同部位和病理类型的检查与治疗差异很大。",
            "任何单一症状都不能直接证明患有癌症。",
            "许多癌症在早期发现并得到适当治疗时有更好的治疗机会。",
        ],
        "topics": ["具体癌种", "危险因素", "筛查", "检查结果"],
        "sections": {},
    },
}

_EMERGENCY_PHRASES = (
    "剧烈胸痛",
    "严重呼吸困难",
    "意识不清",
    "突然昏厥",
    "单侧肢体无力",
    "口角歪斜",
    "大量呕血",
    "大量便血",
    "持续抽搐",
    "想自杀",
    "自杀计划",
    "口唇发紫",
    "严重气短",
)


def emergency_guidance(message: str) -> str | None:
    matches = [phrase for phrase in _EMERGENCY_PHRASES if phrase in message]
    if not matches:
        return None
    return (
        "你描述的情况包含需要立即处理的危险信号："
        f"**{'、'.join(matches)}**。请立即拨打当地急救电话或前往急诊，"
        "不要等待在线回答，也不要自行驾车。如果身边有人，请让其陪同并携带现用药物清单。"
    )


def build_report_followup_answer(
    message: str,
    history: list[dict[str, Any]],
) -> str | None:
    report_text = next(
        (
            str(item.get("content") or "")
            for item in reversed(history)
            if item.get("role") == "assistant"
            and "## 检查报告解读" in str(item.get("content") or "")
        ),
        None,
    )
    if report_text is None or not _looks_like_report_context_reply(message):
        return None

    findings = _markdown_report_findings(report_text)
    high = [item for item, _result, flag in findings if "偏高" in flag or "↑" in flag]
    low = [item for item, _result, flag in findings if "偏低" in flag or "↓" in flag]
    synthetic = "合成演示报告" in report_text or "演示数据提示" in report_text
    lines = [
        *(
            [
                "> **演示数据提示：** 当前文件为合成演示报告，以下内容仅用于验证分析流程，"
                "不可用于真实诊疗。",
                "",
            ]
            if synthetic
            else []
        ),
        "### 已合并本次补充信息",
        "",
        f"- **本次情况：** {_extract_context_sentence(message, ('体检', '复查', '就诊'))}",
        f"- **主要不适：** {_symptom_context(message)}",
        f"- **既往疾病：** {_history_context(message)}",
        f"- **当前用药：** {_medication_context(message)}",
    ]
    if findings:
        lines.extend(["", "### 异常项目分层解读", ""])
        interpretations = _interpret_report_findings(findings)
        lines.extend(interpretations)
        if not interpretations:
            if high:
                lines.append(f"- 标记偏高：{'、'.join(high)}")
            if low:
                lines.append(f"- 标记偏低：{'、'.join(low)}")
        lines.append(
            "- 所有“偏高/偏低”首先是对报告原文的复述；单次结果不能独立确诊。"
        )
    lines.extend(
        [
            "",
            "### 下一步建议",
            "",
            "- 不要根据本次自动解读自行停用、加量或更换氨氯地平。"
            "如果正在按有效处方服用，请遵照原开药医生方案；若出现明显头晕、晕厥、"
            "血压过低或其他不适，应及时联系医生。",
            "- 补充近期规范测量的家庭血压和心率记录，并携带原始报告、既往检查结果"
            "到体检医生或全科/心血管内科复核。",
            "- 优先确认空腹血糖和血红蛋白异常，再由医生结合情况复核血常规、肝功能和血脂。",
            "- 如果出现胸痛、严重呼吸困难、意识异常、单侧肢体无力等危险症状，立即急诊就医。",
            "",
            "### 参考依据",
            "",
            "- [WHO：空腹血糖诊断阈值与确认原则]"
            "(https://cdn.who.int/media/docs/default-source/searo/ncd/ncd-flip-charts/1.-diabetes-24-04-19.pdf)",
            "- [NHLBI：贫血诊断与血红蛋白评估]"
            "(https://www.nhlbi.nih.gov/health/anemia/diagnosis)",
            "- [NIDDK：肝酶升高的临床评估]"
            "(https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/diagnosis)",
            "",
            "### 边界",
            "",
            "- 本回答将当前补充信息与上一份报告合并整理，不构成诊断或处方。",
        ]
    )
    return "\n".join(lines)


_REPORT_FOLLOWUP_QUESTIONS = {
    "blood_pressure": "最近一周早晚的家庭血压和心率大约是多少？测量前是否静坐了几分钟？",
    "glucose": "这次抽血前是否至少空腹 8 小时？以前的空腹血糖或糖化血红蛋白结果大约是多少？",
    "anemia": "既往是否有贫血，近期有没有容易疲劳、心慌、黑便，或其他可能失血的情况？",
    "infection": "体检前后是否有发热、咳嗽、咽痛、尿路不适，或近期感染和明显熬夜、剧烈运动？",
    "liver": "近期是否饮酒，或使用过中草药、止痛药及其他可能影响肝功能的药物？",
    "lipids": "这次血脂是否为空腹检查？是否吸烟，家族中有没有较早发生心梗或脑卒中的情况？",
}


def apply_report_dialogue(
    answer: str,
    acknowledgement: str | None,
    focus: str | None,
) -> str:
    """Add a bounded conversational turn without changing locked facts."""
    safe_acknowledgement = _safe_dialogue_acknowledgement(acknowledgement)
    locked_focus = _locked_report_focus(answer)
    # The rule layer owns clinical priority. The model may choose the focus
    # only when no priority can be derived from the locked analysis.
    selected_focus = locked_focus or focus or "blood_pressure"
    question = _REPORT_FOLLOWUP_QUESTIONS.get(
        selected_focus,
        _REPORT_FOLLOWUP_QUESTIONS["blood_pressure"],
    )

    intro = safe_acknowledgement or (
        "了解了。你目前没有明显不适，这次属于年度体检；我先按报告里的异常程度帮你排一下优先级。"
    )
    dialogue = [
        intro,
        "",
        answer,
        "",
        "### 我接下来想先确认一件事",
        "",
        question,
        "",
        "你可以直接按实际情况回答，我会继续结合上一份报告分析，不需要重新上传。",
    ]
    return "\n".join(dialogue)


def _safe_dialogue_acknowledgement(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split()).strip()
    unsafe_markers = (
        "确诊",
        "诊断为",
        "建议服用",
        "应该服用",
        "停药",
        "加量",
        "减量",
        "换药",
        "毫克",
        "mg",
    )
    if (
        not text
        or len(text) < 6
        or len(text) > 80
        or re.search(r"\d", text)
        or re.search(r"[\u4e00-\u9fff]", text) is None
    ):
        return None
    if any(marker in text for marker in unsafe_markers):
        return None
    return text


def _locked_report_focus(answer: str) -> str | None:
    priorities = (
        ("空腹血糖", "glucose"),
        ("血红蛋白", "anemia"),
        ("白细胞计数", "infection"),
        ("丙氨酸氨基转移酶", "liver"),
        ("总胆固醇", "lipids"),
    )
    return next((focus for marker, focus in priorities if marker in answer), None)


def _interpret_report_findings(
    findings: list[tuple[str, str, str]],
) -> list[str]:
    indexed = {item: (result, flag) for item, result, flag in findings}
    lines: list[str] = []
    glucose = indexed.get("空腹血糖")
    if glucose and _numeric_value(glucose[0]) is not None:
        value = _numeric_value(glucose[0])
        if value is not None and value >= 7.0:
            lines.append(
                f"- **优先确认｜空腹血糖 {glucose[0]}：** 如果采血前确实空腹至少8小时，"
                "该数值达到 WHO 使用的糖尿病诊断阈值；无明显症状时不能凭单次结果确诊，"
                "应由医生安排复测空腹血糖和/或糖化血红蛋白等确认。"
            )
    hemoglobin = indexed.get("血红蛋白")
    if hemoglobin and ("偏低" in hemoglobin[1] or "↓" in hemoglobin[1]):
        lines.append(
            f"- **优先确认｜血红蛋白 {hemoglobin[0]}：** 低于报告参考范围，提示需要评估贫血；"
            "通常需结合完整血常规指标，并由医生根据情况评估铁蛋白、失血或其他原因。"
        )
    white_cells = indexed.get("白细胞计数")
    if white_cells and ("偏高" in white_cells[1] or "↑" in white_cells[1]):
        lines.append(
            f"- **结合症状｜白细胞计数 {white_cells[0]}：** 可见于感染、炎症、应激等多种情况；"
            "目前无明显不适，仍需结合分类计数、近期感染史和必要时复查判断。"
        )
    alt = indexed.get("丙氨酸氨基转移酶")
    if alt and ("偏高" in alt[1] or "↑" in alt[1]):
        lines.append(
            f"- **进一步评估｜丙氨酸氨基转移酶 {alt[0]}：** 表示肝酶升高，但不能单独判断病因；"
            "需结合其他肝功能指标、饮酒、药物和代谢因素评估。"
        )
    lipid_items = [
        item for item in ("总胆固醇", "甘油三酯")
        if item in indexed and ("偏高" in indexed[item][1] or "↑" in indexed[item][1])
    ]
    if lipid_items:
        values = "、".join(f"{item} {indexed[item][0]}" for item in lipid_items)
        lines.append(
            f"- **心血管风险评估｜{values}：** 需要结合是否空腹、LDL-C、HDL-C、血压、"
            "吸烟和家族史进行整体评估，不能仅凭这两项决定是否用药。"
        )
    return lines


def _numeric_value(result: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", result)
    return float(match.group()) if match else None


def _looks_like_report_context_reply(message: str) -> bool:
    context_markers = ("本次", "体检", "主要不适", "既往", "目前", "正在服用", "没有服用")
    return sum(marker in message for marker in context_markers) >= 2


def _markdown_report_findings(report_text: str) -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    for line in report_text.splitlines():
        if not line.startswith("|") or "---" in line or "项目" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        findings.append((cells[0], cells[1], cells[3]))
    return findings


def _extract_context_sentence(message: str, markers: tuple[str, ...]) -> str:
    sentences = re.split(r"[。；;\n]", message)
    match = next((sentence.strip() for sentence in sentences if any(m in sentence for m in markers)), "")
    return match or "用户已补充，但未能可靠结构化提取"


def _symptom_context(message: str) -> str:
    if any(marker in message for marker in ("没有明显不适", "无明显不适", "没有不适")):
        return "目前无明显不适（用户自述）"
    return _extract_context_sentence(message, ("不适", "症状"))


def _history_context(message: str) -> str:
    match = re.search(r"既往(?:有|患有|确诊)([^，。；;\n]+)", message)
    return match.group(1).strip() if match else "未明确"


def _medication_context(message: str) -> str:
    match = re.search(r"目前(?:每天)?(?:服用|使用)([^，。；;\n]+)", message)
    return match.group(1).strip() if match else "未明确"


def build_disease_answer(
    message: str,
    payload: dict[str, Any],
) -> str:
    if not payload.get("found", True):
        return str(payload.get("message") or "未找到相关疾病信息")
    if payload.get("matchType") == "fuzzy":
        diseases = [
            str(item).strip()
            for item in payload.get("diseases", [])
            if str(item).strip()
        ]
        lines = ["### 你可能想查询", ""]
        lines.extend(f"- {item}" for item in diseases)
        lines.append("\n请补充完整疾病名称后再查询，名称相近不代表医学上相同。")
        return "\n".join(lines)

    disease = dict(payload.get("disease") or {})
    name = str(disease.get("name") or "该疾病")
    relations = dict(payload.get("relations") or {})
    routing_departments = [
        str(item).strip()
        for item in payload.get("routingDepartments", [])
        if str(item).strip()
    ]
    uses_catalog_routing = bool(
        routing_departments and not relations.get("所属科室")
    )
    if uses_catalog_routing:
        relations["所属科室"] = routing_departments
    reviewed = bool(payload.get("relationsReviewed")) or str(
        payload.get("knowledgeStatus") or ""
    ).upper() in {"PUBLISHED", "APPROVED"}
    lines = [f"\n\n### 查询对象\n\n你查询的是 **{name}**。"]
    official_card = _OFFICIAL_DISEASE_CARDS.get(name)

    # 简要认识：优先权威卡片；否则用目录简介（标注为参考）。
    if official_card and _is_general_entity_query(message, name):
        lines.extend(["\n### 简要认识\n", official_card["summary"]])
        lines.extend(f"- {fact}" for fact in official_card["facts"])
        lines.append("\n### 你可以继续问\n")
        lines.append("、".join(official_card["topics"]))
    else:
        summary = str(disease.get("summary") or "").strip()
        if summary:
            lines.extend(["\n### 简要认识\n", summary])
        lines.extend(
            f"- **{label}：** {disease[key]}"
            for key, label in (("病因", "病因"), ("高发人群", "高发人群"))
            if disease.get(key)
        )

    requested = _requested_section(message, relations, official_card)
    if requested:
        label, values = requested
        lines.append(f"\n### {label}\n")
        lines.extend(f"- {value}" for value in values)
    elif not official_card:
        for label, values in _overview_sections(relations):
            lines.append(f"\n### {label}\n")
            lines.extend(f"- {value}" for value in values)

    if "并发症" in message:
        lines.append(
            "\n这些项目代表需要关注或筛查的风险，并不表示每位患者都会发生。"
            "是否已经出现并发症，需要结合病史、体格检查和相应检查判断。"
        )
    elif any(marker in message for marker in ("挂什么科", "看哪个科", "科室")):
        lines.append("\n可优先选择上述专科；医院没有细分专科时，可先到全科或普通内科分诊。")
        if uses_catalog_routing:
            lines.append(
                "\n该分流来自标准化疾病目录，不等同于已审核的诊疗结论，"
                "请以具体医院挂号目录和分诊意见为准。"
            )
    elif any(marker in message for marker in ("检查", "筛查")):
        lines.append("\n检查项目应由医生根据诊断阶段和个人风险选择，不建议自行打包检查。")

    questions = (
        []
        if _is_general_entity_query(message, name)
        else _follow_up_questions(name, message)
    )
    if questions:
        lines.append("\n### 为了进一步判断，建议补充\n")
        lines.extend(f"- {question}" for question in questions)

    source = _OFFICIAL_SOURCES.get(name)
    lines.append("\n### 证据与边界\n")
    if source:
        lines.append(f"- [{source[0]}]({source[1]})（权威来源）")
    elif reviewed and disease.get("sourceUri"):
        title = str(disease.get("sourceTitle") or "权威来源")
        lines.append(f"- [{title}]({disease['sourceUri']})（权威来源）")
    lines.append(
        "- 上述疾病关系含内部医学百科（disease-kb 开源目录）内容，**未经逐条人工审核**，"
        "仅供参考、不作诊断依据；完整关系可在“医学知识图谱”页查看。"
    )
    lines.append("- 本回答用于医学信息与就医决策支持，不构成诊断或处方。")
    return "\n".join(lines)


def _is_general_entity_query(message: str, name: str) -> bool:
    normalized = message.strip(" \n。！？?")
    return normalized == name or any(
        marker in normalized
        for marker in ("是什么", "介绍一下", "了解一下", "简单介绍")
    )


def _requested_section(
    message: str,
    relations: dict[str, Any],
    official_card: dict[str, Any] | None = None,
) -> tuple[str, list[str]] | None:
    mapping = (
        (("并发症",), "并发症"),
        (("挂什么科", "看哪个科", "科室"), "所属科室"),
        (("检查", "筛查"), "检查项目"),
        (("忌口", "忌吃", "不能吃", "不宜吃"), "忌吃"),
        (("宜吃", "吃什么好", "饮食", "食疗"), "宜吃"),
        (("怎么治", "如何治", "治疗方式", "治疗方法", "能治好"), "治疗方式"),
        (("症状", "表现"), "症状"),
    )
    for markers, label in mapping:
        if any(marker in message for marker in markers):
            values = [str(value) for value in relations.get(label, []) if str(value).strip()]
            if not values and official_card:
                values = [
                    str(value)
                    for value in dict(official_card.get("sections") or {}).get(label, [])
                    if str(value).strip()
                ]
            return (label, values or ["当前知识库没有足够可靠的数据，请由医生进一步评估"])
    return None


# General "什么是 X" questions name no specific section, so show a compact
# overview instead of dropping every relation the graph just returned.
_OVERVIEW_SECTIONS = ("症状", "所属科室", "检查项目", "治疗方式")


def _overview_sections(relations: dict[str, Any]) -> list[tuple[str, list[str]]]:
    overview: list[tuple[str, list[str]]] = []
    for label in _OVERVIEW_SECTIONS:
        values = [str(value).strip() for value in relations.get(label, []) if str(value).strip()]
        if values:
            overview.append((label, values[:8]))
    return overview


def _follow_up_questions(name: str, message: str) -> list[str]:
    if "并发症" in message and name == "糖尿病":
        return [
            "糖尿病类型、确诊时间及最近一次糖化血红蛋白（HbA1c）",
            "近期肾功能、尿白蛋白/肌酐比值和眼底检查结果",
            "是否有足部破损、麻木、视力变化、胸痛或活动后气短",
        ]
    if name == "高血压":
        return [
            "不同日期规范测量的家庭血压记录",
            "是否合并糖尿病、肾病、冠心病、脑卒中或妊娠",
            "目前使用的药物、过敏史及近期肾功能和血钾结果",
        ]
    return [
        "症状何时开始、持续多久以及严重程度",
        "既往疾病、过敏史和当前使用的药物",
        "已经完成的检查及异常结果",
    ]
