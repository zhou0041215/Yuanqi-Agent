from yuanqi_agent.medical_response import (
    apply_report_dialogue,
    build_report_followup_answer,
)

REPORT = """## 检查报告解读

### 报告原文项目

| 项目 | 结果 | 参考范围 | 原文标记 |
|---|---:|---:|---|
| 白细胞计数 | 12.50 10^9/L | 3.50-9.50 | ↑ 偏高 |
| 血红蛋白 | 105 g/L | 115-150 | ↓ 偏低 |
| 血小板计数 | 226 10^9/L | 125-350 | 未标记 |
"""


def test_report_context_reply_bypasses_new_disease_search() -> None:
    answer = build_report_followup_answer(
        "本次是年度体检，没有明显不适。既往有高血压，目前每天服用氨氯地平。",
        [{"role": "assistant", "content": REPORT}],
    )

    assert answer is not None
    assert "年度体检" in answer
    assert "无明显不适" in answer
    assert "高血压" in answer
    assert "氨氯地平" in answer
    assert "白细胞计数" in answer
    assert "血红蛋白" in answer
    assert "血小板计数" not in answer
    assert "自行停用、加量或更换" in answer
    assert "优先确认" in answer


def test_unrelated_message_is_not_treated_as_report_context() -> None:
    assert build_report_followup_answer(
        "高血压有哪些并发症？",
        [{"role": "assistant", "content": REPORT}],
    ) is None


def test_report_dialogue_keeps_locked_answer_and_asks_one_question() -> None:
    answer = "### 异常项目分层解读\n\n- 血红蛋白偏低，这是锁定事实"
    dialogue = apply_report_dialogue(answer, "我了解你的补充信息了。", "anemia")

    assert "我了解你的补充信息了" in dialogue
    assert "锁定事实" in dialogue
    assert "既往是否有贫血" in dialogue
    assert "不需要重新上传" in dialogue


def test_unsafe_model_acknowledgement_falls_back() -> None:
    dialogue = apply_report_dialogue(
        "锁定事实",
        "已经确诊，建议服用 10mg 药物。",
        "glucose",
    )

    assert "已经确诊" not in dialogue
    assert "按报告里的异常程度" in dialogue
    assert "空腹 8 小时" in dialogue


def test_clinical_priority_cannot_be_overridden_by_model_focus() -> None:
    dialogue = apply_report_dialogue(
        "优先确认空腹血糖；同时进一步评估丙氨酸氨基转移酶。",
        "了解了，我会结合你补充的情况继续分析。",
        "liver",
    )

    assert "空腹 8 小时" in dialogue
    assert "近期是否饮酒" not in dialogue
