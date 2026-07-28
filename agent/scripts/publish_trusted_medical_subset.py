"""Publish a small source-backed Neo4j subset without deleting legacy data.

Every published node/relationship carries an authoritative HTTPS source and
governance metadata (see docs/TRUSTED_MEDICAL_QA.md). Diseases are sourced from
World Health Organization fact sheets. Drug facts are loaded from the versioned
``trusted_drugs.v1.json`` resource; label warnings use official DailyMed labels,
while general class facts use the WHO Model List of Essential Medicines.

This starter dataset is general health-education content. Clinical, pharmacy and
compliance sign-off is still required before production display.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from neo4j import AsyncGraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yuanqi_agent.trusted_medical_knowledge import get_trusted_drug_catalog

WHO_FACT_SHEET_TITLE = "World Health Organization fact sheet"


@dataclass(frozen=True)
class DiseaseSeed:
    name: str
    summary: str
    source_uri: str
    symptoms: tuple[str, ...] = ()
    complications: tuple[str, ...] = ()
    departments: tuple[str, ...] = ()
    exams: tuple[str, ...] = ()


SEEDS = (
    DiseaseSeed(
        "糖尿病",
        "与胰岛素分泌不足或机体不能有效利用胰岛素有关的慢性疾病。",
        "https://www.who.int/news-room/fact-sheets/detail/diabetes",
        ("明显口渴", "排尿增多", "视物模糊", "疲劳", "非主动体重下降"),
        ("心肌梗死", "脑卒中", "肾功能衰竭", "糖尿病视网膜病变", "糖尿病足"),
        ("内分泌科",),
        ("血糖检查",),
    ),
    DiseaseSeed(
        "高血压",
        "以血压持续升高为特征的慢性状况，多数患者没有明显症状。",
        "https://www.who.int/news-room/fact-sheets/detail/hypertension",
        ("严重头痛", "胸痛", "头晕", "呼吸困难", "视力变化"),
        ("心脏病", "脑卒中", "肾脏疾病"),
        ("心血管内科",),
        ("血压测量",),
    ),
    DiseaseSeed(
        "抑郁症",
        "以持续情绪低落或失去兴趣和愉悦感为核心表现的常见精神障碍。",
        "https://www.who.int/news-room/fact-sheets/detail/depression",
        ("情绪低落", "兴趣减退", "注意力下降", "睡眠改变", "明显疲劳", "自杀想法"),
        (),
        ("精神科", "临床心理科"),
        (),
    ),
    DiseaseSeed(
        "哮喘",
        "与气道炎症及气道周围肌肉收紧有关的慢性肺部疾病。",
        "https://www.who.int/news-room/fact-sheets/detail/asthma",
        ("咳嗽", "喘鸣", "气短", "胸闷"),
        (),
        ("呼吸内科",),
        ("肺功能检查",),
    ),
    DiseaseSeed(
        "乙型病毒性肝炎",
        "乙型肝炎病毒引起的肝脏感染，可以是急性或慢性。",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-b",
        ("黄疸", "尿色深", "明显疲劳", "恶心", "呕吐", "腹痛"),
        ("肝硬化", "肝细胞癌"),
        ("感染科", "肝病科"),
        ("乙肝血清学检查",),
    ),
    DiseaseSeed(
        "丙型病毒性肝炎",
        "丙型肝炎病毒引起、主要经受感染血液传播的肝脏感染。",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-c",
        ("明显疲劳", "食欲下降", "恶心", "腹痛", "尿色深", "黄疸"),
        ("肝硬化", "肝细胞癌"),
        ("感染科", "肝病科"),
        ("丙肝抗体检查", "丙肝病毒核酸检查"),
    ),
    DiseaseSeed(
        "慢性阻塞性肺疾病",
        "造成持续气流受限和呼吸问题的慢性肺部疾病。",
        "https://www.who.int/news-room/fact-sheets/detail/chronic-obstructive-pulmonary-disease-(copd)",
        ("气短", "慢性咳嗽", "咳痰"),
        (),
        ("呼吸内科",),
        ("肺功能检查",),
    ),
    DiseaseSeed(
        "癌症",
        "异常细胞失去正常控制、侵入邻近组织并可能发生转移的一大类疾病。",
        "https://www.who.int/news-room/fact-sheets/detail/cancer",
    ),
    # ── 以下为基于 WHO 实况报道扩充的常见病一般健康教育内容 ──────────────
    DiseaseSeed(
        "脑卒中",
        "因脑部供血中断或血管破裂导致脑组织受损的急性疾病，是致残和致死的重要原因。",
        "https://www.who.int/news-room/fact-sheets/detail/stroke",
        ("突发面部或肢体无力", "言语不清", "单眼或双眼视力障碍", "剧烈头痛", "行走困难或眩晕"),
        ("肢体瘫痪", "吞咽困难", "认知障碍"),
        ("神经内科", "急诊医学科"),
        ("头颅CT检查", "头颅磁共振检查"),
    ),
    DiseaseSeed(
        "冠心病",
        "冠状动脉供血不足引起的心脏疾病，属于心血管疾病，是全球主要死因之一。",
        "https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds)",
        ("胸痛", "胸闷", "气短", "心悸"),
        ("心肌梗死", "心力衰竭"),
        ("心血管内科",),
        ("心电图检查", "冠状动脉造影"),
    ),
    DiseaseSeed(
        "结核病",
        "主要由结核分枝杆菌引起、通常侵犯肺部的传染病，可经空气传播。",
        "https://www.who.int/news-room/fact-sheets/detail/tuberculosis",
        ("持续咳嗽", "咳血", "胸痛", "乏力", "消瘦", "夜间盗汗", "发热"),
        (),
        ("感染科", "呼吸内科"),
        ("痰涂片检查", "胸部X线检查"),
    ),
    DiseaseSeed(
        "肺炎",
        "由感染引起的肺部急性炎症，是儿童和老年人的重要健康威胁。",
        "https://www.who.int/news-room/fact-sheets/detail/pneumonia",
        ("发热", "咳嗽", "咳痰", "呼吸急促", "胸痛"),
        (),
        ("呼吸内科",),
        ("胸部X线检查", "血常规检查"),
    ),
    DiseaseSeed(
        "流行性感冒",
        "由流感病毒引起的急性呼吸道传染病，具有季节性流行特点。",
        "https://www.who.int/news-room/fact-sheets/detail/influenza-(seasonal)",
        ("发热", "咳嗽", "咽痛", "肌肉酸痛", "头痛", "乏力"),
        (),
        ("呼吸内科", "感染科"),
        (),
    ),
    DiseaseSeed(
        "艾滋病",
        "由人类免疫缺陷病毒（HIV）感染导致免疫系统受损的慢性传染病。",
        "https://www.who.int/news-room/fact-sheets/detail/hiv-aids",
        ("发热", "咽痛", "淋巴结肿大", "乏力", "体重下降"),
        ("机会性感染",),
        ("感染科",),
        ("HIV抗体检测",),
    ),
    DiseaseSeed(
        "疟疾",
        "由疟原虫引起、经受感染的按蚊叮咬传播的急性传染病。",
        "https://www.who.int/news-room/fact-sheets/detail/malaria",
        ("发热", "寒战", "头痛", "出汗", "乏力"),
        (),
        ("感染科",),
        ("血涂片检查",),
    ),
    DiseaseSeed(
        "麻疹",
        "由麻疹病毒引起、传染性很强的急性呼吸道传染病，可通过疫苗预防。",
        "https://www.who.int/news-room/fact-sheets/detail/measles",
        ("发热", "咳嗽", "流涕", "结膜充血", "皮疹"),
        (),
        ("感染科", "儿科"),
        (),
    ),
    DiseaseSeed(
        "登革热",
        "由登革病毒引起、经蚊媒传播的急性传染病，多见于热带和亚热带地区。",
        "https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue",
        ("高热", "剧烈头痛", "眼眶痛", "肌肉和关节疼痛", "皮疹"),
        (),
        ("感染科",),
        (),
    ),
    DiseaseSeed(
        "痴呆",
        "以认知功能进行性下降为特征、影响日常生活能力的一组综合征。",
        "https://www.who.int/news-room/fact-sheets/detail/dementia",
        ("记忆力下降", "语言障碍", "判断力减退", "情绪或行为改变"),
        (),
        ("神经内科", "精神科"),
        (),
    ),
    DiseaseSeed(
        "癫痫",
        "以反复发作为特征的慢性脑部疾病，发作由脑内异常电活动引起。",
        "https://www.who.int/news-room/fact-sheets/detail/epilepsy",
        ("反复发作性抽搐", "意识丧失", "感觉异常", "一时性行为改变"),
        (),
        ("神经内科",),
        ("脑电图检查",),
    ),
    DiseaseSeed(
        "帕金森病",
        "以运动症状为主的进行性神经系统退行性疾病。",
        "https://www.who.int/news-room/fact-sheets/detail/parkinson-disease",
        ("静止性震颤", "运动迟缓", "肌肉僵直", "姿势与平衡障碍"),
        (),
        ("神经内科",),
        (),
    ),
    DiseaseSeed(
        "肥胖症",
        "以体内脂肪过度积累、可能损害健康为特征的慢性状况。",
        "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        ("体重过度增加",),
        ("糖尿病", "高血压", "心脏病"),
        ("内分泌科", "营养科"),
        ("体重指数测量",),
    ),
    DiseaseSeed(
        "甲型病毒性肝炎",
        "由甲型肝炎病毒引起、主要经污染的食物或水传播的肝脏感染。",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-a",
        ("发热", "乏力", "食欲下降", "恶心", "腹痛", "黄疸", "尿色深"),
        (),
        ("感染科", "肝病科"),
        ("甲肝抗体检查",),
    ),
    DiseaseSeed(
        "丁型病毒性肝炎",
        "由丁型肝炎病毒引起、需在乙型肝炎病毒感染基础上才能复制的肝脏感染。",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-d",
        ("黄疸", "乏力", "恶心", "腹痛"),
        ("肝硬化", "肝细胞癌"),
        ("感染科", "肝病科"),
        ("丁肝血清学检查",),
    ),
    DiseaseSeed(
        "戊型病毒性肝炎",
        "由戊型肝炎病毒引起、主要经污染水源传播的肝脏感染。",
        "https://www.who.int/news-room/fact-sheets/detail/hepatitis-e",
        ("黄疸", "乏力", "食欲下降", "恶心", "腹痛", "尿色深"),
        (),
        ("感染科", "肝病科"),
        ("戊肝抗体检查",),
    ),
)


TRUSTED_DRUG_CATALOG = get_trusted_drug_catalog()
DRUG_SEEDS = tuple(TRUSTED_DRUG_CATALOG.drugs)

RELATIONS = {
    "symptoms": ("Symptom", "HAS_SYMPTOM"),
    "complications": ("Disease", "COMPLICATION"),
    "departments": ("Department", "BELONGS_TO"),
    "exams": ("Exam", "REQUIRES_EXAM"),
}


async def publish(uri: str, username: str, password: str, database: str) -> None:
    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
    try:
        async with driver.session(database=database) as session:
            for seed in SEEDS:
                await session.run(
                    """
                    MERGE (d:Disease {name: $name})
                    SET d.entityKey = 'Disease:' + $name,
                        d.summary = $summary,
                        d.reviewStatus = 'PUBLISHED',
                        d.sourceTitle = $source_title,
                        d.sourceUri = $source_uri,
                        d.knowledgeVersion = 1,
                        d.reviewedAt = datetime(),
                        d.reviewedBy = 'trusted-starter-dataset'
                    """,
                    name=seed.name,
                    summary=seed.summary,
                    source_uri=seed.source_uri,
                    source_title=WHO_FACT_SHEET_TITLE,
                )
                for field, (label, relation) in RELATIONS.items():
                    for neighbor_name in getattr(seed, field):
                        await session.run(
                            f"""
                            MATCH (d:Disease {{name: $disease}})
                            MERGE (n:{label} {{name: $neighbor}})
                            SET n.entityKey = $entity_key,
                                n.reviewStatus = 'PUBLISHED',
                                n.sourceTitle = $source_title,
                                n.sourceUri = $source_uri,
                                n.knowledgeVersion = 1,
                                n.reviewedAt = datetime(),
                                n.reviewedBy = 'trusted-starter-dataset'
                            MERGE (d)-[r:{relation}]->(n)
                            SET r.reviewStatus = 'PUBLISHED',
                                r.reviewed = true,
                                r.sourceTitle = $source_title,
                                r.sourceUri = $source_uri,
                                r.reviewedAt = datetime(),
                                r.reviewedBy = 'trusted-starter-dataset'
                            """,
                            disease=seed.name,
                            neighbor=neighbor_name,
                            entity_key=f"{label}:{neighbor_name}",
                            source_uri=seed.source_uri,
                            source_title=WHO_FACT_SHEET_TITLE,
                        )

            # Governed drug attributes loaded from the versioned trusted resource.
            for drug in DRUG_SEEDS:
                await session.run(
                    """
                    MERGE (r:Drug {name: $name})
                    SET r.entityKey = 'Drug:' + $name,
                        r.category = $category,
                        r.summary = $summary,
                        r.warnings = $warnings,
                        r.reviewStatus = 'PUBLISHED',
                        r.sourceTitle = $source_title,
                        r.sourceUri = $source_uri,
                        r.knowledgeVersion = $knowledge_version,
                        r.reviewedAt = datetime($curated_at),
                        r.reviewedBy = $curated_by,
                        r.releaseStatus = $release_status
                    """,
                    name=drug.name,
                    category=drug.category,
                    summary=drug.summary,
                    warnings=drug.warnings,
                    source_uri=str(drug.source_uri),
                    source_title=drug.source_title,
                    knowledge_version=TRUSTED_DRUG_CATALOG.knowledge_version,
                    curated_at=TRUSTED_DRUG_CATALOG.curated_at.isoformat(),
                    curated_by=TRUSTED_DRUG_CATALOG.curated_by,
                    release_status=TRUSTED_DRUG_CATALOG.release_status,
                )
        print(
            f"Published {len(SEEDS)} governed diseases, their reviewed relationships, "
            f"and {len(DRUG_SEEDS)} drug-class entries."
        )
    finally:
        await driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="neo4j://localhost:17687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", default="yuanqi-local")
    parser.add_argument("--database", default="neo4j")
    args = parser.parse_args()
    asyncio.run(publish(args.uri, args.username, args.password, args.database))


if __name__ == "__main__":
    main()
