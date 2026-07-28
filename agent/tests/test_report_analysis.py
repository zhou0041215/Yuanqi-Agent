import pytest

from yuanqi_agent.errors import AgentError
from yuanqi_agent.report_analysis import analyze_report


def test_text_report_extracts_only_explicit_flags() -> None:
    result = analyze_report(
        "blood.txt",
        "text/plain",
        "血常规\n白细胞 12.5 10^9/L ↑ 3.5-9.5\n血红蛋白 105 g/L ↓ 115-150\n".encode(),
    )

    assert result.file_name == "blood.txt"
    assert [item.flag for item in result.findings] == ["high", "low"]
    assert "2 个带有" in result.summary
    assert any("不能独立用于诊断" in warning for warning in result.warnings)


def test_report_rejects_unsupported_type() -> None:
    with pytest.raises(AgentError) as caught:
        analyze_report("archive.zip", "application/zip", b"not a report")

    assert caught.value.code == "UNSUPPORTED_REPORT_TYPE"


def test_report_does_not_infer_abnormality_without_marker() -> None:
    result = analyze_report("lab.csv", "text/csv", "项目 结果\n血糖 6.1 mmol/L\n".encode())

    assert result.findings[0].flag == "unknown"


def test_report_only_asks_for_missing_patient_context() -> None:
    result = analyze_report(
        "lab.txt",
        "text/plain",
        (
            "性别 / 年龄\n男 / 45岁\n采样时间\n2026-07-26 09:15\n"
            "白细胞计数 12.50 10^9/L ↑ 3.50-9.50\n"
        ).encode(),
    )

    assert result.patient_context.sex == "男"
    assert result.patient_context.age == 45
    assert result.patient_context.collected_at == "2026-07-26 09:15"
    assert result.patient_context.pregnancy_status == "不适用（报告标注为男性）"
    assert all("年龄和性别" not in question for question in result.follow_up_questions)
    assert all("检查或采样日期" not in question for question in result.follow_up_questions)
    assert any("就诊原因" in question for question in result.follow_up_questions)


def test_synthetic_report_is_explicitly_marked() -> None:
    result = analyze_report(
        "demo.txt",
        "text/plain",
        "合成检验报告 仅用于软件功能测试\n血糖 7.2 mmol/L ↑ 3.9-6.1\n".encode(),
    )

    assert result.is_synthetic is True


def test_report_extracts_existing_history_and_urgent_instruction() -> None:
    result = analyze_report(
        "record.txt",
        "text/plain",
        (
            "主诉：发热2天\n既往史：高血压\n当前用药：氨氯地平\n"
            "医生建议症状加重时及时就诊\n"
        ).encode(),
    )

    assert result.patient_context.visit_reason == "发热2天"
    assert result.patient_context.medical_history == "高血压"
    assert result.patient_context.current_medications == "氨氯地平"
    assert "及时就诊" in (result.patient_context.urgent_instruction or "")
    assert all("既往疾病" not in question for question in result.follow_up_questions)
