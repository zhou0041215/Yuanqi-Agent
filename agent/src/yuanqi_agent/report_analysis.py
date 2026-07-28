from __future__ import annotations

import io
import re
from pathlib import Path

from pydantic import Field
from pypdf import PdfReader

from yuanqi_agent.errors import AgentError
from yuanqi_agent.models import StrictModel

MAX_REPORT_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 40_000
ALLOWED_REPORT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
}


class ReportFinding(StrictModel):
    item: str
    result: str
    reference: str | None = None
    flag: str = Field(pattern=r"^(high|low|abnormal|unknown)$")


class ReportPatientContext(StrictModel):
    sex: str | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    collected_at: str | None = None
    reported_at: str | None = None
    visit_reason: str | None = None
    symptoms: str | None = None
    medical_history: str | None = None
    current_medications: str | None = None
    pregnancy_status: str | None = None
    urgent_instruction: str | None = None


class ReportAnalysis(StrictModel):
    file_name: str
    report_type: str
    is_synthetic: bool
    summary: str
    findings: list[ReportFinding]
    extracted_text_preview: str
    patient_context: ReportPatientContext
    follow_up_questions: list[str]
    warnings: list[str]


def analyze_report(file_name: str, content_type: str, content: bytes) -> ReportAnalysis:
    if not content or len(content) > MAX_REPORT_BYTES:
        raise AgentError(
            "INVALID_REPORT_SIZE",
            "报告文件应大于 0 且不超过 10 MB",
            status_code=400,
        )
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type not in ALLOWED_REPORT_TYPES:
        raise AgentError(
            "UNSUPPORTED_REPORT_TYPE",
            "仅支持 PDF、TXT、CSV、JPG 和 PNG 检查报告",
            status_code=415,
        )

    text = _extract_text(normalized_type, content)
    cleaned = _clean_text(text)
    if len(cleaned) < 8:
        raise AgentError(
            "REPORT_TEXT_NOT_FOUND",
            "未识别到足够的报告文字；请上传清晰原图或可复制文字的 PDF",
            status_code=422,
        )

    findings = _extract_findings(cleaned)
    context = _extract_patient_context(cleaned)
    abnormal_count = sum(item.flag != "unknown" for item in findings)
    summary = (
        f"已从报告中提取 {len(findings)} 个可识别项目，其中 {abnormal_count} 个带有"
        "报告原文中的异常标记。"
        if findings
        else "已提取报告文字，但没有可靠识别出结构化检验项目。"
    )
    return ReportAnalysis(
        file_name=Path(file_name).name[:200],
        report_type=normalized_type,
        is_synthetic=any(marker in cleaned for marker in ("合成演示", "合成检验", "仅用于软件功能测试")),
        summary=summary,
        findings=findings[:80],
        extracted_text_preview=cleaned[:4000],
        patient_context=context,
        follow_up_questions=_missing_context_questions(context),
        warnings=[
            "异常标记和参考范围以报告原文为准，不同实验室的范围可能不同。",
            "单项指标不能独立用于诊断，需要结合症状、病史和医生查体。",
            "系统不会仅凭本报告给出确诊结论、处方或用药剂量。",
        ],
    )


def _extract_patient_context(text: str) -> ReportPatientContext:
    sex = _first_group(text, r"(?:性别|性别\s*/\s*年龄)[：:\s]+(男|女)")
    age_text = _first_group(
        text,
        r"(?:年龄[：:\s]+|性别\s*/\s*年龄[：:\s]+(?:男|女)\s*/\s*)(\d{1,3})\s*岁?",
    )
    collected_at = _first_group(
        text,
        r"(?:采样时间|检查日期|检查时间)[：:\s]+(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)",
    )
    reported_at = _first_group(
        text,
        r"报告时间[：:\s]+(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)",
    )
    visit_reason = _first_group(text, r"(?:就诊原因|主诉)[：:\s]+([^\n]{2,200})")
    symptoms = _first_group(text, r"(?:主要不适|症状)[：:\s]+([^\n]{2,200})")
    history = _first_group(text, r"(?:既往史|既往疾病)[：:\s]+([^\n]{1,300})")
    medications = _first_group(text, r"(?:当前用药|现用药物)[：:\s]+([^\n]{1,300})")
    urgent = _first_group(
        text,
        r"([^\n]*(?:立即就医|尽快就医|及时就诊|尽快复查)[^\n]*)",
    )
    pregnancy_status = "不适用（报告标注为男性）" if sex == "男" else None
    return ReportPatientContext(
        sex=sex,
        age=int(age_text) if age_text else None,
        collected_at=collected_at,
        reported_at=reported_at,
        visit_reason=visit_reason,
        symptoms=symptoms,
        medical_history=history,
        current_medications=medications,
        pregnancy_status=pregnancy_status,
        urgent_instruction=urgent,
    )


def _missing_context_questions(context: ReportPatientContext) -> list[str]:
    questions: list[str] = []
    if not context.collected_at:
        questions.append("这份报告的检查或采样日期是什么？")
    if not context.visit_reason and not context.symptoms:
        questions.append("本次检查的就诊原因和目前主要不适是什么？")
    if context.age is None or context.sex is None:
        questions.append("年龄和性别是什么？")
    if context.sex == "女" and not context.pregnancy_status:
        questions.append("目前是否处于妊娠期或哺乳期？")
    if not context.medical_history:
        questions.append("是否有已确诊的既往疾病？")
    if not context.current_medications:
        questions.append("目前正在使用哪些药物或保健品？")
    return questions


def _first_group(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_text(content_type: str, content: bytes) -> str:
    if content_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages[:30])
        except Exception as exc:
            raise AgentError(
                "INVALID_REPORT_FILE",
                "PDF 文件无法解析或已损坏",
                status_code=400,
            ) from exc
    if content_type in {"text/plain", "text/csv"}:
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise AgentError(
            "INVALID_REPORT_ENCODING",
            "文本报告编码无法识别",
            status_code=400,
        )
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(content))
        image.verify()
        image = Image.open(io.BytesIO(content)).convert("RGB")
        return pytesseract.image_to_string(image, lang="chi_sim+eng")
    except ImportError as exc:
        raise AgentError(
            "REPORT_OCR_NOT_CONFIGURED",
            "图片 OCR 尚未配置；请安装 report-ocr 依赖和 Tesseract 中文语言包",
            status_code=503,
        ) from exc
    except Exception as exc:
        raise AgentError(
            "REPORT_OCR_FAILED",
            "图片文字识别失败，请上传清晰、方向正确的原图",
            status_code=422,
        ) from exc


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)[:MAX_EXTRACTED_CHARS]


def _extract_findings(text: str) -> list[ReportFinding]:
    findings: list[ReportFinding] = []
    pattern = re.compile(
        r"^(?P<item>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9 /()%+-]{1,30})"
        r"[\s:：]+(?P<value>-?\d+(?:\.\d+)?(?:\s*[A-Za-z%/·^0-9]+)?)"
        r"(?:\s+(?P<flag>[↑↓HL高低异常]+))?"
        r"(?:\s+(?P<reference>-?\d+(?:\.\d+)?\s*[-~—至]\s*-?\d+(?:\.\d+)?))?$"
    )
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        marker = match.group("flag") or ""
        flag = "unknown"
        if any(value in marker for value in ("↑", "H", "高")):
            flag = "high"
        elif any(value in marker for value in ("↓", "L", "低")):
            flag = "low"
        elif "异常" in marker:
            flag = "abnormal"
        findings.append(
            ReportFinding(
                item=match.group("item").strip(),
                result=match.group("value").strip(),
                reference=match.group("reference"),
                flag=flag,
            )
        )
    return findings
