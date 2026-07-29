from yuanqi_agent.sse import format_result, is_confirmed_write_result


def test_create_patient_success_requires_real_identity_fields() -> None:
    incomplete = {"id": 10, "status": "ACTIVE"}

    assert not is_confirmed_write_result("create_patient", incomplete)
    assert "创建成功" not in format_result("create_patient", incomplete)


def test_write_success_messages_use_server_generated_business_identifiers() -> None:
    patient = {
        "id": 10,
        "patientNo": "P20260730001",
        "name": "李四",
    }
    prescription = {
        "id": 20,
        "prescriptionNo": "RX20260730001",
    }
    record = {
        "id": 30,
        "recordNo": "MR20260730001",
    }

    assert "李四" in format_result("create_patient", patient)
    assert "P20260730001" in format_result("create_patient", patient)
    assert "RX20260730001" in format_result("create_prescription", prescription)
    assert "MR20260730001" in format_result("create_medical_record", record)
    assert "系统 ID" not in format_result("create_patient", patient)
    assert "系统 ID" not in format_result("create_prescription", prescription)
    assert "系统 ID" not in format_result("create_medical_record", record)
