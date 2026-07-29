import pytest

from yuanqi_agent.errors import AgentError
from yuanqi_agent.models import PatientContext, ToolCall
from yuanqi_agent.write_grounding import (
    bind_verified_patient_context,
    ground_natural_write_call,
)


def test_create_patient_discards_model_invented_personal_data() -> None:
    grounded = ground_natural_write_call(
        "给我创建患者李四",
        ToolCall(
            name="create_patient",
            arguments={
                "name": "李四",
                "gender": "MALE",
                "birth_date": "1990-01-01",
                "phone": "13800138000",
                "id_card": "110101199001011234",
                "blood_type": "A型",
                "allergy_history": "青霉素过敏",
                "medical_history": "高血压",
            },
        ),
    )

    assert grounded.arguments == {
        "name": "李四",
        "gender": "UNKNOWN",
        "birth_date": None,
        "phone": None,
        "id_card": None,
        "blood_type": None,
        "allergy_history": None,
        "medical_history": None,
    }


def test_create_patient_keeps_only_explicit_optional_data() -> None:
    grounded = ground_natural_write_call(
        "创建患者王芳，性别女，出生日期1992年3月4日，手机号13912345678，血型O型",
        ToolCall(
            name="create_patient",
            arguments={
                "name": "王芳",
                "gender": "FEMALE",
                "birth_date": "1992-03-04",
                "phone": "13912345678",
                "blood_type": "O型",
            },
        ),
    )

    assert grounded.arguments["gender"] == "FEMALE"
    assert grounded.arguments["birth_date"] == "1992-03-04"
    assert grounded.arguments["phone"] == "13912345678"
    assert grounded.arguments["blood_type"] == "O型"


def test_create_prescription_uses_user_medication_text() -> None:
    message = (
        "为当前患者创建一张演示处方：诊断为高血压，"
        "药品信息为演示药品A，仅用于功能测试，总金额为1元。"
    )
    grounded = ground_natural_write_call(
        message,
        bind_verified_patient_context(
            ToolCall(
                name="create_prescription",
                arguments={
                    "diagnosis": "高血压",
                    "drugs": '[{"name":"演示药品A","purpose":"功能测试"}]',
                    "total_amount": 1,
                    "notes": "患者需要复诊",
                },
            ),
            patient_context(),
        ),
    )

    assert grounded.arguments["patient_id"] == 2
    assert grounded.arguments["drugs"] == "演示药品A，仅用于功能测试"
    assert grounded.arguments["notes"] is None
    assert grounded.arguments["total_amount"] == 1.0


def test_create_medical_record_rejects_model_invented_required_fields() -> None:
    with pytest.raises(AgentError) as captured:
        ground_natural_write_call(
            "为当前患者创建病历",
            bind_verified_patient_context(
                ToolCall(
                    name="create_medical_record",
                    arguments={"visit_date": "2026-07-30"},
                ),
                patient_context(),
            ),
        )

    assert captured.value.code == "UNGROUNDED_WRITE_ARGUMENTS"
    assert "就诊日期" in captured.value.message


def test_create_medical_record_lists_missing_required_fields() -> None:
    with pytest.raises(AgentError) as captured:
        ground_natural_write_call(
            "为当前患者创建病历",
            bind_verified_patient_context(
                ToolCall(
                    name="create_medical_record",
                    arguments={},
                ),
                patient_context(),
            ),
        )

    assert captured.value.code == "UNGROUNDED_WRITE_ARGUMENTS"
    assert "就诊日期" in captured.value.message


def test_create_medical_record_keeps_explicit_values_and_drops_invented_notes() -> None:
    grounded = ground_natural_write_call(
        (
            "为当前患者创建病历，就诊日期为2026-07-30，诊断为高血压。"
        ),
        bind_verified_patient_context(
            ToolCall(
                name="create_medical_record",
                arguments={
                    "visit_date": "2026-07-30",
                    "diagnosis": "高血压",
                    "notes": "三天后复诊",
                },
            ),
            patient_context(),
        ),
    )

    assert grounded.arguments["patient_id"] == 2
    assert grounded.arguments["visit_date"] == "2026-07-30T00:00:00"
    assert grounded.arguments["diagnosis"] == "高血压"
    assert grounded.arguments["notes"] is None


def test_create_medical_record_preserves_explicit_visit_time() -> None:
    grounded = ground_natural_write_call(
        "为当前患者创建病历，就诊时间为2026-07-30 10:30，诊断为高血压。",
        bind_verified_patient_context(
            ToolCall(
                name="create_medical_record",
                arguments={
                    "visit_date": "2026-07-30",
                    "diagnosis": "高血压",
                },
            ),
            patient_context(),
        ),
    )

    assert grounded.arguments["visit_date"] == "2026-07-30T10:30:00"


def test_create_prescription_rejects_invented_amount() -> None:
    with pytest.raises(AgentError) as captured:
        ground_natural_write_call(
            "创建一张处方，诊断为高血压，药品信息为演示药品A",
            bind_verified_patient_context(
                ToolCall(
                    name="create_prescription",
                    arguments={
                        "diagnosis": "高血压",
                        "drugs": "演示药品A",
                        "total_amount": 1,
                    },
                ),
                patient_context(),
            ),
        )

    assert captured.value.code == "UNGROUNDED_WRITE_ARGUMENTS"
    assert "总金额" in captured.value.message


def test_verified_patient_context_overwrites_model_patient_id() -> None:
    bound = bind_verified_patient_context(
        ToolCall(
            name="create_prescription",
            arguments={
                "patient_id": 999,
                "diagnosis": "高血压",
                "drugs": "演示药品A",
                "total_amount": 1,
            },
        ),
        patient_context(),
    )

    assert bound.arguments["patient_id"] == 2


def test_patient_write_requires_verified_workspace_context() -> None:
    with pytest.raises(AgentError) as captured:
        bind_verified_patient_context(
            ToolCall(
                name="create_medical_record",
                arguments={"patient_id": 999, "visit_date": "2026-07-30"},
            ),
            None,
        )

    assert captured.value.code == "PATIENT_CONTEXT_REQUIRED"
    assert "患者工作台" in captured.value.message


def test_create_patient_requires_name_to_appear_in_user_message() -> None:
    with pytest.raises(AgentError) as captured:
        ground_natural_write_call(
            "给我创建一位患者",
            ToolCall(
                name="create_patient",
                arguments={"name": "李四"},
            ),
        )

    assert captured.value.code == "UNGROUNDED_WRITE_ARGUMENTS"
    assert "患者姓名" in captured.value.message


def patient_context() -> PatientContext:
    return PatientContext(patient_id=2, patient_no="P-0002", name="张三")
