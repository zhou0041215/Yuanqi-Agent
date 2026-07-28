"""Canonical department taxonomy used by the medical knowledge graph.

The source dataset contains hospital-specific and historical department names.
This module maps them to stable user-facing names without claiming that the
underlying disease-to-department edge has received clinical review.
"""

from __future__ import annotations

from dataclasses import dataclass

NHC_DEPARTMENT_SOURCE = (
    "https://www.nhc.gov.cn/fzs/c100048/201808/"
    "afa9a6d10b9c4ed3ac36358fc20243ff.shtml"
)
CATALOG_SOURCE = "https://github.com/nuolade/disease-kb"


@dataclass(frozen=True)
class Department:
    name: str
    code: str
    parent: str
    aliases: tuple[str, ...] = ()


DEPARTMENTS = (
    Department("全科医疗科", "02", "综合", ("其他科室", "其他综合")),
    Department("内科", "03", "内科"),
    Department("呼吸内科", "03.01", "内科"),
    Department("消化内科", "03.02", "内科"),
    Department("神经内科", "03.03", "内科"),
    Department("心血管内科", "03.04", "内科", ("心内科",)),
    Department("血液内科", "03.05", "内科", ("血液科",)),
    Department("肾病科", "03.06", "内科", ("肾内科", "泌尿内科")),
    Department("内分泌科", "03.07", "内科"),
    Department("风湿免疫科", "03.08", "内科"),
    Department("外科", "04", "外科"),
    Department("普通外科", "04.01", "外科", ("普外科",)),
    Department("肝胆外科", "CUSTOM.HEPATOBILIARY", "外科"),
    Department("神经外科", "04.02", "外科"),
    Department("骨科", "04.03", "外科", ("骨外科",)),
    Department("泌尿外科", "04.04", "外科", ("男科",)),
    Department("胸外科", "04.05", "外科", ("心胸外科",)),
    Department("心脏大血管外科", "04.06", "外科"),
    Department("烧伤科", "04.07", "外科"),
    Department("整形外科", "04.08", "外科", ("整形美容科",)),
    Department("妇产科", "05", "妇产科"),
    Department("妇科", "05.01", "妇产科"),
    Department("产科", "05.02", "妇产科"),
    Department(
        "生殖健康与不孕症科",
        "05.06",
        "妇产科",
        ("不孕不育", "生殖健康"),
    ),
    Department("儿科", "07", "儿科", ("儿科综合", "小儿内科")),
    Department("小儿外科", "08", "儿科"),
    Department("眼科", "10", "五官"),
    Department("耳鼻咽喉科", "11", "五官", ("耳鼻喉科", "五官科")),
    Department("口腔科", "12", "五官"),
    Department("皮肤科", "13.01", "皮肤科", ("皮肤性病科",)),
    Department("性传播疾病科", "13.02", "皮肤科", ("性病科",)),
    Department("医疗美容科", "14", "外科"),
    Department("精神科", "15", "精神心理", ("精神心理科",)),
    Department("临床心理科", "15.06", "精神心理", ("心理科",)),
    Department("感染科", "16", "感染", ("传染科",)),
    Department("肝病科", "16.03", "感染", ("肝病",)),
    Department("肿瘤科", "19", "肿瘤"),
    Department("肿瘤内科", "19.01", "肿瘤"),
    Department("肿瘤外科", "19.02", "肿瘤"),
    Department("急诊医学科", "20", "急诊", ("急诊科",)),
    Department("康复医学科", "21", "康复", ("康复科",)),
    Department("中医科", "50", "中医", ("中医综合",)),
    Department("肛肠科", "50.11", "中医"),
    Department("营养科", "CUSTOM.NUTRITION", "综合", ("减肥",)),
    Department("医学遗传科", "CUSTOM.GENETICS", "综合", ("遗传病科",)),
)


ALIAS_TO_CANONICAL = {
    alias: department.name
    for department in DEPARTMENTS
    for alias in (department.name, *department.aliases)
}

EXPLICIT_DISEASE_ROUTES = {
    "糖尿病视网膜病变": ("眼科", "内分泌科"),
    "脑卒中": ("神经内科", "急诊医学科"),
    "肾衰竭": ("肾病科",),
    "肾脏疾病": ("肾病科",),
    "肝细胞癌": ("肝病科", "肿瘤科"),
}

INVALID_DISEASE_NAMES = frozenset({"无标题文档"})


def canonical_department(name: str) -> str | None:
    """Return the canonical name for a known source department."""

    return ALIAS_TO_CANONICAL.get(name.strip())
