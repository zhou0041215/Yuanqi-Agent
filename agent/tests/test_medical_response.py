from yuanqi_agent.medical_response import build_disease_answer, emergency_guidance


def test_diabetes_complication_answer_is_evidence_bounded_and_asks_for_screening_data() -> None:
    answer = build_disease_answer(
        "糖尿病有哪些并发症？",
        {
            "disease": {"name": "糖尿病"},
            "relations": {
                "并发症": ["糖尿病肾病", "糖尿病视网膜病变"],
            },
        },
    )

    assert "糖尿病肾病" in answer
    assert "糖尿病视网膜病变" in answer
    assert "并不表示每位患者都会发生" in answer
    assert "糖化血红蛋白" in answer
    assert "尿白蛋白/肌酐比值" in answer
    assert "who.int/news-room/fact-sheets/detail/diabetes" in answer
    assert "治疗药品" not in answer


def test_emergency_red_flag_stops_normal_chat_flow() -> None:
    answer = emergency_guidance("突然出现剧烈胸痛和严重呼吸困难")

    assert answer is not None
    assert "立即" in answer
    assert "急诊" in answer


def test_common_non_emergency_question_is_not_overtriaged() -> None:
    assert emergency_guidance("糖尿病有哪些并发症？") is None
