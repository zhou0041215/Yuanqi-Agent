from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from langgraph.types import Command

from yuanqi_agent.errors import AgentError, ThreadAccessDeniedError, ThreadConflictError
from yuanqi_agent.graph import first_interrupt_value
from yuanqi_agent.java_client import JavaApiClient
from yuanqi_agent.medical_response import (
    apply_report_dialogue,
    build_report_followup_answer,
    emergency_guidance,
)
from yuanqi_agent.models import (
    AgentExecution,
    AgentRunRequest,
    ApprovalDecision,
    PatientContext,
    PendingTool,
    RunStatus,
    ToolCall,
    VerifiedUserContext,
)
from yuanqi_agent.planner import IntentPlanner
from yuanqi_agent.runtime import RequestRuntime, reset_runtime, set_runtime
from yuanqi_agent.sse import encode_sse
from yuanqi_agent.tools import ToolRegistry
from yuanqi_agent.write_grounding import (
    WRITE_TOOL_NAMES,
    bind_verified_patient_context,
    ground_natural_write_call,
)

MAX_MULTI_TURN_ITERATIONS = 10
LOGGER = logging.getLogger(__name__)


# ── 医学关键词路由 ─────────────────────────────────────────────────────

_MEDICAL_DISEASE_KEYWORDS = [
    "乙型病毒性肝炎", "丙型病毒性肝炎", "慢性阻塞性肺疾病", "糖尿病",
    "高血压", "肺炎", "冠心病", "胃炎", "抑郁症", "癌症", "肿瘤",
    "哮喘", "慢阻肺", "乙肝", "丙肝", "肝炎", "肾炎", "关节炎",
    "心梗", "脑梗", "中风", "骨折",
    "什么病", "什么疾病", "得了", "患病", "生病", "疾病",
]
_DISEASE_ALIASES = {
    "慢阻肺": "慢性阻塞性肺疾病",
    "乙肝": "乙型病毒性肝炎",
    "丙肝": "丙型病毒性肝炎",
}
_MEDICAL_SYMPTOM_KEYWORDS = [
    "头痛", "头晕", "发热", "发烧", "咳嗽", "胸闷", "胸痛", "心悸",
    "恶心", "呕吐", "腹痛", "腹泻", "失眠", "疲劳", "乏力", "气短",
    "耳鸣", "视力", "麻木", "水肿", "皮疹", "出血", "症状", "表现",
    "可能是什么", "怎么回事", "什么原因",
]
_MEDICAL_DRUG_KEYWORDS = [
    "二甲双胍", "阿莫西林", "奥美拉唑", "氨氯地平", "缬沙坦", "胰岛素",
    "阿司匹林", "硝酸甘油", "氟西汀", "舍曲林", "布洛芬", "头孢",
    "药物", "吃药", "用药", "副作用", "禁忌", "怎么吃",
]
_MEDICAL_DEPT_KEYWORDS = [
    "挂什么科", "看哪个科", "哪个科", "科室", "门诊",
]
_WRITE_INTENT_MARKERS = ("创建", "新增", "修改", "更新", "删除", "开具", "录入", "变更")
_MEDICATION_ADVICE_MARKERS = (
    "吃什么药", "吃啥药", "建议吃", "推荐药", "怎么用药", "如何用药",
    "开点药", "用什么药", "服什么药", "有什么药", "吃哪些药", "吃那些药",
    "降压药", "降血压",
)


def _has_write_intent(message: str) -> bool:
    """Return whether the user is asking to mutate business data."""
    return any(marker in message for marker in _WRITE_INTENT_MARKERS)


def _route_medical_tool(message: str, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    """根据关键词直接路由到医学工具，绕过 planner"""
    available = {t["name"] for t in tools}
    msg = message.strip()

    # Deterministic keyword routes below are read-only. A message such as
    # "为患者 ID 1 创建一张处方" contains both "患者" and a write intent;
    # routing it to list_patients would prevent the planner from selecting the
    # approval-gated create_prescription tool.
    if _has_write_intent(msg):
        return None

    if any(keyword in msg for keyword in ("病历", "就诊记录")) and "list_medical_records" in available:
        return {"name": "list_medical_records", "arguments": {"keyword": None}}

    if (
        any(keyword in msg for keyword in ("处方列表", "查询处方", "查看处方", "有哪些处方"))
        and "list_prescriptions" in available
    ):
        return {"name": "list_prescriptions", "arguments": {"keyword": None}}

    if any(keyword in msg for keyword in ("患者", "病人")) and "list_patients" in available:
        return {"name": "list_patients", "arguments": {"keyword": None}}

    for kw in _MEDICAL_DISEASE_KEYWORDS:
        if kw in msg and "search_disease" in available:
            # 提取疾病名称
            name = kw if kw not in ("什么病", "什么疾病", "得了", "患病", "生病", "疾病") else msg
            name = _DISEASE_ALIASES.get(name, name)
            return {"name": "search_disease", "arguments": {"name": name}}

    for kw in _MEDICAL_SYMPTOM_KEYWORDS:
        if kw in msg and "search_symptom" in available:
            return {"name": "search_symptom", "arguments": {"symptom": kw}}

    for kw in _MEDICAL_DRUG_KEYWORDS:
        if kw in msg and "search_drug" in available:
            name = (
                _extract_drug_name(msg, kw)
                if kw not in ("药物", "吃药", "用药", "副作用", "禁忌", "怎么吃")
                else msg
            )
            return {"name": "search_drug", "arguments": {"name": name}}

    for kw in _MEDICAL_DEPT_KEYWORDS:
        if kw in msg and "search_department" in available:
            return {"name": "search_department", "arguments": {"name": None}}

    return None


def _extract_drug_name(message: str, matched_keyword: str) -> str:
    """Preserve a complete medicine name instead of truncating to a keyword."""
    start = message.find(matched_keyword)
    candidate = message[start:].strip(" ，。！？?：:")
    suffixes = (
        "的副作用",
        "有什么副作用",
        "副作用",
        "的禁忌",
        "有什么禁忌",
        "禁忌",
        "的用法",
        "怎么吃",
        "怎么用",
        "能不能",
        "可以",
        "是否",
        "是什么",
        "有什么作用",
        "的作用",
    )
    positions = [
        candidate.find(suffix)
        for suffix in suffixes
        if candidate.find(suffix) > 0
    ]
    if positions:
        candidate = candidate[:min(positions)]
    candidate = candidate.strip(" ，。！？?：:")
    return candidate if candidate and len(candidate) <= 80 else matched_keyword


_INTENT_MARKERS = {
    "drug": ("副作用", "禁忌", "怎么吃", "怎么用", "用法", "服用", "剂量", "不良反应"),
    "department": ("挂什么科", "看哪个科", "哪个科", "科室", "门诊", "挂号"),
    "symptom": ("可能是什么", "怎么回事", "什么原因", "是什么病", "什么毛病"),
}


def _route_by_resolved_entities(
    message: str,
    entities: dict[str, list[str]],
    tools: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Route on entity names actually present in the graph, not a fixed keyword list."""
    # Entity routes are read-only. Write requests must reach the planner so it can
    # select an approval-gated business tool such as create_prescription.
    if _has_write_intent(message):
        return None

    available = {tool["name"] for tool in tools}
    disease = next(iter(entities.get("Disease") or []), None)
    drug = next(iter(entities.get("Drug") or []), None)
    symptom = next(iter(entities.get("Symptom") or []), None)

    # 明确在问药，且消息里确实出现了图谱中的药名。
    if drug and "search_drug" in available and (
        any(marker in message for marker in _INTENT_MARKERS["drug"])
        or (disease is None and symptom is None)
    ):
        return {"name": "search_drug", "arguments": {"name": drug}}

    if disease and "search_disease" in available:
        return {"name": "search_disease", "arguments": {"name": disease}}

    # 只报症状、没提到具体疾病时才做症状反查。
    if symptom and "search_symptom" in available:
        return {"name": "search_symptom", "arguments": {"symptom": symptom}}

    if (
        any(marker in message for marker in _INTENT_MARKERS["department"])
        and "search_department" in available
    ):
        return {"name": "search_department", "arguments": {"name": None}}

    return None


def _fallback_medical_read_tool(
    message: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Use hybrid medical retrieval only for non-mutating requests."""
    available = {tool["name"] for tool in tools}
    if "search_knowledge" in available and not _has_write_intent(message):
        return {"name": "search_knowledge", "arguments": {"query": message}}
    return None


def _contextualize_message(message: str, history: list[dict[str, Any]]) -> str:
    """Resolve short medical follow-ups without asking the model to guess the subject."""
    normalized = message.strip()
    if not any(marker in normalized for marker in _MEDICATION_ADVICE_MARKERS):
        return normalized
    if "降血压" in normalized or "降压药" in normalized:
        return f"高血压：{normalized}"
    if any(keyword in normalized for keyword in _MEDICAL_DISEASE_KEYWORDS):
        return normalized
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        previous = str(item.get("content") or "")
        for disease in _MEDICAL_DISEASE_KEYWORDS:
            if disease in previous and disease not in {
                "什么病", "什么疾病", "得了", "患病", "生病", "疾病",
            }:
                return f"{disease}：{normalized}"
    return normalized


def _is_medication_advice(message: str) -> bool:
    return any(marker in message for marker in _MEDICATION_ADVICE_MARKERS)


_DISCLAIMER_MARKERS = (
    "本回答由 AI 基于医学知识图谱",
    "本回答基于医学知识图谱",
    "仅供参考，不构成诊断或用药建议",
)


def _clean_history_for_generation(
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Strip disclaimer lines from prior assistant turns before generation.

    Small models imitate conversation history more strongly than they follow
    instructions: if a previous answer ends with the fixed disclaimer, the
    model reproduces it verbatim and the answer ends up with duplicates. The
    deterministic disclaimer is re-appended by the answer layer anyway.
    """
    cleaned: list[dict[str, Any]] = []
    for item in history:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "")
        if role == "assistant":
            content = "\n".join(
                line
                for line in content.splitlines()
                if not any(marker in line for marker in _DISCLAIMER_MARKERS)
            ).strip()
            if not content:
                continue
        cleaned.append({"role": role, "content": content})
    return cleaned


def _has_report_context(history: list[dict[str, Any]]) -> bool:
    return any(
        item.get("role") == "assistant"
        and "## 检查报告解读" in str(item.get("content") or "")
        for item in history
    )


def _medication_safety_response(subject: str) -> str:
    disease = next(
        (item for item in _MEDICAL_DISEASE_KEYWORDS if item in subject and len(item) >= 2),
        "这种情况",
    )
    response = (
        f"\n\n关于 **{disease}** 的用药，不能仅凭聊天内容推荐具体药名或剂量。"
        "医生需要结合多次测量结果、年龄、过敏史、妊娠情况、肝肾功能，"
        "以及是否合并糖尿病、心脑血管疾病等选择方案。请到相应专科或基层慢病门诊评估，"
        "并只按医生处方服药；不要自行开始、换药、加量或停药。"
    )
    if disease == "高血压":
        response += (
            "\n\n如果血压达到或超过 180/120 mmHg，或同时出现胸痛、呼吸困难、"
            "意识异常、剧烈头痛、视物异常、单侧肢体无力等症状，请立即急诊就医。"
        )
    return response


def _is_truncated_term(value: str) -> bool:
    """Detect catalog terms the upstream dataset cut off at 10 characters.

    About 6% of the open catalog's symptom names end in an ellipsis
    ("一侧乳头萎缩，..."). The full wording is gone upstream and cannot be
    recovered, and showing a fragment as if it were a complete clinical sign is
    worse than omitting it. They stay in the graph for browsing.
    """
    return value.endswith("...") or value.endswith("..") or "…" in value


def _sanitize_disease_payload(payload: dict[str, Any], message: str) -> dict[str, Any]:
    cleaned = dict(payload)
    # Gate removed: keep the disease's catalog fields (summary/病因/高发人群).
    # The answer layer labels unreviewed content as encyclopedia reference
    # rather than hiding everything but the name.
    relations: dict[str, list[str]] = {}
    for label, raw_values in dict(payload.get("relations") or {}).items():
        values: list[str] = []
        for raw in raw_values if isinstance(raw_values, list) else []:
            value = str(raw).strip()
            if (
                not value
                or len(value) > 80
                or value in {"Ⅰ", "Ⅱ", "Ⅲ", "I", "II", "III", "未知", "其他"}
                or value in values
                or _is_truncated_term(value)
            ):
                continue
            values.append(value)
            if len(values) >= 20:
                break
        if values:
            relations[label] = values
    if any(marker in message for marker in _MEDICAL_DEPT_KEYWORDS):
        relations = {
            "所属科室": relations.get("所属科室", []),
        }
    elif "并发症" in message:
        relations = {
            "并发症": relations.get("并发症", []),
        }
    elif "检查" in message:
        relations = {
            "检查项目": relations.get("检查项目", []),
        }
    elif "症状" in message or "表现" in message:
        relations = {
            "症状": relations.get("症状", []),
        }
    relations.pop("治疗药品", None)
    cleaned["relations"] = relations
    return cleaned


class LoopEventType(StrEnum):
    REASONING = "reasoning"
    TEXT = "text"
    TOOL_RESULT = "tool_result"
    UI_DATA = "uiData"
    ERROR = "error"
    DONE = "done"


class LoopEvent:
    __slots__ = ("data", "type")

    def __init__(self, type: LoopEventType, data: dict[str, Any]) -> None:
        self.type = type
        self.data = data

    def to_sse(self) -> bytes:
        return encode_sse(self.type.value, self.data)


class LoopController:
    """Manages the multi-turn generator lifecycle with pause/resume for approvals."""

    def __init__(self) -> None:
        self._generator: AsyncIterator[LoopEvent] | None = None
        self._approval_signal = asyncio.Event()

    def set_generator(self, gen: AsyncIterator[LoopEvent]) -> None:
        self._generator = gen
        self._approval_signal.clear()

    def signal_approval(self) -> None:
        self._approval_signal.set()

    def clear(self) -> None:
        self._generator = None
        self._approval_signal.clear()


class AgentService:
    def __init__(
        self,
        graph: Any,
        java_client: JavaApiClient,
        planner: IntentPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self._graph = graph
        self._java = java_client
        self._planner = planner
        self._tools = tool_registry
        self._controllers: dict[str, LoopController] = {}

    def _get_controller(self, thread_id: str) -> LoopController:
        if thread_id not in self._controllers:
            self._controllers[thread_id] = LoopController()
        return self._controllers[thread_id]

    # ── SSE streaming loop ───────────────────────────────────────────────

    async def run_loop(
        self,
        request: AgentRunRequest,
        authorization: str,
        trace_id: str,
    ) -> AsyncIterator[bytes]:
        """Multi-turn tool loop with SSE event streaming."""
        user = await self._java.get_user_context(authorization, trace_id)
        thread_id = str(request.thread_id or uuid4())
        controller = self._get_controller(thread_id)

        registry = self._tools
        planner = self._planner
        if registry is None or planner is None:
            yield encode_sse("error", {"error": {"code": "SERVICE_UNAVAILABLE", "message": "Agent not configured"}})
            return

        gen = self._loop_generator(
            thread_id,
            request.mode,
            request.message,
            [item.model_dump(mode="json") for item in request.history],
            request.tool_call,
            request.patient_context,
            user,
            authorization,
            trace_id,
            planner,
            registry,
            controller,
        )
        controller.set_generator(gen)

        try:
            async for event in gen:
                yield event.to_sse()
        except Exception:
            LOGGER.exception(
                "Agent stream failed",
                extra={"trace_id": trace_id, "thread_id": thread_id},
            )
            yield encode_sse("error", {"error": {"code": "INTERNAL_ERROR", "message": "Agent execution failed"}})

    async def resume_loop(
        self,
        thread_id: UUID,
        decision: ApprovalDecision,
        authorization: str,
        trace_id: str,
    ) -> AsyncIterator[bytes]:
        """Resume persisted LangGraph state in a separate SSE request."""
        try:
            execution = await self.resume(thread_id, decision, authorization, trace_id)
            if execution.status == RunStatus.REJECTED:
                yield encode_sse("text", {"text": "操作已驳回，未修改任何业务数据。"})
            elif execution.result is not None:
                from yuanqi_agent.sse import format_result, is_confirmed_write_result

                formatted = format_result(execution.tool_name or "", execution.result)
                if not is_confirmed_write_result(
                    execution.tool_name or "",
                    execution.result,
                ):
                    yield encode_sse(
                        "error",
                        {
                            "error": {
                                "code": "UNCONFIRMED_WRITE_RESULT",
                                "message": (
                                    "业务写入返回结果缺少必要标识，系统不会显示成功。"
                                    "请到对应工作台核对实际数据。"
                                ),
                            }
                        },
                    )
                    return
                yield encode_sse(
                    "tool_result",
                    {
                        "toolResult": {
                            "toolName": execution.tool_name,
                            "result": execution.result,
                            "formatted": formatted,
                        }
                    },
                )
            yield encode_sse(
                "done",
                {"threadId": str(thread_id), "status": execution.status.value},
            )
        except Exception as exc:
            yield encode_sse(
                "error",
                {"error": {"code": "RESUME_FAILED", "message": str(exc)}},
            )

    async def _loop_generator(
        self,
        thread_id: str,
        mode: str,
        message: str,
        prior_history: list[dict[str, Any]],
        initial_tool_call: ToolCall | None,
        patient_context: PatientContext | None,
        user: VerifiedUserContext,
        authorization: str,
        trace_id: str,
        planner: IntentPlanner,
        registry: ToolRegistry,
        controller: LoopController,
    ) -> AsyncIterator[LoopEvent]:
        """Core multi-turn loop that yields LoopEvents."""
        message = _contextualize_message(message, prior_history)
        user_question = message  # the loop may rewrite `message` for tool chaining
        medication_advice = _is_medication_advice(message)
        history: list[dict[str, Any]] = [
            *prior_history,
            {"role": "user", "content": message},
        ]

        # Rule-triggered safety notices: the trigger and the notice content are
        # deterministic; the model only rephrases the wording. `notice_state`
        # reports whether the model produced anything.
        notice_state = {"generated": False}
        stream_notice = getattr(planner, "stream_safety_notice", None)

        async def phrase_notice(notice: str) -> AsyncIterator[LoopEvent]:
            notice_state["generated"] = False
            if stream_notice is None:
                return
            try:
                async for token in stream_notice(
                    user_question,
                    notice,
                    history=_clean_history_for_generation(prior_history)[-6:],
                ):
                    if token:
                        notice_state["generated"] = True
                        yield LoopEvent(LoopEventType.TEXT, {"text": token})
            except Exception:
                LOGGER.exception(
                    "Safety notice generation failed",
                    extra={"trace_id": trace_id, "thread_id": thread_id},
                )

        emergency = emergency_guidance(message)
        if emergency:
            yield LoopEvent(LoopEventType.REASONING, {"reasoning": "检测到需要优先处理的危险信号"})
            async for event in phrase_notice(emergency):
                yield event
            if not notice_state["generated"]:
                # Deliberate exception to the no-fallback policy: a user in a
                # possible emergency must still get the escalation guidance
                # even when the model is down.
                yield LoopEvent(LoopEventType.TEXT, {"text": emergency})
            yield LoopEvent(LoopEventType.DONE, {"threadId": thread_id, "status": "completed"})
            return
        report_followup = (
            build_report_followup_answer(message, prior_history)
            if mode == "report"
            else None
        )
        if report_followup:
            yield LoopEvent(
                LoopEventType.REASONING,
                {"reasoning": "识别到检查报告上下文补充，正在合并报告与健康信息"},
            )
            yield LoopEvent(
                LoopEventType.REASONING,
                {"reasoning": "医学规则已锁定事实，正在组织对话并选择下一项追问"},
            )
            dialogue_plan = None
            plan_dialogue = getattr(planner, "plan_report_dialogue", None)
            if plan_dialogue is not None:
                try:
                    dialogue_plan = await plan_dialogue(message, report_followup)
                except Exception:
                    dialogue_plan = None
            report_response = apply_report_dialogue(
                report_followup,
                getattr(dialogue_plan, "acknowledgement", None),
                getattr(dialogue_plan, "focus", None),
            )
            yield LoopEvent(LoopEventType.TEXT, {"text": report_response})
            yield LoopEvent(LoopEventType.DONE, {"threadId": thread_id, "status": "completed"})
            return
        if mode == "report":
            if not _has_report_context(prior_history):
                yield LoopEvent(
                    LoopEventType.TEXT,
                    {
                        "text": (
                            "当前会话中没有可用的检查报告内容。请先上传报告，"
                            "解析完成后再继续提问。报告模式不会查询医学知识图谱。"
                        )
                    },
                )
                yield LoopEvent(
                    LoopEventType.DONE,
                    {"threadId": thread_id, "status": "completed"},
                )
                return
            yield LoopEvent(
                LoopEventType.REASONING,
                {"reasoning": "正在仅依据报告内容和本次补充信息组织回答"},
            )
            generated = False
            stream_report = getattr(planner, "stream_report_response", None)
            if stream_report is not None:
                async for token in stream_report(history):
                    if token:
                        generated = True
                        yield LoopEvent(LoopEventType.TEXT, {"text": token})
            if not generated:
                yield LoopEvent(
                    LoopEventType.TEXT,
                    {
                        "text": (
                            "本地报告解读模型当前不可用。报告原文仍保持隔离，"
                            "系统没有改用知识图谱生成答案，请稍后重试。"
                        )
                    },
                )
            yield LoopEvent(
                LoopEventType.DONE,
                {"threadId": thread_id, "status": "completed"},
            )
            return
        permissions = set(user.permissions)
        iteration = 0

        while iteration < MAX_MULTI_TURN_ITERATIONS:
            iteration += 1

            # ── Plan ──
            yield LoopEvent(LoopEventType.REASONING, {"reasoning": f"第 {iteration} 步：分析意图，选择工具"})
            tools = registry.describe(permissions)
            if not tools:
                yield LoopEvent(LoopEventType.ERROR, {"error": {"code": "NO_TOOLS", "message": "No tools available"}})
                return

            # Explicit structured calls (for example a form-generated write)
            # take precedence over natural-language routing.
            #
            # Entity resolution runs against the whole graph first, so any of the
            # catalog's diseases/drugs/symptoms can be addressed by name. The
            # legacy keyword table only covers business tools and colloquial
            # phrasings ("得了什么病") that name no entity at all.
            routed = None
            route_reason = ""
            entity_routed = False
            if (
                iteration == 1
                and initial_tool_call is None
                and not _has_write_intent(message)
            ):
                resolved = await registry.resolve_medical_entities(message)
                if resolved:
                    routed = _route_by_resolved_entities(message, resolved, tools)
                    if routed:
                        entity_routed = True
                        matched = "；".join(
                            f"{label} {'、'.join(names[:3])}"
                            for label, names in resolved.items()
                            if names
                        )
                        route_reason = f"知识图谱实体识别（{matched}）"
            if routed is None:
                routed = _route_medical_tool(message, tools)
                route_reason = "医学关键词匹配"
            if initial_tool_call is not None and iteration == 1:
                tool_call = initial_tool_call
                yield LoopEvent(
                    LoopEventType.REASONING,
                    {"reasoning": f"使用已验证的结构化工具请求：{tool_call.name}"},
                )
            elif routed and iteration == 1:
                tool_call = ToolCall(**routed)
                yield LoopEvent(
                    LoopEventType.REASONING,
                    {"reasoning": f"{route_reason} → {tool_call.name}"},
                )
            else:
                try:
                    tool_call = await planner.plan(message, tools, history=history[:-1])
                except Exception as exc:
                    fallback = _fallback_medical_read_tool(message, tools)
                    if fallback is None:
                        yield LoopEvent(LoopEventType.ERROR, {"error": {"code": "PLANNING_FAILED", "message": str(exc)}})
                        return
                    tool_call = ToolCall(**fallback)
                    yield LoopEvent(
                        LoopEventType.REASONING,
                        {"reasoning": "模型未选择工具，转为医疗知识混合检索"},
                    )

            if tool_call.name in WRITE_TOOL_NAMES:
                try:
                    tool_call = bind_verified_patient_context(
                        tool_call,
                        patient_context,
                    )
                    if initial_tool_call is None:
                        tool_call = ground_natural_write_call(
                            user_question,
                            tool_call,
                        )
                except AgentError as exc:
                    yield LoopEvent(
                        LoopEventType.ERROR,
                        {
                            "error": {
                                "code": exc.code,
                                "message": exc.message,
                                "details": exc.details,
                            }
                        },
                    )
                    return

            yield LoopEvent(LoopEventType.REASONING, {"reasoning": f"调用工具：{tool_call.name}"})

            # ── Execute via graph ──
            config = {"configurable": {"thread_id": thread_id}}
            initial_state = {
                "messages": history,
                "user_context": user.model_dump(mode="json", by_alias=False),
                "requested_tool": tool_call.model_dump(mode="json", by_alias=False),
            }
            runtime_token = set_runtime(
                RequestRuntime(
                    authorization, trace_id, thread_id,
                    user_id=user.user_id,
                    department_id=user.department_ids[0] if user.department_ids else None,
                )
            )
            try:
                result = await self._graph.ainvoke(initial_state, config=config)
            finally:
                reset_runtime(runtime_token)

            # ── Check for approval ──
            interrupt_value = first_interrupt_value(result)
            if interrupt_value is not None:
                pending_raw = result.get("pending_tool")
                pending = PendingTool.model_validate(pending_raw) if pending_raw else None
                if pending:
                    yield LoopEvent(LoopEventType.UI_DATA, {
                        "uiData": {
                            "type": "approval_card",
                            "threadId": thread_id,
                            "action": pending.action,
                            "riskLevel": pending.risk_level,
                            "tool": pending.name,
                            "targetParameters": pending.arguments,
                            "fingerprint": pending.fingerprint,
                        }
                    })

                # LangGraph has already checkpointed the interrupt. End this SSE
                # response so the browser can submit an independent resume request.
                return

            # ── Extract result ──
            error = result.get("error")
            if error:
                yield LoopEvent(LoopEventType.ERROR, {"error": {"code": "TOOL_FAILED", "message": str(error)}})
                return

            payload = result.get("result")
            if (
                tool_call.name == "search_knowledge"
                and isinstance(payload, dict)
                and not payload.get("items")
            ):
                no_evidence_notice = (
                    "没有找到与当前问题足够相关、可核验的医学知识。"
                    "系统不会使用低相关结果拼接答案。可以请用户补充疾病名称、"
                    "症状、检查结果或药物名称后再次提问。"
                )
                async for event in phrase_notice(no_evidence_notice):
                    yield event
                if not notice_state["generated"]:
                    yield LoopEvent(LoopEventType.ERROR, {
                        "error": {
                            "code": "GENERATION_UNAVAILABLE",
                            "message": (
                                "回答生成模型当前不可用，本次未能生成回答。"
                                "请稍后重新提问。"
                            ),
                        }
                    })
                    return
                yield LoopEvent(
                    LoopEventType.DONE,
                    {"threadId": thread_id, "status": "completed"},
                )
                return
            if tool_call.name == "search_disease" and isinstance(payload, dict):
                payload = _sanitize_disease_payload(payload, message)
            if medication_advice and isinstance(payload, dict):
                payload["safetyMode"] = "medication_guidance"
            from yuanqi_agent.sse import format_result
            formatted = format_result(
                tool_call.name,
                payload,
                user_message=user_question,
            )
            # Drug responses are emitted once as a deterministic safety-aware
            # text block below. Keep the structured tool event for clients,
            # but do not let the frontend prepend a duplicate formatted block.
            deterministic_medical_tools = {
                "search_disease",
                "search_symptom",
                "search_drug",
                "search_department",
                "search_knowledge",
            }
            tool_event_formatted = (
                "" if tool_call.name in deterministic_medical_tools else formatted
            )

            yield LoopEvent(LoopEventType.TOOL_RESULT, {
                "toolResult": {
                    "toolName": tool_call.name,
                    "result": payload,
                    "formatted": tool_event_formatted,
                },
            })

            # Update history
            history.append({"role": "assistant", "content": f"[Called tool: {tool_call.name}]"})
            import orjson
            tool_result_str = orjson.dumps(payload).decode("utf-8") if payload else "No result"
            history.append({"role": "tool", "content": tool_result_str})

            # ── 判断是否需要继续 ──
            # 如果结果为空或未找到，直接生成回复
            is_empty = (
                payload is None
                or (isinstance(payload, dict) and payload.get("found") is False)
                or (isinstance(payload, dict) and not payload.get("content") and not payload.get("disease") and not payload.get("drug"))
            )
            if is_empty or iteration >= 3:
                break

            # A resolved entity lookup already carries the section the user asked
            # for (症状 / 科室 / 检查 / 忌口 …). Chaining another keyword-routed
            # tool here would re-match generic words like "症状" as if they were
            # entity names and overwrite this good result with an empty one.
            if entity_routed:
                break

            # 尝试用关键词路由下一个工具
            next_routed = _route_medical_tool(message, tools)
            if next_routed:
                from yuanqi_agent.models import ToolCall as TC
                next_call = TC(**next_routed)
            else:
                try:
                    next_call = await planner.plan(message, tools, history=history[:-1])
                except Exception:
                    next_call = None

            if next_call is None:
                break

            # 避免重复调用同一工具
            if next_call.name == tool_call.name:
                break

            message = f"[Previous tool {tool_call.name} returned results. Now call {next_call.name}]"

        # ── Generate final response ──
        yield LoopEvent(LoopEventType.REASONING, {"reasoning": "正在生成回复..."})
        if medication_advice:
            medication_notice = _medication_safety_response(user_question)
            async for event in phrase_notice(medication_notice):
                yield event
            if not notice_state["generated"]:
                yield LoopEvent(LoopEventType.ERROR, {
                    "error": {
                        "code": "GENERATION_UNAVAILABLE",
                        "message": (
                            "回答生成模型当前不可用，本次未能生成回答。"
                            "请稍后重新提问。"
                        ),
                    }
                })
                return
            yield LoopEvent(LoopEventType.DONE, {"threadId": thread_id, "status": "completed"})
            return
        if tool_call.name in {
            "search_disease",
            "search_symptom",
            "search_drug",
            "search_department",
            "search_knowledge",
        } and isinstance(payload, dict):
            # RAG answer layer: the deterministic, governance-gated rendering
            # of the retrieval is the *evidence*; the model rewrites it into a
            # natural answer and must not add uncited facts. There is no
            # template fallback — if the model is unavailable, the request
            # fails loudly instead of silently degrading to canned text.
            evidence = formatted
            generated = False
            generated_text = ""
            stream_medical = getattr(planner, "stream_medical_answer", None)
            if stream_medical is not None and evidence.strip():
                yield LoopEvent(
                    LoopEventType.REASONING,
                    {"reasoning": "正在基于知识图谱检索证据组织回答..."},
                )
                try:
                    async for token in stream_medical(
                        user_question,
                        evidence,
                        history=_clean_history_for_generation(prior_history)[-6:],
                    ):
                        if token:
                            generated = True
                            generated_text += token
                            yield LoopEvent(LoopEventType.TEXT, {"text": token})
                except Exception:
                    LOGGER.exception(
                        "Grounded medical generation failed",
                        extra={"trace_id": trace_id, "thread_id": thread_id},
                    )
            if generated:
                # Guarantee exactly one disclaimer: append the fixed one only
                # when the model didn't already close with its own.
                tail = generated_text[-120:]
                if not any(marker in tail for marker in _DISCLAIMER_MARKERS):
                    yield LoopEvent(LoopEventType.TEXT, {
                        "text": (
                            "\n\n> 本回答由 AI 基于医学知识图谱检索内容生成，"
                            "仅供参考，不构成诊断或用药建议；具体请咨询医生。"
                        )
                    })
                yield LoopEvent(
                    LoopEventType.DONE,
                    {"threadId": thread_id, "status": "completed"},
                )
                return
            yield LoopEvent(LoopEventType.ERROR, {
                "error": {
                    "code": "GENERATION_UNAVAILABLE",
                    "message": (
                        "回答生成模型当前不可用，本次未能生成回答。"
                        "医学检索本身已成功，请稍后重新提问。"
                    ),
                }
            })
            return
        response_text = ""
        async for token in planner.stream_response(history):
            response_text += token
            yield LoopEvent(LoopEventType.TEXT, {"text": token})

        yield LoopEvent(LoopEventType.DONE, {"threadId": thread_id, "status": "completed"})

    async def resume(
        self,
        thread_id: UUID,
        decision: ApprovalDecision,
        authorization: str,
        trace_id: str,
    ) -> AgentExecution:
        user = await self._java.get_user_context(authorization, trace_id)
        config = self._config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if not snapshot.values:
            raise ThreadConflictError(
                "THREAD_NOT_FOUND",
                "No persisted Agent thread exists for this identifier",
                status_code=404,
            )
        self._assert_same_user(snapshot.values.get("user_context"), user)
        if not any(task.interrupts for task in snapshot.tasks):
            raise ThreadConflictError(
                "THREAD_NOT_INTERRUPTED",
                "Agent thread is not waiting for approval",
                status_code=409,
            )
        runtime_token = set_runtime(
            RequestRuntime(
                authorization,
                trace_id,
                thread_id,
                user_id=user.user_id,
                department_id=user.department_ids[0] if user.department_ids else None,
            )
        )
        try:
            result = await self._graph.ainvoke(
                Command(resume=decision.model_dump(mode="json", by_alias=False)),
                config=config,
            )
        finally:
            reset_runtime(runtime_token)
        return self._to_execution(thread_id, result)

    def _to_execution(self, thread_id: UUID, result: dict[str, Any]) -> AgentExecution:
        interrupt_value = first_interrupt_value(result)
        pending_raw = result.get("pending_tool")
        pending = PendingTool.model_validate(pending_raw) if pending_raw else None
        tool_name_raw = result.get("requested_tool")
        tool_name = tool_name_raw.get("name") if isinstance(tool_name_raw, dict) else None
        if interrupt_value is not None:
            status = RunStatus.WAITING_APPROVAL
        elif result.get("error"):
            status = RunStatus.FAILED
        elif result.get("approval_status") == "rejected":
            status = RunStatus.REJECTED
        else:
            status = RunStatus.COMPLETED
        return AgentExecution(
            thread_id=thread_id,
            status=status,
            result=result.get("result"),
            pending_tool=pending if status == RunStatus.WAITING_APPROVAL else None,
            approval_comment=result.get("approval_comment"),
            tool_name=tool_name,
        )

    def _assert_same_user(
        self, persisted: dict[str, Any] | None, current: VerifiedUserContext
    ) -> None:
        if not persisted:
            raise ThreadAccessDeniedError(
                "THREAD_OWNER_MISSING",
                "Persisted thread has no verified owner",
                status_code=403,
            )
        wrong_user = persisted.get("user_id") != current.user_id
        if wrong_user:
            raise ThreadAccessDeniedError(
                "THREAD_ACCESS_DENIED",
                "Agent thread belongs to another user",
                status_code=403,
            )

    def _config(self, thread_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(thread_id)}}
