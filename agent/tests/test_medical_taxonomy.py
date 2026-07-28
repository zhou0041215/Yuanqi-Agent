from yuanqi_agent.medical_taxonomy import (
    ALIAS_TO_CANONICAL,
    DEPARTMENTS,
    NHC_DEPARTMENT_SOURCE,
    canonical_department,
)


def test_department_taxonomy_has_unique_names_and_codes() -> None:
    names = [item.name for item in DEPARTMENTS]
    codes = [item.code for item in DEPARTMENTS]
    assert len(names) == len(set(names))
    assert len(codes) == len(set(codes))
    assert NHC_DEPARTMENT_SOURCE.startswith("https://")


def test_all_aliases_are_unambiguous() -> None:
    expected_alias_count = sum(1 + len(item.aliases) for item in DEPARTMENTS)
    assert len(ALIAS_TO_CANONICAL) == expected_alias_count


def test_common_legacy_names_are_normalized() -> None:
    assert canonical_department("心内科") == "心血管内科"
    assert canonical_department("骨外科") == "骨科"
    assert canonical_department("传染科") == "感染科"
    assert canonical_department("儿科综合") == "儿科"
    assert canonical_department("不存在的科室") is None
