from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from yuanqi_agent.errors import AgentError
from yuanqi_agent.models import StrictModel, ToolCall


class IntentPlanner(Protocol):
    async def plan(
        self,
        message: str,
        tools: list[dict[str, Any]],
        history: list[dict[str, Any]] | None = None,
    ) -> ToolCall: ...

    async def generate_response(
        self,
        history: list[dict[str, Any]],
    ) -> str: ...

    def stream_response(
        self,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[str]: ...

    async def plan_report_dialogue(
        self,
        user_message: str,
        locked_analysis: str,
    ) -> "ReportDialoguePlan | None": ...

    def stream_report_response(
        self,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[str]: ...

    def stream_medical_answer(
        self,
        question: str,
        evidence: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]: ...

    def stream_safety_notice(
        self,
        question: str,
        notice: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]: ...


class PlannerResponse(StrictModel):
    tool_call: ToolCall


class ReportDialoguePlan(StrictModel):
    acknowledgement: str = Field(min_length=1, max_length=80)
    focus: Literal[
        "blood_pressure",
        "glucose",
        "anemia",
        "infection",
        "liver",
        "lipids",
    ]


class OllamaFunctionCall(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    name: str
    arguments: dict[str, Any]


class OllamaToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    function: OllamaFunctionCall


class OllamaMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    content: str = ""
    tool_calls: list[OllamaToolCall] = Field(default_factory=list, alias="tool_calls")


class OllamaChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    message: OllamaMessage


class OllamaStreamDelta(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    content: str = ""


class OllamaStreamChunk(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    message: OllamaStreamDelta | None = None
    done: bool = False


class HttpIntentPlanner:
    """Strongly typed adapter for an internal model/tool-planning gateway."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        api_key: str | None = None,
        max_response_bytes: int = 1_000_000,
    ):
        self._client = client
        self._endpoint = endpoint
        self._api_key = api_key
        self._max_response_bytes = max_response_bytes

    async def plan(
        self,
        message: str,
        tools: list[dict[str, Any]],
        history: list[dict[str, Any]] | None = None,
    ) -> ToolCall:
        if not tools:
            raise AgentError("NO_AVAILABLE_TOOLS", "No tools are available to this user", 403)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            content = await _post_json_limited(
                self._client,
                self._endpoint,
                headers=headers,
                payload={
                    "message": message,
                    "tools": tools,
                    "history": history or [],
                    "responseSchema": PlannerResponse.model_json_schema(by_alias=True),
                },
                max_response_bytes=self._max_response_bytes,
            )
            planned = PlannerResponse.model_validate_json(content).tool_call
        except (httpx.HTTPError, ValidationError, ValueError) as exc:
            raise AgentError(
                "INTENT_PLANNER_UNAVAILABLE",
                "The intent planner returned an invalid response",
                status_code=502,
            ) from exc
        return _ensure_allowed(planned, tools)

    async def generate_response(self, history: list[dict[str, Any]]) -> str:
        return ""

    async def plan_report_dialogue(
        self,
        user_message: str,
        locked_analysis: str,
    ) -> ReportDialoguePlan | None:
        # The generic internal planning API has no dedicated constrained
        # dialogue contract. Keep the deterministic report response instead.
        return None

    async def stream_report_response(
        self,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        del history
        if False:
            yield ""

    async def stream_response(
        self,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        yield ""
        return

    async def stream_medical_answer(
        self,
        question: str,
        evidence: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        # The generic internal gateway has no grounded-generation contract.
        # Yield nothing; the answer layer surfaces GENERATION_UNAVAILABLE.
        del question, evidence, history
        if False:
            yield ""

    async def stream_safety_notice(
        self,
        question: str,
        notice: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        # Same as stream_medical_answer: no generation contract on the
        # generic gateway, so yield nothing.
        del question, notice, history
        if False:
            yield ""


class OllamaIntentPlanner:
    """Local Ollama adapter using permission-filtered native function calling."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        model: str,
        max_response_bytes: int = 1_000_000,
    ):
        self._client = client
        self._endpoint = endpoint
        self._model = model
        self._max_response_bytes = max_response_bytes

    async def plan(
        self,
        message: str,
        tools: list[dict[str, Any]],
        history: list[dict[str, Any]] | None = None,
    ) -> ToolCall:
        if not tools:
            raise AgentError("NO_AVAILABLE_TOOLS", "No tools are available to this user", 403)
        ollama_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"],
                },
            }
            for tool in tools
        ]
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是一个医学知识助手。根据用户的问题，选择最合适的一个工具函数。\n\n"
                    "工具选择规则（严格遵守）：\n"
                    "- 用户问某种疾病（如'糖尿病'、'高血压'）→ 用 search_disease\n"
                    "- 用户描述症状（如'头痛'、'发热'）或问'可能是什么病' → 用 search_symptom\n"
                    "- 用户问某种药物（如'二甲双胍'、'阿莫西林'）→ 用 search_drug\n"
                    "- 用户问'挂什么科'、'看哪个科' → 用 search_department\n"
                    "- 用户问患者相关 → 用 list_patients 或 get_patient\n"
                    "- 用户问病历相关 → 用 list_medical_records、get_medical_record 或 create_medical_record\n"
                    "- 用户问处方相关 → 用 list_prescriptions、get_prescription 或 create_prescription\n"
                    "- 创建患者、病历、处方属于写操作，系统会触发人工审批\n"
                    "- 写操作只能使用用户明确提供的值，绝不能猜测姓名、日期、"
                    "手机号、身份证号、诊断、医生、药品、金额等字段\n"
                    "- 创建患者时，用户未提供的可选字段必须为 null，未提供性别必须为 UNKNOWN\n"
                    "- 创建病历或处方时不要生成 patientId；患者由已验证的患者工作台上下文绑定\n"
                    "- 医生与科室由服务端根据当前登录身份写入，不要向用户索要或生成\n"
                    "- 创建处方或病历缺少必填字段时也不得编造；参数会由系统再次核验\n"
                    "- 只有当以上工具都不匹配时，才用 search_knowledge\n\n"
                    "不要自己回答问题，必须调用工具。如果已有工具结果，用结果决定下一步。"
                ),
            },
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        try:
            content = await _post_json_limited(
                self._client,
                self._endpoint,
                headers={"Content-Type": "application/json"},
                payload={
                    "model": self._model,
                    "messages": messages,
                    "tools": ollama_tools,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0},
                },
                max_response_bytes=self._max_response_bytes,
            )
            response = OllamaChatResponse.model_validate_json(content)
            if len(response.message.tool_calls) != 1:
                raise ValueError("Ollama must select exactly one tool")
            function = response.message.tool_calls[0].function
            planned = ToolCall(name=function.name, arguments=function.arguments)
        except (httpx.HTTPError, ValidationError, ValueError) as exc:
            raise AgentError(
                "INTENT_PLANNER_UNAVAILABLE",
                "The local intent planner returned an invalid response",
                status_code=502,
            ) from exc
        return _ensure_allowed(planned, tools)

    async def generate_response(self, history: list[dict[str, Any]]) -> str:
        """Generate a natural-language response based on the conversation history."""
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an intelligent medical assistant. Summarize the "
                    "tool execution results into a clear, concise response for the user. "
                    "For medical results, organize by disease/symptom/drug clearly. "
                    "Never prescribe a specific medicine or dosage from chat context. "
                    "If the user asks what medicine to take, explain that individualized "
                    "selection requires a clinician and relevant measurements and history. "
                    "Ignore unrelated or zero-confidence retrieval results. "
                    "Every medical factual claim must be directly supported by a cited "
                    "tool result. Preserve citation identifiers such as [K1]. If evidence "
                    "is missing or marked insufficient, explicitly abstain instead of "
                    "using model memory. Never present graph associations as a diagnosis, "
                    "mandatory examination, or personalized treatment. "
                    "Use the same language as the user's last message. Do not call any tools."
                ),
            },
        ]
        messages.extend(history)
        try:
            content = await _post_json_limited(
                self._client,
                self._endpoint,
                headers={"Content-Type": "application/json"},
                payload={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.3},
                },
                max_response_bytes=self._max_response_bytes,
            )
            parsed = OllamaChatResponse.model_validate_json(content)
            return parsed.message.content if hasattr(parsed.message, "content") else ""
        except (httpx.HTTPError, ValidationError, ValueError):
            return ""

    async def plan_report_dialogue(
        self,
        user_message: str,
        locked_analysis: str,
    ) -> ReportDialoguePlan | None:
        """Select a conversational acknowledgement and one bounded follow-up.

        Medical facts remain in ``locked_analysis`` and are never delegated to
        the model. The model may only choose one predefined follow-up focus.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "你是医疗报告解读助手的对话协调层，不负责诊断、处方或改写医学事实。"
                    "依据锁定分析，生成一句自然、克制的承接语，并从允许的 focus 中选择"
                    "下一轮最值得询问的一项。承接语不得给出新数值、新疾病、新药物、"
                    "治疗建议或诊断结论，不得声称已由医生确认。只输出符合 JSON Schema 的对象。"
                    "acknowledgement 必须是一句自然中文，不能填写 focus 的英文值。"
                    "例如：{\"acknowledgement\":\"了解了，我会结合你补充的情况继续看这份报告。\","
                    "\"focus\":\"glucose\"}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户补充：\n{user_message}\n\n"
                    f"锁定分析（只能用于选择重点，不得改写）：\n{locked_analysis}"
                ),
            },
        ]
        try:
            content = await _post_json_limited(
                self._client,
                self._endpoint,
                headers={"Content-Type": "application/json"},
                payload={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "format": ReportDialoguePlan.model_json_schema(),
                    "options": {"temperature": 0.2},
                },
                max_response_bytes=self._max_response_bytes,
            )
            response = OllamaChatResponse.model_validate_json(content)
            return ReportDialoguePlan.model_validate_json(response.message.content)
        except (httpx.HTTPError, ValidationError, ValueError):
            return None

    async def stream_response(
        self,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Stream a natural-language response token by token."""
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an intelligent medical assistant. Summarize the "
                    "tool execution results into a clear, concise response for the user. "
                    "For medical results, organize by disease/symptom/drug clearly. "
                    "Never prescribe a specific medicine or dosage from chat context. "
                    "If the user asks what medicine to take, explain that individualized "
                    "selection requires a clinician and relevant measurements and history. "
                    "Ignore unrelated or zero-confidence retrieval results. "
                    "Every medical factual claim must be directly supported by a cited "
                    "tool result. Preserve citation identifiers such as [K1]. If evidence "
                    "is missing or marked insufficient, explicitly abstain instead of "
                    "using model memory. Never present graph associations as a diagnosis, "
                    "mandatory examination, or personalized treatment. "
                    "Use the same language as the user's last message. Do not call any tools."
                ),
            },
        ]
        messages.extend(history)
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.3},
        }
        try:
            async with self._client.stream(
                "POST", self._endpoint, headers=headers, json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = OllamaStreamChunk.model_validate_json(line)
                        if chunk.message and chunk.message.content:
                            yield chunk.message.content
                    except ValidationError:
                        continue
        except httpx.HTTPError:
            return

    async def stream_medical_answer(
        self,
        question: str,
        evidence: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Rewrite governance-gated retrieval evidence into a natural answer.

        The evidence text is the deterministic, review-aware rendering of the
        knowledge-graph / vector retrieval. The model must stay strictly inside
        it: fluency is delegated to the model, facts are not.
        """
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是医疗知识问答助手。下面会给你一段【检索证据】，"
                    "它来自医学知识图谱和向量检索，且已经过审核状态过滤。\n\n"
                    "严格遵守：\n"
                    "1. 只能使用【检索证据】中出现的医学事实作答，"
                    "禁止补充证据之外的疾病、症状、机制、数值、检查、药物或剂量，"
                    "即使你记得相关知识也不能加入。\n"
                    "2. 证据里只给出名称、没有解释时，不得替它编造原因、机制或说明——"
                    "只能列出名称本身，并说明知识库未提供更多细节。"
                    "与用户问题明显无关的条目直接忽略，不要强行解释它和问题的关系。\n"
                    "3. 引用标识（如 [K1]）只能标在证据里真实存在的事实后面；"
                    "你自己组织的过渡句、建议句一律不得标注引用。"
                    "证据中的来源链接（如 WHO 链接）放在对应事实附近。\n"
                    "4. 若证据表明未找到相关信息，如实告知没有查到，"
                    "并说明用户可以补充什么（如完整药名、疾病名称）；"
                    "不得在没有证据时给出多喝水、注意休息之类的笼统建议。\n"
                    "5. 用自然、流畅、有条理的中文直接回答用户的问题：先给核心结论，"
                    "再展开细节；不要机械照抄证据的排版。\n"
                    "6. 证据正文中的审核状态说明、就医提醒需保留其含义；"
                    "但不要在结尾自行添加'仅供参考''请咨询医生'之类的免责段落，"
                    "系统会统一附加声明。\n"
                    "7. 不做诊断，不推荐具体药物或剂量。"
                    "不要输出'根据检索证据'这类套话，直接回答即可。"
                ),
            },
        ]
        if history:
            messages.extend(
                item for item in history
                if item.get("role") in {"user", "assistant"}
            )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n\n"
                    f"【检索证据】\n{evidence}\n\n"
                    "请基于以上证据回答用户问题。"
                ),
            }
        )
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.3},
        }
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = OllamaStreamChunk.model_validate_json(line)
                        if chunk.message and chunk.message.content:
                            yield chunk.message.content
                    except ValidationError:
                        continue
        except httpx.HTTPError:
            return

    async def stream_safety_notice(
        self,
        question: str,
        notice: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Rephrase a rule-triggered safety notice into natural language.

        The trigger decision and the notice content are owned by deterministic
        rules; the model only owns the wording. It must not answer the user's
        underlying question beyond what the notice conveys.
        """
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是医疗助手的安全提示表达层。下面的【安全提示】是系统安全规则"
                    "生成的固定内容，你的任务只是把它改写成自然、温和但态度明确的中文回复。\n\n"
                    "严格遵守：\n"
                    "1. 不得回答或部分回答用户原本的问题：不推荐任何药物或剂量、"
                    "不做诊断、不猜测可能的疾病或病因（例如不要写'可能是某某病'）、"
                    "不补充提示之外的医学事实，即使你知道答案。\n"
                    "2. 提示中的关键信息一条都不能丢：就医建议、急诊指征（包括具体数值"
                    "和症状列表）、风险说明必须全部保留，数值不得改动；"
                    "提示里每一条具体的行为指令（如'不要自行驾车'、'不要自行停药'）"
                    "都必须逐条保留原意，不能合并成笼统的说法。\n"
                    "3. 可以调整语气和组织方式，适当共情，但不得淡化风险或弱化语气。\n"
                    "4. 直接输出回复内容，不要解释你在做什么。"
                ),
            },
        ]
        if history:
            messages.extend(
                item for item in history
                if item.get("role") in {"user", "assistant"}
            )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"用户消息：{question}\n\n"
                    f"【安全提示】\n{notice}\n\n"
                    "请把安全提示改写成对这位用户的自然回复。"
                ),
            }
        )
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.2},
        }
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = OllamaStreamChunk.model_validate_json(line)
                        if chunk.message and chunk.message.content:
                            yield chunk.message.content
                    except ValidationError:
                        continue
        except httpx.HTTPError:
            return

    async def stream_report_response(
        self,
        history: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Answer only from the uploaded report conversation context."""
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是检查报告解读助手。只能使用对话中已经出现的报告原文、"
                    "结构化指标和用户主动补充的信息回答。禁止调用或假设任何知识图谱内容，"
                    "禁止编造报告中没有的数值、诊断、用药或检查结果。"
                    "先直接回答当前问题，再说明不确定性；每轮最多追问一个最有价值的问题。"
                    "如涉及诊断或处方，只能解释信息边界并建议由医生结合临床情况确认。"
                    "如出现明确危险信号，建议立即就医。使用中文，表达自然简洁。"
                ),
            },
        ]
        messages.extend(history)
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.2},
        }
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = OllamaStreamChunk.model_validate_json(line)
                        if chunk.message and chunk.message.content:
                            yield chunk.message.content
                    except ValidationError:
                        continue
        except httpx.HTTPError:
            return


async def _post_json_limited(
    client: httpx.AsyncClient,
    endpoint: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    max_response_bytes: int,
) -> bytes:
    content = bytearray()
    async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            if len(content) + len(chunk) > max_response_bytes:
                raise ValueError("planner response exceeds the configured limit")
            content.extend(chunk)
    return bytes(content)


def _ensure_allowed(planned: ToolCall, tools: list[dict[str, Any]]) -> ToolCall:
    allowed_names = {str(tool["name"]) for tool in tools}
    if planned.name not in allowed_names:
        raise AgentError(
            "PLANNER_SELECTED_FORBIDDEN_TOOL",
            "The intent planner selected a tool unavailable to this user",
            status_code=403,
        )
    return planned
