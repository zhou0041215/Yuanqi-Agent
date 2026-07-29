from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from pydantic import ValidationError

from yuanqi_agent.errors import AgentError
from yuanqi_agent.models import PatientContext, ToolCall
from yuanqi_agent.tools import (
    CreateMedicalRecordArgs,
    CreatePatientArgs,
    CreatePrescriptionArgs,
)

WRITE_TOOL_NAMES = frozenset(
    {"create_patient", "create_medical_record", "create_prescription"}
)

_FIELD_LABELS = {
    "name": "患者姓名",
    "patient_id": "患者系统 ID",
    "patientId": "患者系统 ID",
    "visit_date": "就诊日期",
    "visitDate": "就诊日期",
    "diagnosis": "诊断",
    "drugs": "药品信息",
    "total_amount": "总金额",
    "totalAmount": "总金额",
}


def ground_natural_write_call(message: str, call: ToolCall) -> ToolCall:
    """Remove or reject write arguments that are not supported by the user message."""
    if call.name not in WRITE_TOOL_NAMES:
        return call
    if call.name == "create_patient":
        arguments = _ground_create_patient(message, call.arguments)
    elif call.name == "create_prescription":
        arguments = _ground_create_prescription(message, call.arguments)
    else:
        arguments = _ground_create_medical_record(message, call.arguments)
    return ToolCall(name=call.name, arguments=arguments)


def bind_verified_patient_context(
    call: ToolCall,
    patient_context: PatientContext | None,
) -> ToolCall:
    """Replace any model/client patient value with the Java-verified workspace target."""
    if call.name not in {"create_prescription", "create_medical_record"}:
        return call
    if patient_context is None:
        raise AgentError(
            "PATIENT_CONTEXT_REQUIRED",
            "创建病历或处方必须从患者工作台进入助手，系统不会使用聊天中填写的患者 ID。",
            status_code=422,
            details={"requiredContext": "patientContext"},
        )
    arguments = dict(call.arguments)
    arguments["patient_id"] = patient_context.patient_id
    arguments.pop("patientId", None)
    return ToolCall(name=call.name, arguments=arguments)


def _ground_create_patient(message: str, raw: dict) -> dict:
    args = _validate(CreatePatientArgs, raw, "创建患者")
    name = args.name.strip()
    if not _contains_text(message, name):
        _missing("创建患者", ["患者姓名"])

    return {
        "name": name,
        "gender": _explicit_gender(message),
        "birth_date": (
            args.birth_date
            if args.birth_date and args.birth_date in _explicit_dates(message)
            else None
        ),
        "phone": _ground_digits(message, args.phone),
        "id_card": _ground_digits(message, args.id_card),
        "blood_type": _explicit_blood_type(message),
        "allergy_history": _ground_optional_text(message, args.allergy_history),
        "medical_history": _ground_optional_text(message, args.medical_history),
    }


def _ground_create_prescription(message: str, raw: dict) -> dict:
    args = _validate(CreatePrescriptionArgs, raw, "创建处方")
    missing: list[str] = []
    if not _contains_text(message, args.diagnosis):
        missing.append("诊断")

    drugs = _extract_medication(message)
    if drugs is None and _contains_text(message, args.drugs):
        drugs = args.drugs.strip()
    if not drugs:
        missing.append("药品信息")

    amount = _extract_amount(message)
    if amount is None or abs(amount - args.total_amount) > 0.000001:
        missing.append("总金额")
    if missing:
        _missing("创建处方", missing)

    record_id = (
        args.record_id
        if args.record_id and _has_labeled_id(message, "病历", args.record_id)
        else None
    )
    return {
        "patient_id": args.patient_id,
        "record_id": record_id,
        "diagnosis": args.diagnosis.strip(),
        "drugs": drugs,
        "total_amount": amount,
        "notes": _ground_optional_text(message, args.notes),
    }


def _ground_create_medical_record(message: str, raw: dict) -> dict:
    args = _validate(CreateMedicalRecordArgs, raw, "创建病历")
    missing: list[str] = []
    visit_date = _ground_visit_datetime(message, args.visit_date)
    if visit_date is None:
        missing.append("就诊日期")
    if missing:
        _missing("创建病历", missing)

    return {
        "patient_id": args.patient_id,
        "visit_date": visit_date,
        "chief_complaint": _ground_optional_text(message, args.chief_complaint),
        "diagnosis": _ground_optional_text(message, args.diagnosis),
        "treatment_plan": _ground_optional_text(message, args.treatment_plan),
        "notes": _ground_optional_text(message, args.notes),
    }


def _validate(model_type, raw: dict, action: str):
    try:
        return model_type.model_validate(raw)
    except ValidationError as exc:
        missing = [
            _FIELD_LABELS.get(str(error["loc"][-1]), str(error["loc"][-1]))
            for error in exc.errors(include_url=False)
            if error["type"] == "missing" and error.get("loc")
        ]
        if missing:
            _missing(action, missing)
        raise AgentError(
            "INVALID_WRITE_ARGUMENTS",
            f"{action}参数不完整或格式不正确，请补充后重试。",
            status_code=422,
            details=exc.errors(include_url=False),
        ) from exc


def _missing(action: str, fields: list[str]) -> None:
    joined = "、".join(dict.fromkeys(fields))
    raise AgentError(
        "UNGROUNDED_WRITE_ARGUMENTS",
        f"{action}缺少可核验的{joined}。请明确提供，系统不会自动猜测。",
        status_code=422,
        details={"missingFields": list(dict.fromkeys(fields))},
    )


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _contains_text(message: str, value: str | None) -> bool:
    if value is None or not value.strip():
        return False
    return _normalize(value) in _normalize(message)


def _ground_optional_text(message: str, value: str | None) -> str | None:
    return value.strip() if value and _contains_text(message, value) else None


def _ground_digits(message: str, value: str | None) -> str | None:
    if not value:
        return None
    candidate = re.sub(r"\D", "", value)
    source = re.sub(r"\D", "", message)
    return value.strip() if candidate and candidate in source else None


def _explicit_gender(message: str) -> str:
    normalized = _normalize(message)
    female = (
        r"(?:性别\s*(?:为|是|[:：])?\s*女|女性|女患者|[,，\s]女(?:[,，。\s]|$))"
    )
    male = r"(?:性别\s*(?:为|是|[:：])?\s*男|男性|男患者|[,，\s]男(?:[,，。\s]|$))"
    if re.search(female, normalized):
        return "FEMALE"
    if re.search(male, normalized):
        return "MALE"
    return "UNKNOWN"


def _explicit_blood_type(message: str) -> str | None:
    match = re.search(
        r"血型\s*(?:为|是|[:：])?\s*(AB|A|B|O)\s*(?:型|型血)?",
        unicodedata.normalize("NFKC", message),
        flags=re.IGNORECASE,
    )
    return f"{match.group(1).upper()}型" if match else None


def _explicit_dates(message: str) -> set[str]:
    values: set[str] = set()
    for year, month, day in re.findall(
        r"(?<!\d)(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?(?!\d)",
        unicodedata.normalize("NFKC", message),
    ):
        try:
            values.add(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            continue
    return values


def _ground_visit_datetime(message: str, value: str) -> str | None:
    try:
        candidate = datetime.fromisoformat(value.strip())
    except ValueError:
        try:
            candidate = datetime.combine(date.fromisoformat(value.strip()), datetime.min.time())
        except ValueError:
            return None
    candidate_value = candidate.replace(tzinfo=None).isoformat(timespec="seconds")
    explicit_values = _explicit_visit_datetimes(message)
    if candidate_value in explicit_values:
        return candidate_value
    same_day = [
        explicit
        for explicit in explicit_values
        if explicit[:10] == candidate_value[:10]
    ]
    if len(same_day) == 1:
        return same_day[0]
    return None


def _explicit_visit_datetimes(message: str) -> set[str]:
    values: set[str] = set()
    normalized = unicodedata.normalize("NFKC", message)
    pattern = (
        r"(?<!\d)(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?"
        r"(?:[T\s]+(\d{1,2})[:：](\d{1,2})(?:[:：](\d{1,2}))?)?(?!\d)"
    )
    for year, month, day, hour, minute, second in re.findall(pattern, normalized):
        try:
            values.add(
                datetime(
                    int(year),
                    int(month),
                    int(day),
                    int(hour or 0),
                    int(minute or 0),
                    int(second or 0),
                ).isoformat(timespec="seconds")
            )
        except ValueError:
            continue
    return values


def _has_labeled_id(message: str, label: str, value: int) -> bool:
    normalized = unicodedata.normalize("NFKC", message)
    patterns = [
        rf"{label}\s*(?:系统\s*)?ID\s*[为是:#：()（）]*\s*{value}(?!\d)",
        rf"系统\s*ID\s*[为是:#：()（）]*\s*{value}(?!\d)",
    ]
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def _extract_medication(message: str) -> str | None:
    match = re.search(
        r"(?:药品信息|药物信息|用药信息)\s*(?:为|是|[:：])\s*(.+?)"
        r"(?=(?:[,，]\s*)?(?:总金额|金额|备注)\s*(?:为|是|[:：])|[。\n]|$)",
        message,
        flags=re.DOTALL,
    )
    if not match:
        return None
    value = match.group(1).strip(" \t\r\n,，;；\"'“”")
    return value or None


def _extract_amount(message: str) -> float | None:
    match = re.search(
        r"(?:总金额|金额)\s*(?:为|是|[:：])?\s*(\d+(?:\.\d+)?)\s*元?",
        unicodedata.normalize("NFKC", message),
    )
    return float(match.group(1)) if match else None
